// Mac two-finger swipe -> game contact: the shared adapter (dm/host/dm_swipe.h) on its own, and the exact publication
// sequence front_mac.m produces for a trackpad gesture, driven through the host's own touch layer (hle_touch.c) and its
// gesture recognizer. The values below are written by hand from the rules in those files, not computed by them.
//
// What the game must see: a contact that opens at the pointer, moves down the panel when the fingers move down (the
// torch), and ends with no Tap - because a Tap is the only thing this build turns into a click. Inertia and a stalled
// trackpad must not leave a contact behind, which is what the idle timeout is for: a contact nobody ends would be
// promoted to Press after 0.5 s by the title's own clock.
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <unistd.h>
#include "dm_input.h"
#include "dm_swipe.h"
typedef struct { uint32_t id; float x, y; } dm_touch;
void dm_touch_set_from(const dm_touch *t, int n, int source);
void dm_touch_cancel_from(int source);
int gesture_fill(void *out, int n, uint64_t now_ns);
int touch_fill_n(void *out, int max, uint64_t now_ns);
void dm_touch_contact_snapshot(void *out);
void dm_touch_policy_activate(int active);
typedef struct { uint64_t generation, revision, sample, down_ns; int source, count, id, x, y, down_x, down_y, phase; } snap;
typedef struct { int64_t samp, ctx; int32_t type, dir, x, y, dx, dy; float vx, vy; uint32_t attr; float scale, rot; int32_t npt, pt[4][2]; } gesture_state;
enum { IDLE, COMPLETE, CANCEL, TOUCH, PRESS, TAP, PAN, SWIPE, PINCH, ROTATE };
enum { DM_CONTACT_UNKNOWN, DM_CONTACT_IOS, DM_CONTACT_MAC_LEFT, DM_CONTACT_MAC_SWIPE };
enum { DM_CONTACT_DOWN, DM_CONTACT_HOLDING, DM_CONTACT_PRESS, DM_CONTACT_CANCELLED, DM_CONTACT_RELEASED };
static int fails, cases;
static gesture_state g[16]; static int gn;
static int frame_touches;
static const uint64_t S = 1000000000ull, MS = 1000000ull;
static void rd(uint64_t t) {
    uint8_t buf[0x10 + 0x28 * 16];
    int k = touch_fill_n(buf, 16, t);
    int32_t cnt = 0; memcpy(&cnt, buf + 8, 4);
    frame_touches = k ? cnt : 0;
    memset(g, 0xcc, sizeof g); gn = gesture_fill(g, 16, t);
}
static void check(const char *what, int ok) {
    cases++; if (!ok) fails++;
    printf("%s %s\n", ok ? "✓" : "✗", what);
}
static int64_t ctx_top(void) { return gn > 0 ? g[0].ctx : -1; }
static int ctx_has(int64_t ctx, int type) { for (int i = 0; i < gn; i++) if (g[i].ctx == ctx && g[i].type == type) return 1; return 0; }
static int newest_is(int type, int x, int y) {
    return gn > 0 && g[0].type == type && g[0].x == x && g[0].y == y && g[0].npt == 1 && g[0].pt[0][0] == x && g[0].pt[0][1] == y;
}
static snap now_snap(void) { snap s; memset(&s, 0, sizeof s); dm_touch_contact_snapshot(&s); return s; }
// front_mac.m's publication for a swipe: one contact at the adapter's position, from the MAC_SWIPE source.
static void publish(const dm_swipe *s) {
    dm_touch t = {0, s->x, s->y};
    dm_touch_set_from(&t, 1, DM_CONTACT_MAC_SWIPE);
}

int main(void) {
    dm_touch_policy_activate(1);   // Darkest Dungeon turns it on; it only promotes the snapshot's hold

    // ---- 1. The adapter on its own: signs, distance, edges, idle ----------------------------------------
    // Natural scrolling on (isDirectionInvertedFromDevice): the fingers' own direction, so a downward swipe is positive.
    check("sign: natural scrolling keeps the finger direction", dm_swipe_component(12.5, 1) == 12.5f);
    check("sign: without it the delta is negated, so a downward swipe is still positive", dm_swipe_component(12.5, 0) == -12.5f);
    check("sign: zero is zero either way", dm_swipe_component(0, 0) == 0 && dm_swipe_component(0, 1) == 0);

    dm_swipe w; memset(&w, 0, sizeof w);
    const uint64_t t0 = 1000 * S;
    float nx = 0, ny = 0;
    dm_swipe_begin(&w, t0, 0.5f, 0.5f);
    int moved = dm_swipe_move(&w, t0 + 16 * MS, 0, 36, 1280, 720, DM_SWIPE_GAIN, &nx, &ny);
    check("move: a 36-point downward swipe on a 720-point picture is 1/20 of the panel",
          moved && ny > 0.5499f && ny < 0.5501f);
    dm_swipe_move(&w, t0 + 32 * MS, 0, 100000, 1280, 720, 1, &nx, &ny);
    check("move: the contact is clamped to the bottom of the picture", ny == 0.999f);
    dm_swipe_move(&w, t0 + 34 * MS, 0, -100000, 1280, 720, 1, &nx, &ny);
    check("move: and to the top edge", ny == 0);
    dm_swipe_begin(&w, t0, 0.5f, 0.5f);
    dm_swipe_move(&w, t0, 0, 36, 1280, 720, 2.0f, &nx, &ny);
    check("move: the gain scales the travel", ny > 0.5999f && ny < 0.6001f);
    check("idle: not before the timeout", !dm_swipe_idle(&w, t0 + DM_SWIPE_IDLE_NS - MS));
    check("idle: and yes after it", dm_swipe_idle(&w, t0 + DM_SWIPE_IDLE_NS));
    dm_swipe_end(&w);
    check("end: a finished swipe is never idle again", !dm_swipe_idle(&w, t0 + 10 * S));

    // ---- 2. What the game sees: Touch -> Pan -> Complete, at the pointer, with no Tap ---------------------
    dm_swipe s; memset(&s, 0, sizeof s);
    uint64_t t = 2000 * S;
    // The pointer is at A (640,360); the fingers are anywhere on the trackpad.
    dm_swipe_begin(&s, t, 0.5f, 0.5f);
    publish(&s); rd(t);
    int64_t ctx = ctx_top();
    check("game: the contact opens at the pointer (640,360), one point", newest_is(TOUCH, 640, 360) && frame_touches == 1);
    check("game: its source is the swipe, not the left button (the roster hold must not see it)", now_snap().source == DM_CONTACT_MAC_SWIPE);
    // A downward swipe of 72 points moves the contact 72 panel rows, as a finger drag of the same distance would.
    dm_swipe_move(&s, t + 16 * MS, 0, 72, 1280, 720, DM_SWIPE_GAIN, &nx, &ny); publish(&s); rd(t + 16 * MS);
    check("game: it moves down the panel as a Pan (640,432)", newest_is(PAN, 640, 432));
    dm_swipe_move(&s, t + 32 * MS, 0, 72, 1280, 720, DM_SWIPE_GAIN, &nx, &ny); publish(&s); rd(t + 32 * MS);
    check("game: and keeps following (640,504)", newest_is(PAN, 640, 504));
    dm_swipe_end(&s); dm_touch_set_from(NULL, 0, DM_CONTACT_MAC_SWIPE); rd(t + 48 * MS);
    check("game: the release ends it without a Tap", (g[0].type == COMPLETE || g[0].type == SWIPE) && !ctx_has(ctx, TAP));
    check("game: no Press ever appeared in it", !ctx_has(ctx, PRESS));
    rd(t + 64 * MS);

    // ---- 3. A swipe that is never ended would become Press: that is what the timeout prevents ------------
    memset(&s, 0, sizeof s);
    t = 3000 * S;
    dm_swipe_begin(&s, t, 0.5f, 0.3f); publish(&s); rd(t);
    int64_t stuck = ctx_top();
    usleep(560 * 1000);
    rd(t + 600 * MS);   // the game's next frame, 0.6 s later: this is the read that promotes it
    check("timeout: an unended contact does reach PRESS (the title's own clock)", now_snap().phase == DM_CONTACT_PRESS);
    check("timeout: so the adapter reports it idle well before that", dm_swipe_idle(&s, dm_swipe_now_ns()));
    // and once the front end ends it, the release is Complete, not a Tap
    dm_swipe_end(&s); dm_touch_set_from(NULL, 0, DM_CONTACT_MAC_SWIPE); rd(t + 700 * MS);
    check("timeout: ended, its release clicks nothing", g[0].type == COMPLETE && !ctx_has(stuck, TAP));

    // ---- 4. Losing focus cancels the contact: never a lift (a lift can arrive as the game's Tap) ---------
    memset(&s, 0, sizeof s);
    t = 4000 * S;
    dm_swipe_begin(&s, t, 0.5f, 0.5f); publish(&s); rd(t);
    dm_swipe_move(&s, t + 16 * MS, 0, 40, 1280, 720, 1, &nx, &ny); publish(&s); rd(t + 16 * MS);
    dm_swipe_end(&s); dm_touch_cancel_from(DM_CONTACT_MAC_SWIPE); rd(t + 32 * MS);
    check("cancel: it is reported as CANCEL with no point", gn > 0 && g[0].type == CANCEL && g[0].npt == 0);
    check("cancel: the contact is left CANCELLED", now_snap().phase == DM_CONTACT_CANCELLED);
    rd(t + 48 * MS);
    check("cancel: no Tap was produced", !ctx_has(ctx_top(), TAP));

    // ---- 5. The pointer is not moved by the swipe, and the next click still works ------------------------
    // The adapter keeps its own position; front_mac.m never calls dm_mouse_set from it, so the system pointer and the
    // Mouse HID sample stay where they were. A tap/left click afterwards is still one Tap at the pointer.
    memset(&s, 0, sizeof s);
    t = 5000 * S;
    dm_swipe_begin(&s, t, 0.25f, 0.75f); publish(&s); rd(t);
    dm_swipe_move(&s, t + 16 * MS, 0, 24, 1280, 720, 1, &nx, &ny); publish(&s); rd(t + 16 * MS);
    dm_swipe_end(&s); dm_touch_set_from(NULL, 0, DM_CONTACT_MAC_SWIPE); rd(t + 32 * MS);
    rd(t + 48 * MS);
    dm_touch click = {0, 0.25f, 0.75f};
    dm_touch_set_from(&click, 1, DM_CONTACT_MAC_LEFT);
    rd(t + 100 * MS);
    check("after: a left click still opens at its own point (320,540)", newest_is(TOUCH, 320, 540));
    dm_touch_set_from(NULL, 0, DM_CONTACT_MAC_LEFT); rd(t + 116 * MS);
    check("after: and is still the game's Tap", newest_is(TAP, 320, 540));

    printf("mac swipe audit: %d checks, %d failed\n", cases, fails);
    return fails != 0;
}
