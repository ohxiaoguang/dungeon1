#include "../../host/dm_input.h"
// Diagnostic only: DM_GL_FRAME_CAPTURE names a file "id count directory".
// A changed id arms <=180 frames, <=360 total. At most four 8 MiB readbacks
// are in flight. Raw RGBA rows are bottom-up. Copy on the producer GL queue.
static void gl_frame_capture(void) {
    static int init; static const char *request;
    static unsigned long long last; static unsigned remain, total; static int wait_click;
    static char dir[768]; static _Atomic int pending;
    static uint64_t prev_draw, prev_pass;
    uint64_t draws = g_n_draw - prev_draw, passes = g_n_pass - prev_pass;
    prev_draw = g_n_draw; prev_pass = g_n_pass;
    if (!init) { init = 1; request = getenv("DM_GL_FRAME_CAPTURE"); }
    if (!request) return;
    FILE *f = fopen(request, "r");
    if (f) {
        unsigned long long id; unsigned count; char path[768];
        if (fscanf(f, "%llu %u %767[^\n]", &id, &count, path) == 3 && id != last && count >= 1 && count <= 180 && total < 360) {
            last = id; remain = count < 360 - total ? count : 360 - total;
            strlcpy(dir, path, sizeof dir);
            wait_click = getenv("DM_GL_CAPTURE_CLICK") && !strcmp(getenv("DM_GL_CAPTURE_CLICK"), "1");
            GLOG("[capture] armed request %llu: %u frames -> %s", id, remain, dir);
        }
        fclose(f);
    }
    g_capture_tracing = 0;
    if (!remain) return;
    if (wait_click) { dm_pointer_snapshot p; if (!dm_mouse_snapshot(&p) || !(p.buttons & DM_MOUSE_LEFT)) return; wait_click = 0; }
    g_capture_tracing = getenv("DM_GL_CAPTURE_TRACE") && !strcmp(getenv("DM_GL_CAPTURE_TRACE"), "1");
    remain--; total++;
    uint64_t frame = g_frames + 1, serial = g_serial;
    id<MTLTexture> tex = g_win.col[g_win.cur];
    NSUInteger row = tex.width * 4, bytes = row * tex.height;
    if (!tex || tex.pixelFormat != MTLPixelFormatRGBA8Unorm || bytes > 8 * 1024 * 1024 || atomic_load(&pending) >= 4) {
        GLOG("[capture] frame %llu DROPPED (unsupported target or backlog)", (unsigned long long)frame); return;
    }
    pass_end();
    id<MTLBuffer> rb = [g_dev newBufferWithLength:bytes options:MTLResourceStorageModeShared];
    if (!rb) { GLOG("[capture] frame %llu allocation failed", (unsigned long long)frame); return; }
    id<MTLCommandBuffer> cb = cb_get(); id<MTLBlitCommandEncoder> enc = [cb blitCommandEncoder];
    [enc copyFromTexture:tex sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(tex.width,tex.height,1)
                toBuffer:rb destinationOffset:0 destinationBytesPerRow:row destinationBytesPerImage:bytes];
    [enc endEncoding];
    NSString *path = [NSString stringWithFormat:@"%s/frame-%08llu.rgba", dir, (unsigned long long)frame];
    GLOG("[capture] frame=%llu submission=%llu source=%llu draws=%llu passes=%llu fb=%u vp=%d,%d,%d,%d scissor=%d,%d,%d,%d enabled=%d blend=%d mask=%u %lux%lu -> %s",
        (unsigned long long)frame,(unsigned long long)serial,(unsigned long long)g_win.serial[g_win.cur],(unsigned long long)draws,(unsigned long long)passes,S.fb,
        S.vp[0],S.vp[1],S.vp[2],S.vp[3],S.sc[0],S.sc[1],S.sc[2],S.sc[3],S.scissor,S.blend,S.cmask,(unsigned long)tex.width,(unsigned long)tex.height,path.UTF8String);
    atomic_fetch_add(&pending,1);
    [cb addCompletedHandler:^(id<MTLCommandBuffer> done) {
        int ok = 0;
        if (done.status == MTLCommandBufferStatusCompleted) { FILE *out = fopen(path.UTF8String,"wb"); if (out) { ok = fwrite(rb.contents,1,bytes,out) == bytes; fclose(out); } }
        if (!ok) GLOG("[capture] frame %llu WRITE/GPU FAILED status=%lu",(unsigned long long)frame,(unsigned long)done.status);
        atomic_fetch_sub(&pending,1);
    }];
}
