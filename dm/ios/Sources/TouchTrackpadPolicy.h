// SPDX-License-Identifier: MIT
// The virtual trackpad's gesture policy, in one place so it can be unit-tested without UIKit (dm/ios/tests).
// The mode itself is DM_TOUCH_INPUT (dm/host/dm_input.h lists its values); this header decides what a touch on the
// glass means, and the rule it exists for is that moving, clicking and dragging are different intents:
//
//   · a finger that goes down publishes NOTHING. It cannot start a game contact, so it cannot pick up, drag, buy or
//     toggle anything by being put down, however long it stays;
//   · a finger that stays inside the slop and comes up quickly is a tap: one contact at the cursor, down and up in
//     the same turn, which is the game's own Tap - the only thing this build turns into a click;
//   · a finger that leaves the slop only moves the cursor. Its release publishes nothing at all;
//   · a finger held still for longer than a tap publishes nothing either, even when it comes up: a long press is
//     inert by design, because the game turns a still contact into Press (hold to toggle, hold to buy, hold to open);
//   · two fingers that pause for DM_TRACKPAD_DRAG_HOLD and then move are a drag: the contact starts at the cursor
//     (the item under the pointer) and follows it;
//   · two fingers that move before the pause are a swipe: the same kind of contact, at the same place, but this is the
//     gesture the game's own lists and the torch answer to. Both are one contact that follows the fingers and neither
//     is a click, and a gesture that has become one of them can never become the other or a tap.
// Every state is reached from the previous one, so a gesture can never change its mind: once it is a tap candidate
// it can only become a click or nothing; once it is moving it cannot click; once it is two-finger pending it can
// only become a scroll (inert) or a drag, never a click.
//
// The overlay calls these as UIKit delivers touches. dm_trackpad_slop() converts the panel threshold below into the
// caller's units (DmGamepad.m works in view points), so the overlay and the recognizer agree on what "still" means.
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

// How long two fingers must stay put before moving them counts as a drag, and how long a single finger may stay down
// and still count as a tap. The tap window is under the recognizer's 0.5 s Press threshold on purpose: a contact the
// game would have promoted to Press must never be manufactured by a release.
#define DM_TRACKPAD_DRAG_HOLD_NS 300000000ull
#define DM_TRACKPAD_TAP_NS 450000000ull

// What the overlay must do. Every value is one publication at most; DM_TP_NONE means "the host hears nothing".
enum {
    DM_TP_NONE = 0,
    DM_TP_CURSOR,           // move the cursor by (dx, dy); no touch, no click
    DM_TP_CLICK,            // one contact at the cursor, down and up: the game's own Tap
    DM_TP_DRAG_DOWN,        // contact down at the cursor (a two-finger drag that served its pause)
    DM_TP_DRAG_MOVE,        // move by (dx, dy) and publish the contact at the new cursor
    DM_TP_DRAG_UP,          // the drag's contact is lifted
    DM_TP_SWIPE_DOWN,       // contact down at the cursor (a two-finger swipe, the game's own touch drag)
    DM_TP_SWIPE_MOVE,       // move by (dx, dy) and publish the contact at the new cursor
    DM_TP_SWIPE_UP,         // the swipe's contact is lifted
    DM_TP_CONTACT_CANCEL    // the open contact (drag or swipe) must be cancelled, never lifted
};

typedef enum {
    DM_TP_IDLE = 0,   // no finger
    DM_TP_SINGLE,     // one finger, still inside the slop: a tap candidate
    DM_TP_MOVING,     // one finger, moving the cursor
    DM_TP_TWO,        // two fingers, still inside the slop: the pause decides scroll or drag
    DM_TP_SCROLL,     // two fingers moving before the pause: inert (see below)
    DM_TP_DRAG,       // two fingers, past the pause: the contact is down at the cursor
    DM_TP_CANCELLED   // the gesture was cancelled: every finger still down is ignored until it lifts
} dm_tp_state;

// DM_TP_SCROLL is the two-finger swipe, and it publishes a contact. This game's lists and the torch are dragged with
// a touch that starts somewhere and then moves (hle_touch.c: Touch then Pan, and the UI follows the touch point); it
// reads no mouse at all - no InitializeMouse / GetMouseState / GetMouseStates import in main, asserted in
// dm/ios/tests/test_trackpad_policy.py - so the Switch Mouse HID wheel is not a channel for it. A swipe is therefore
// the same contact a drag publishes, only reached by a different gesture, and it starts at the pointer so the game
// acts on what the player points at. Consequence, accepted: a swipe that starts on a draggable item drags it, which
// is what a finger drag does there too; the mode's protection is that a single finger can no longer start one.

typedef struct {
    dm_tp_state state;
    int fingers;                       // fingers the gesture is following (a third cancels)
    uint64_t down_ns, two_ns;          // when the single finger went down, when the second joined
    float down_x, down_y, last_x, last_y;    // the single finger: where it went down, where it was last read
    float pivot_x, pivot_y, last_x2, last_y2; // the two-finger centroid: at the pause's start, last read
} dm_tp_gesture;

static inline void dm_tp_reset(dm_tp_gesture *g) { memset(g, 0, sizeof *g); }

// A finger (or another finger) went down. Never publishes anything by itself.
static inline int dm_tp_down(dm_tp_gesture *g, uint64_t now, int n, float x0, float y0, float x1, float y1) {
    if (n <= 0) { if (g->state == DM_TP_CANCELLED) dm_tp_reset(g); return DM_TP_NONE; }
    g->fingers = n;
    if (g->state == DM_TP_CANCELLED) return DM_TP_NONE;   // ignored until every finger has lifted
    if (n >= 3) {                                         // a third finger is never a gesture, and ends a contact safely
        int open = g->state == DM_TP_DRAG || g->state == DM_TP_SCROLL;
        g->state = DM_TP_CANCELLED;
        return open ? DM_TP_CONTACT_CANCEL : DM_TP_NONE;
    }
    if (g->state == DM_TP_DRAG) return DM_TP_NONE;        // a finger joining a drag changes nothing about it
    if (n == 2) {                                         // the second finger freezes the cursor and starts the pause
        g->state = DM_TP_TWO;
        g->two_ns = now;
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
    *dx = *dy = 0;
    switch (g->state) {
    case DM_TP_DRAG: {
        if (n < 2) return DM_TP_NONE;                     // one lifted: the release ends the drag, nothing moves it
        float cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
        *dx = cx - g->last_x2; *dy = cy - g->last_y2;
        g->last_x2 = cx; g->last_y2 = cy;
        return (*dx != 0 || *dy != 0) ? DM_TP_DRAG_MOVE : DM_TP_NONE;
    }
    case DM_TP_SCROLL: {                                  // the game's own touch drag, at the pointer
        if (n < 2) return DM_TP_NONE;
        float cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
        *dx = cx - g->last_x2; *dy = cy - g->last_y2;
        g->last_x2 = cx; g->last_y2 = cy;
        return (*dx != 0 || *dy != 0) ? DM_TP_SWIPE_MOVE : DM_TP_NONE;
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
        if (now - g->two_ns < DM_TRACKPAD_DRAG_HOLD_NS) {  // moved before the pause: a swipe, never a drag
            g->state = DM_TP_SCROLL;
            *dx = cx - g->pivot_x; *dy = cy - g->pivot_y;
            g->last_x2 = cx; g->last_y2 = cy;
            return DM_TP_SWIPE_DOWN;
        }
        g->state = DM_TP_DRAG;
        *dx = cx - g->pivot_x; *dy = cy - g->pivot_y;
        g->last_x2 = cx; g->last_y2 = cy;
        return DM_TP_DRAG_DOWN;                           // the down is at the cursor as it is now, before the move
    }
    default: return DM_TP_NONE;
    }
}

// A finger lifted. `left` is how many are still down afterwards. Only DM_TP_SINGLE can become a click, and only
// inside the tap window: everything else ends without publishing.
static inline int dm_tp_up(dm_tp_gesture *g, uint64_t now, int left) {
    int action = DM_TP_NONE;
    if (g->state == DM_TP_DRAG) action = DM_TP_DRAG_UP;
    else if (g->state == DM_TP_SCROLL) action = DM_TP_SWIPE_UP;
    else if (g->state == DM_TP_SINGLE && now - g->down_ns <= DM_TRACKPAD_TAP_NS) action = DM_TP_CLICK;
    if (left > 0) { g->state = DM_TP_CANCELLED; g->fingers = left; }   // a finger left on the glass may not act
    else dm_tp_reset(g);
    return action;
}

// The gesture was cancelled (focus loss, a system gesture, the app going away). An open contact must be cancelled,
// not lifted: a lift could still arrive as the game's Tap, which is a click.
static inline int dm_tp_cancel(dm_tp_gesture *g) {
    int action = (g->state == DM_TP_DRAG || g->state == DM_TP_SCROLL) ? DM_TP_CONTACT_CANCEL : DM_TP_NONE;
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
