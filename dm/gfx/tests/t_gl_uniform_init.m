// Link-time GLSL defaults must reach actual GPU draws, survive glUniform overrides
// and be restored on relink. No game shaders or resources are used by this test.
#include "../gl/hle_gl.m"
void *front_metal_layer(void) { return NULL; }
module_t *module_of(const void *p) { (void)p; return NULL; }
module_t g_mod[MAX_MOD]; int g_nmod;
void svc_thread_dump(void) {}
uint64_t now_ns(void) { return clock_gettime_nsec_np(CLOCK_UPTIME_RAW); }
void dm_vi_layer_size(int *w, int *h) { *w = *h = 8; }
int dm_mouse_snapshot(dm_pointer_snapshot *p) { memset(p, 0, sizeof *p); return 0; }
static int checks, failed;
#define CHECK(c, label) do { checks++; if (!(c)) { failed++; fprintf(stderr,"FAIL: %s\n",label); } } while (0)
static void pixel(GLuint pr, const float want[3]) {
    h_glUseProgram(pr); h_glViewport(0,0,8,8); h_glDrawArrays(GL_TRIANGLES,0,3);
    uint8_t out[8*8*4] = {0}; h_glReadPixels(0,0,8,8,GL_RGBA,GL_UNSIGNED_BYTE,out);
    for (int i=0;i<64;i++) for (int c=0;c<3;c++) CHECK(abs((int)out[i*4+c]-(int)lroundf(want[c]*255))<=1,"GPU pixel matches uniform default/override");
}
int main(void) { @autoreleasepool {
    // Device setup exercises the same pipeline and uniform upload as the host.
    dev_init();
    NSError *error=nil;
    id<MTLLibrary> lib=[g_dev newLibraryWithSource:@"#include <metal_stdlib>\nusing namespace metal;\n"
      "struct V { float4 p [[position]]; };\n"
      "vertex V vs(uint i [[vertex_id]]) { V v; v.p=float4(float2((i<<1)&2,i&2)*2-1,0,1); return v; }\n"
      "fragment float4 fs(constant float4 *w [[buffer(0)]]) { return float4(w[0].x,w[1].x,w[2].x,1); }\n" options:nil error:&error];
    CHECK(lib!=nil,"synthetic shaders compile"); if (!lib) return 1;
    float defaults[12]={.2f,0,0,0,.4f,0,0,0,.6f,0,0,0};
    shuni member={.name="weights",.off=0,.count=3,.stride=16,.type=T_FLOAT};
    shinfo vi={.ub_slot=-1}, fi={.frag=1,.ub_slot=0,.ub_size=48,.nu=1,.u=&member,.initial=(uint8_t *)defaults};
    GLuint vs=h_glCreateShader(GL_VERTEX_SHADER), fs=h_glCreateShader(GL_FRAGMENT_SHADER), pr=h_glCreateProgram();
    shader_of(vs)->si=&vi; shader_of(vs)->fn=[lib newFunctionWithName:@"vs"];
    shader_of(fs)->si=&fi; shader_of(fs)->fn=[lib newFunctionWithName:@"fs"];
    h_glAttachShader(pr,vs); h_glAttachShader(pr,fs); h_glLinkProgram(pr);
    CHECK(prog_of(pr)->linked,"program links");
    const float initial[3]={.2f,.4f,.6f}, override[3]={.8f,.1f,.3f}, zero[3]={0};
    for (int i=0;i<3;i++) { char name[32]; snprintf(name,sizeof name,"weights[%d]",i); float v=-1;
        h_glGetUniformfv(pr,h_glGetUniformLocation(pr,name),&v); CHECK(fabsf(v-initial[i])<1e-6f,"GetUniform returns link-time array defaults"); }
    pixel(pr,initial);
    h_glUniform1fv(h_glGetUniformLocation(pr,"weights"),3,override); pixel(pr,override);
    h_glLinkProgram(pr); pixel(pr,initial);
    fi.initial=NULL; h_glLinkProgram(pr); pixel(pr,zero);
    fprintf(stderr,"t_gl_uniform_init: %d checks, %d failed\n",checks,failed);
    return failed?1:0;
} }
