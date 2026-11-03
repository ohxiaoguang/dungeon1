// Virtual-trackpad input audit: the exact publication sequence DmGamepad.m produces in trackpad mode, driven through
// the host's own touch layer (hle_touch.c) and its gesture recognizer, with the expected values written by hand from
// the rules in hle_touch.c - not computed by the code under test.
//
// The overlay publishes as little as it can:
//   · a finger that is only down publishes NOTHING (that is the fix for touching the glass and picking up the item
//     under the pointer), so the game's touch state is empty and its gesture history does not move;
//   · a tap publishes one contact at the cursor, down and up in the same turn (two publications, no frame between),
//     which the touch layer reports as Start then End and the recognizer as Touch then Tap - one click, at the cursor;
//   · a drag publishes one contact at the cursor and moves it, which is Touch then Pan then Complete - no Tap;
//   · a still finger opens one contact only after the hold window, and holding it past the game's own 0.5 s Press
//     threshold is what produces Press: the release of that contact is Complete, never a Tap.
// So the checks below are about what the game can see: a Tap carries the CURSOR (never the glass), a long still finger
// produces no contact at all, a drag never clicks, and a cancelled drag never lifts.
//
// The gesture history keeps the newest 16 entries across gestures, so every "no Tap here" check is scoped to the
// contact's own context number - the field the game uses to tell one gesture from the next.
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <unistd.h>
#include "dm_input.h"
typedef struct { uint32_t id; float x, y; } dm_touch;
void dm_touch_set_from(const dm_touch *t, int n, int source);
void dm_touch_cancel_from(int source);
int gesture_fill(void *out, int n, uint64_t now_ns);
int touch_fill_n(void *out, int max, uint64_t now_ns);
void dm_touch_contact_snapshot(void *out);   // dm_contact_snapshot (front.h), same layout as snap below
void dm_touch_policy_activate(int active);
void dm_touch_hold_tap(int on);
typedef struct { uint64_t generation, revision, sample, down_ns; int source, count, id, x, y, down_x, down_y, phase; } snap;
typedef struct { int64_t samp, ctx; int32_t type, dir, x, y, dx, dy; float vx, vy; uint32_t attr; float scale, rot; int32_t npt, pt[4][2]; } gesture_state;
enum { IDLE, COMPLETE, CANCEL, TOUCH, PRESS, TAP, PAN, SWIPE, PINCH, ROTATE };
enum { NEW = 1u << 4, DOUBLE = 1u << 8 };
enum { DM_CONTACT_UNKNOWN, DM_CONTACT_IOS, DM_CONTACT_MAC_LEFT };
enum { DM_CONTACT_DOWN, DM_CONTACT_HOLDING, DM_CONTACT_PRESS, DM_CONTACT_CANCELLED, DM_CONTACT_RELEASED };
static int fails, cases;
static gesture_state g[16]; static int gn;
static int frame_touches;                                   // what the game's touch read returned this frame
static const uint64_t S = 1000000000ull, MS = 1000000ull;
// One frame of the game's input poll: it reads the touch screen (for its Start/End latch) and the gesture history.
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
// ---- The overlay's three publications, exactly as DmGamepad.m makes them ----
// A tap: one contact at the cursor, down and up in the same turn (clickAtCursor).
static void tap(float x, float y) {
    dm_touch t = {0, x, y};
    dm_touch_set_from(&t, 1, DM_CONTACT_IOS);
    dm_touch_set_from(NULL, 0, DM_CONTACT_IOS);
}
static void down(float x, float y) { dm_touch t = {0, x, y}; dm_touch_set_from(&t, 1, DM_CONTACT_IOS); }
static void lift(void) { dm_touch_set_from(NULL, 0, DM_CONTACT_IOS); }
static snap now_snap(void) { snap s; memset(&s, 0, sizeof s); dm_touch_contact_snapshot(&s); return s; }
static int64_t ctx_top(void) { return gn > 0 ? g[0].ctx : -1; }
static int ctx_has(int64_t ctx, int type) { for (int i = 0; i < gn; i++) if (g[i].ctx == ctx && g[i].type == type) return 1; return 0; }
// The newest entry, by type and point: the fields the game reads (type, x/y and the point list)
static int newest_is(int type, int x, int y) {
    return gn > 0 && g[0].type == type && g[0].x == x && g[0].y == y && g[0].npt == 1 && g[0].pt[0][0] == x && g[0].pt[0][1] == y;
}

int main(void) {
    dm_touch_policy_activate(1);   // Darkest Dungeon activates it on iOS; it only makes the snapshot promote holds
    dm_touch_hold_tap(0);

    // ---- 1. A tap: one contact, at the cursor, and nothing else -------------------------------------------
    // The pointer is at A (640,360) and the player's finger is somewhere else entirely. The overlay publishes A.
    tap(0.5f, 0.5f);
    rd(1 * S);
    check("tap: the contact opens at the cursor A (640,360), with one point", newest_is(TOUCH, 640, 360) && frame_touches == 1);
    int64_t tap_ctx = ctx_top();
    rd(1 * S + 16 * MS);
    check("tap: the next frame reports its release as a Tap at A", newest_is(TAP, 640, 360));
    check("tap: that Tap carried no double-tap attribute", g[0].attr == 0);
    check("tap: it is one contact with no Pan and no Press", !ctx_has(tap_ctx, PAN) && !ctx_has(tap_ctx, PRESS));
    rd(1 * S + 33 * MS);   // the End has been reported: this read is the first one with no point at all
    check("tap: and the touch state is empty again once it has been read", frame_touches == 0);

    rd(1 * S + 50 * MS);   // the Idle entry that follows a Complete/anything is the host's, not a new contact

    // ---- 2. A finger that is only down publishes nothing: the bug this round fixes -------------------------
    // Nothing is published at all here - that is what the overlay does while a single finger is down (moving the
    // cursor publishes a position, never a contact, and a still finger publishes nothing whatsoever). The game must
    // therefore see no finger, no Touch, no Press and no Tap, however long the player rests on an item.
    int64_t quiet_ctx = ctx_top();
    for (int i = 0; i < 6; i++) rd(2 * S + (uint64_t)i * 100 * MS);   // 0.6 s of a still finger over an item
    check("still finger: the game's touch state stays empty", frame_touches == 0);
    check("still finger: no Touch, Press or Tap is ever created", ctx_top() == quiet_ctx && !ctx_has(quiet_ctx, PRESS));
    check("still finger: the contact snapshot has no live contact", now_snap().count == 0);

    // Moving the cursor publishes a position on the separate channel (dm_cursor_set, hle_hid.c) and no contact at all,
    // so the game's touch state stays empty across the whole stroke; that path is asserted in the source checks
    // (dm/ios/tests/test_trackpad_policy.py) because this test links only the touch layer.
    for (int i = 0; i < 4; i++) rd(2 * S + (uint64_t)(700 + i * 100) * MS);
    check("cursor: a stroke over an item still publishes no touch point", frame_touches == 0);
    check("cursor: and creates no gesture entry", ctx_top() == quiet_ctx);

    // ---- 3. A drag: one contact at the cursor, moving, and no click at the end -----------------------------
    down(0.5f, 0.5f);                      // what the overlay publishes once two fingers have paused
    rd(3 * S);
    int64_t drag_ctx = ctx_top();
    check("drag: the contact opens at the cursor (640,360)", newest_is(TOUCH, 640, 360) && frame_touches == 1);
    dm_touch_set_from(&(dm_touch){0, 0.5703125f, 0.5f}, 1, DM_CONTACT_IOS);   // 90 px to the right
    rd(3 * S + 16 * MS);
    check("drag: it moves as a Pan, not a second Touch", newest_is(PAN, 730, 360));
    check("drag: the contact snapshot is CANCELLED while it moves (the hold policies disarm)", now_snap().phase == DM_CONTACT_CANCELLED);
    dm_touch_set_from(&(dm_touch){0, 0.640625f, 0.5f}, 1, DM_CONTACT_IOS);
    rd(3 * S + 32 * MS);
    lift(); rd(3 * S + 48 * MS);
    check("drag: the release ends it without a Tap", (g[0].type == COMPLETE || g[0].type == SWIPE) && !ctx_has(drag_ctx, TAP));
    check("drag: no Press ever appeared in it", !ctx_has(drag_ctx, PRESS));
    rd(3 * S + 64 * MS);

    // ---- 3b. A hold: one contact, opened late, that reaches the game's own Press and ends without a Tap -------
    // This is what the overlay publishes when a single finger has stayed still for 0.5 s (DmGamepad.m holdTick). The
    // contact is opened only then, so nothing exists while the finger is merely resting on the glass.
    down(0.5f, 0.5f); rd(5 * S);
    int64_t hold_ctx = ctx_top();
    check("hold: the contact opens at the cursor (640,360)", newest_is(TOUCH, 640, 360));
    usleep(560 * 1000);                       // the title's own 0.5 s Press clock, measured from that contact
    rd(5 * S + 600 * MS);
    check("hold: holding it past 0.5 s is the game's Press", newest_is(PRESS, 640, 360));
    check("hold: and the contact snapshot agrees", now_snap().phase == DM_CONTACT_PRESS);
    lift(); rd(5 * S + 620 * MS);
    check("hold: its release is Complete, not a Tap", g[0].type == COMPLETE && !ctx_has(hold_ctx, TAP));
    rd(5 * S + 640 * MS);

    // ---- 3c. A hold that is cancelled (focus loss, a moved finger, a second finger) never becomes a Tap -------
    down(0.4f, 0.4f); rd(5 * S + 800 * MS);
    dm_touch_cancel_from(DM_CONTACT_IOS); rd(5 * S + 816 * MS);
    check("hold cancel: it is reported as CANCEL with no point", gn > 0 && g[0].type == CANCEL && g[0].npt == 0);
    check("hold cancel: the contact is left CANCELLED", now_snap().phase == DM_CONTACT_CANCELLED);
    rd(5 * S + 840 * MS);

    // ---- 4. A cancelled drag is cancelled, never lifted ---------------------------------------------------
    down(0.5f, 0.5f); rd(4 * S);
    dm_touch_set_from(&(dm_touch){0, 0.6f, 0.5f}, 1, DM_CONTACT_IOS); rd(4 * S + 16 * MS);
    dm_touch_cancel_from(DM_CONTACT_IOS); rd(4 * S + 32 * MS);
    check("cancel: it is reported as CANCEL with no point", gn > 0 && g[0].type == CANCEL && g[0].npt == 0);
    check("cancel: the contact is left CANCELLED", now_snap().phase == DM_CONTACT_CANCELLED);
    check("cancel: no Tap was produced anywhere in it", !ctx_has(ctx_top(), TAP) && !ctx_has(ctx_top() - 1, TAP));
    rd(4 * S + 48 * MS);

    // ---- 5. After all that, a tap still clicks exactly once, at the cursor --------------------------------
    tap(0.25f, 0.75f); rd(5 * S);
    int64_t back_ctx = ctx_top();
    check("resume: a tap opens at the cursor (320,540)", newest_is(TOUCH, 320, 540));
    check("resume: and carries IsNewTouch, so it is not merged with anything before it", g[0].attr == NEW);
    rd(5 * S + 16 * MS);
    check("resume: its release clicks at (320,540)", newest_is(TAP, 320, 540));
    check("resume: exactly one Tap in that contact", ctx_has(back_ctx, TAP) && g[0].type == TAP);
    rd(5 * S + 33 * MS);

    // ---- 6. Two taps in a row are two Taps, and the game owns the double-tap decision ---------------------
    // The overlay does not merge them: each is its own contact, and the recognizer's 0.35 s rule decides whether the
    // pair is a double tap - the same rule a physical double tap went through before this mode existed.
    tap(0.5f, 0.5f); rd(6 * S);
    int64_t first_ctx = ctx_top();
    rd(6 * S + 16 * MS);
    check("double: the first tap completes as a Tap", newest_is(TAP, 640, 360) && !(g[0].attr & DOUBLE));
    rd(6 * S + 33 * MS);
    tap(0.5f, 0.5f); rd(6 * S + 100 * MS);
    rd(6 * S + 116 * MS);
    check("double: the second tap is a Tap in its own contact", newest_is(TAP, 640, 360) && ctx_top() != first_ctx);
    check("double: and it carries the double-tap attribute the game reads", (g[0].attr & DOUBLE) != 0);
    rd(6 * S + 133 * MS);

    // ---- 7. The hover coordinate and the click coordinate are the same conversion --------------------------
    // In this build a Tap stores its gesture point as the pointer (0x74c238) and the iOS handoff stores
    // dm_panel_point() of the cursor. If those two conversions ever disagreed, one frame would hold two different
    // positions for one point; this pins them together, edges included.
    const float pts[] = {0.f, 0.25f, 0.5f, 0.75f, 0.999f, 1.f};
    int agree = 1;
    for (unsigned i = 0; i < sizeof pts / sizeof *pts; i++) {
        int px, py; dm_panel_point(pts[i], pts[i], &px, &py);
        tap(pts[i], pts[i]);
        rd(7 * S + (uint64_t)i * 100 * MS);
        if (!newest_is(TOUCH, px, py)) {
            agree = 0;
            printf("  published %.3f → gesture (%d,%d), dm_panel_point (%d,%d)\n", pts[i], g[0].x, g[0].y, px, py);
        }
        // The game reads every frame: the release must be seen (and closed) before the next contact begins, or the
        // recognizer would treat the new point as a Pan of the old one - the rule it has always had.
        rd(7 * S + (uint64_t)i * 100 * MS + 16 * MS);
        if (!newest_is(TAP, px, py)) { agree = 0; printf("  tap at %.3f did not click at (%d,%d)\n", pts[i], px, py); }
        rd(7 * S + (uint64_t)i * 100 * MS + 33 * MS);
    }
    check("frame: the touch layer and the pointer handoff convert a position identically", agree);

    // ---- 8. The host layer itself is unchanged for every other input path --------------------------------
    // A still contact held over half a second is still promoted the way the title's own policies expect; this mode
    // simply never publishes one, which is why section 2 above can stay silent for as long as a finger rests.
    down(0.5f, 0.5f); rd(8 * S);
    usleep(560 * 1000);                                     // the snapshot uses the monotonic clock, as the title does
    check("host: a still contact still reaches PRESS after 0.5 s (unchanged for other modes)", now_snap().phase == DM_CONTACT_PRESS);
    dm_touch_hold_tap(1);                                   // the shop's own request
    int64_t shop_ctx = ctx_top();
    rd(8 * S + 600 * MS);
    check("host: with the hold-tap request it stays a Touch (unchanged)", !ctx_has(shop_ctx, PRESS));
    lift(); rd(8 * S + 616 * MS);
    check("host: and its release is the Tap the game buys with (unchanged)", newest_is(TAP, 640, 360));
    dm_touch_hold_tap(0);

    printf("virtual trackpad input audit: %d checks, %d failed\n", cases, fails);
    return fails != 0;
}
