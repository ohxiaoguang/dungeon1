// SPDX-License-Identifier: MIT
// The virtual trackpad's gesture policy, in one place so it can be unit-tested without UIKit (dm/ios/tests).
// The mode itself is DM_TOUCH_INPUT (dm/host/dm_input.h lists its values); this header decides what a touch on the
// glass means, and the rule it exists for is that moving, clicking, holding and swiping are different intents:
//
//   · a finger that goes down publishes NOTHING. It cannot start a game contact, so it cannot pick up, drag, buy or
//     toggle anything just by being put down - the bug this mode was built to fix;
//   · a finger that stays inside the slop and comes up within the tap window is a tap: one contact at the cursor, down
//     and up in the same turn, which is the game's own Tap - the only thing this build turns into a click;
//   · a finger that leaves the slop only moves the cursor. Its release publishes nothing at all, and it can never
//     turn into a click or a hold;
//   · a finger held still past the hold window is a hold: only then is one contact put down, at the cursor, and it
//     stays down until the finger lifts. That gives the game its own Press (hold to toggle a skill, hold to buy, hold
//     to open the details) without ever creating the contact that used to grab an item on touch-down;
//   · two fingers are one swipe: as soon as their midpoint leaves the slop, one contact is opened at the cursor and
//     follows them. Pausing first changes nothing - it is the same contact, and the game treats both as a finger drag,
//     which is what its lists, the torch and a draggable item answer to;
//   · a third finger, a second finger during a hold, or a system cancel ends an open contact by CANCELLING it, never
//     by lifting it (a lift could arrive as the game's Tap, which is a click).
// Every state is reached from the previous one, so a gesture can never change its mind: once it is a tap candidate it
// can only become a click, a hold or nothing; once it is moving it cannot click or hold; once two fingers are down it
// can only swipe.
//
// The overlay calls these as UIKit delivers touches, plus dm_tp_hold() from a timer because nothing arrives while a
// finger is still. dm_trackpad_slop() converts the panel threshold below into the caller's units (DmGamepad.m works in
// view points), so the overlay and the recognizer agree on what "still" means.
#pragma once
#include <math.h>
#include <stdint.h>
#include <string.h>

// The recognizer (hle_touch.c) treats a contact as still until it has moved more than 8 panel pixels on either axis,
// and a still contact's release is a Tap - the only thing this build turns into a click. A stroke must therefore
// cross that threshold BEFORE it counts as movement, and the slop is 9 rather than 8 because a published position is
// truncated to whole panel pixels: a crossing right at 8 would publish exactly 8, which the recognizer does not count
// as movement. The comparison is per axis, as the recognizer's is.
#define DM_TRACKPAD_SLOP_PANEL 9.0f
static inline float dm_trackpad_slop(float picture_width) { return picture_width * DM_TRACKPAD_SLOP_PANEL / 1280.0f; }

// The game's own Press threshold is 0.5 s (hle_touch.c), so a hold is opened at 0.5 s of stillness and the game needs
// another 0.5 s on the contact it then sees: a full hold is about one second, which is the shortest that can produce
// the game's Press without publishing a contact earlier (and that earlier contact is exactly what used to grab items).
#define DM_TRACKPAD_HOLD_NS 500000000ull
// A tap is a release before that hold opens. It stays under the hold threshold so the two can never both apply.
#define DM_TRACKPAD_TAP_NS 450000000ull

// What the overlay must do. Every value is one publication at most; DM_TP_NONE means "the host hears nothing".
enum {
    DM_TP_NONE = 0,
    DM_TP_CURSOR,           // move the cursor by (dx, dy); no touch, no click
    DM_TP_CLICK,            // one contact at the cursor, down and up: the game's own Tap
    DM_TP_HOLD_DOWN,        // one contact at the cursor, held (a still finger past the hold window)
    DM_TP_HOLD_UP,          // that contact is lifted, the game deciding what its release means
    DM_TP_SWIPE_DOWN,       // one contact at the cursor (two fingers): the game's own touch drag
    DM_TP_SWIPE_MOVE,       // move by (dx, dy) and publish the contact at the new cursor
    DM_TP_SWIPE_UP,         // the swipe's contact is lifted
    DM_TP_CONTACT_CANCEL    // the open contact (hold or swipe) must be cancelled, never lifted
};

typedef enum {
    DM_TP_IDLE = 0,   // no finger
    DM_TP_SINGLE,     // one finger, still inside the slop: a tap candidate until the hold window closes
    DM_TP_MOVING,     // one finger, moving the cursor
    DM_TP_HOLDING,    // one finger still, past the hold window: the contact is down
    DM_TP_TWO,        // two fingers, still inside the slop
    DM_TP_SWIPE,      // two fingers, moving: one contact at the cursor follows them
    DM_TP_CANCELLED   // the gesture was cancelled: every finger still down is ignored until it lifts
} dm_tp_state;

// DM_TP_SWIPE publishes a contact because this is the only thing the game answers with. Its lists and the torch are
// dragged with a touch that starts somewhere and then moves (hle_touch.c: Touch then Pan, and the UI follows the touch
// point), and it reads no mouse at all - no InitializeMouse / GetMouseState / GetMouseStates import in main, asserted
// in dm/ios/tests/test_trackpad_policy.py - so the Switch Mouse HID wheel is not a channel for it. A swipe starts at
// the pointer, so the game acts on what the player points at, and over a draggable item it drags that item, exactly
// as a finger drag there does. There is no second, "deliberate drag" gesture: pausing before the movement produced
// the same contact and only made the player wait.

typedef struct {
    dm_tp_state state;
    int fingers;                       // fingers the gesture is following (a third cancels)
    uint64_t down_ns, hold_ns;         // when the single finger went down, when its contact was opened
    float down_x, down_y, last_x, last_y;     // the single finger: where it went down, where it was last read
    float pivot_x, pivot_y, last_x2, last_y2; // the two-finger midpoint: where the swipe began, last read
} dm_tp_gesture;

static inline void dm_tp_reset(dm_tp_gesture *g) { memset(g, 0, sizeof *g); }

// A finger (or another finger) went down. Never publishes anything by itself.
static inline int dm_tp_down(dm_tp_gesture *g, uint64_t now, int n, float x0, float y0, float x1, float y1) {
    if (n <= 0) { if (g->state == DM_TP_CANCELLED) dm_tp_reset(g); return DM_TP_NONE; }
    g->fingers = n;
    if (g->state == DM_TP_CANCELLED) return DM_TP_NONE;   // ignored until every finger has lifted
    if (n >= 3) {                                         // a third finger is never a gesture, and ends a contact safely
        int open = g->state == DM_TP_HOLDING || g->state == DM_TP_SWIPE;
        g->state = DM_TP_CANCELLED;
        return open ? DM_TP_CONTACT_CANCEL : DM_TP_NONE;
    }
    if (n == 2 && g->state == DM_TP_HOLDING) {            // a hold and two fingers never mix: the hold is cancelled
        g->state = DM_TP_CANCELLED;
        return DM_TP_CONTACT_CANCEL;
    }
    if (n == 2) {                                         // two fingers freeze the cursor and wait for the midpoint
        g->state = DM_TP_TWO;
        g->pivot_x = g->last_x2 = (x0 + x1) / 2;
        g->pivot_y = g->last_y2 = (y0 + y1) / 2;
        return DM_TP_NONE;
    }
    if (g->state == DM_TP_IDLE) {
        g->state = DM_TP_SINGLE;
        g->down_ns = now;
        g->down_x = g->last_x = x0;
        g->down_y = g->last_y = y0;
    }
    return DM_TP_NONE;
}

// A finger moved. `n` is how many are on the glass now; only the first two positions are read.
static inline int dm_tp_move(dm_tp_gesture *g, uint64_t now, int n, float x0, float y0, float x1, float y1,
                             float slop, float *dx, float *dy) {
    (void)now;
    *dx = *dy = 0;
    switch (g->state) {
    case DM_TP_SWIPE: {                                   // the game's own touch drag, at the pointer
        if (n < 2) return DM_TP_NONE;
        float cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
        *dx = cx - g->last_x2; *dy = cy - g->last_y2;
        g->last_x2 = cx; g->last_y2 = cy;
        return (*dx != 0 || *dy != 0) ? DM_TP_SWIPE_MOVE : DM_TP_NONE;
    }
    case DM_TP_HOLDING: {                                 // the contact is down: moving it would drag that item
        if (n != 1) return DM_TP_NONE;
        if (fmaxf(fabsf(x0 - g->last_x), fabsf(y0 - g->last_y)) <= slop) return DM_TP_NONE;
        g->state = DM_TP_CANCELLED;
        return DM_TP_CONTACT_CANCEL;
    }
    case DM_TP_SINGLE:
    case DM_TP_MOVING: {
        if (n != 1) return DM_TP_NONE;
        if (g->state == DM_TP_SINGLE) {
            if (fmaxf(fabsf(x0 - g->down_x), fabsf(y0 - g->down_y)) <= slop) return DM_TP_NONE;
            g->state = DM_TP_MOVING;
            *dx = x0 - g->down_x; *dy = y0 - g->down_y;   // the whole offset: no travel is lost at the crossing
        } else {
            *dx = x0 - g->last_x; *dy = y0 - g->last_y;
        }
        g->last_x = x0; g->last_y = y0;
        return DM_TP_CURSOR;
    }
    case DM_TP_TWO: {
        if (n < 2) return DM_TP_NONE;
        float cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
        if (fmaxf(fabsf(cx - g->pivot_x), fabsf(cy - g->pivot_y)) <= slop) return DM_TP_NONE;
        g->state = DM_TP_SWIPE;                           // one path, whether the fingers moved at once or after a pause
        *dx = cx - g->pivot_x; *dy = cy - g->pivot_y;
        g->last_x2 = cx; g->last_y2 = cy;
        return DM_TP_SWIPE_DOWN;                          // the down is at the cursor as it is now, before the move
    }
    default: return DM_TP_NONE;
    }
}

// The hold timer: nothing arrives while a finger is still, so the overlay asks once per touch-down whether the window
// has passed. A still single finger becomes the game's hold; anything else is left alone.
static inline int dm_tp_hold(dm_tp_gesture *g, uint64_t now) {
    if (g->state != DM_TP_SINGLE || g->fingers != 1) return DM_TP_NONE;
    if (now - g->down_ns < DM_TRACKPAD_HOLD_NS) return DM_TP_NONE;
    g->state = DM_TP_HOLDING;
    g->hold_ns = now;
    return DM_TP_HOLD_DOWN;
}

// A finger lifted. `left` is how many are still down afterwards.
static inline int dm_tp_up(dm_tp_gesture *g, uint64_t now, int left) {
    int action = DM_TP_NONE;
    if (g->state == DM_TP_SWIPE) action = DM_TP_SWIPE_UP;
    else if (g->state == DM_TP_HOLDING) {
        // Once the contact has been down for the game's own Press threshold its release is the game's to interpret
        // (the shop's hold-tap buys on the lift, a Press ends). Before that nothing has happened yet, and a lift could
        // still arrive as a Tap - a click nobody asked for - so it is cancelled instead.
        action = now - g->hold_ns >= DM_TRACKPAD_HOLD_NS ? DM_TP_HOLD_UP : DM_TP_CONTACT_CANCEL;
    } else if (g->state == DM_TP_SINGLE && now - g->down_ns <= DM_TRACKPAD_TAP_NS) action = DM_TP_CLICK;
    if (left > 0) { g->state = DM_TP_CANCELLED; g->fingers = left; }   // a finger left on the glass may not act
    else dm_tp_reset(g);
    return action;
}

// The gesture was cancelled (focus loss, a system gesture, the app going away). An open contact must be cancelled,
// not lifted: a lift could still arrive as the game's Tap, which is a click.
static inline int dm_tp_cancel(dm_tp_gesture *g) {
    int action = (g->state == DM_TP_HOLDING || g->state == DM_TP_SWIPE) ? DM_TP_CONTACT_CANCEL : DM_TP_NONE;
    g->state = DM_TP_CANCELLED;
    return action;
}

// The cursor stays on the picture: the last row/column of the panel is still a valid coordinate.
static inline float dm_trackpad_clamp(float v) { return v < 0 ? 0 : v > 0.999f ? 0.999f : v; }

// Where the arrow is drawn: the panel point the handoff writes into the game's pointer (dm_panel_point of the cursor,
// 1280x720) back into view points inside the picture rectangle. Both directions go through that same integer, so the
// tip sits on the exact point the game hit-tests; converting the normalized cursor straight to the screen instead
// would be up to one panel pixel off, which is the drift this avoids. The picture rectangle is passed in, so a
// letterboxed, rotated or resized window (Stage Manager) needs no other change.
static inline void dm_trackpad_arrow_tip(int px, int py, float picture_x, float picture_y,
                                         float picture_width, float picture_height, float *x, float *y) {
    if (!(picture_width > 0 && picture_height > 0)) { *x = picture_x; *y = picture_y; return; }
    *x = picture_x + (float)px * picture_width / 1280.0f;
    *y = picture_y + (float)py * picture_height / 720.0f;
}
