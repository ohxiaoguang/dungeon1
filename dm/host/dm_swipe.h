// SPDX-License-Identifier: MIT
// A two-finger swipe as one synthetic game contact, shared by the two front ends that can produce one: the iOS
// virtual trackpad (DmGamepad.m, where the fingers are UITouches) and the Mac window (front_mac.m, where the gesture
// arrives as scrollWheel:). Each front end only *collects* a gesture; this header owns what the swipe does to the
// contact, so both platforms produce the same thing.
//
// Why a contact at all: this game's lists and the torch are dragged with a touch that starts somewhere and then moves
// (hle_touch.c turns that into Touch then Pan; the title's UI follows the touch point). It reads no mouse - no
// InitializeMouse / GetMouseState import - so the Switch Mouse HID wheel is not a scroll channel for it, and a swipe
// has to become exactly that: one contact, at the pointer, that follows the fingers. The contact is always at the
// pointer, never at the fingers, so the game acts on what the player is pointing at.
//
// The Mac side has no "finger down/up" to borrow, so the caller brackets the gesture (NSEvent phase, or the first
// event when the device reports none) and the contact ends when the gesture ends, when the fingers are gone for
// DM_SWIPE_IDLE_NS, or when the front end loses focus. Inertia (momentumPhase) is never fed to the game: the fingers
// are off the glass by then, and a contact that keeps moving after the hand left would drag the item further.
#pragma once
#include <math.h>
#include <stdint.h>
#include <time.h>
#include "dm_input.h"

// Screen points of contact travel per point of finger travel. 1:1 is what a finger drag does on the same picture, so
// a swipe on a trackpad covers the distance a finger would have covered on the glass.
#define DM_SWIPE_GAIN 1.0f
// No event for this long ends the contact. Only the phase-less case needs it (a wheel, or a trackpad whose gesture
// events never report an end); a trackpad with phases ends on NSEventPhaseEnded long before this.
#define DM_SWIPE_IDLE_NS 300000000ull

typedef struct {
    int active;
    uint64_t last_ns;
    float x, y;        // normalized position of the synthetic contact (the pointer follows it on iOS)
    float travel_y;    // signed total, for diagnostics and tests
} dm_swipe;

// The same monotonic clock the touch layer's contact snapshot uses (front.h), so the idle test and the title's own
// 0.5 s hold measure time the same way.
static inline uint64_t dm_swipe_now_ns(void) {
    struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t);
    return (uint64_t)t.tv_sec * 1000000000ull + (uint64_t)t.tv_nsec;
}
// The contact stays on the picture: the last row/column of the panel is still a valid coordinate.
static inline float dm_swipe_clamp(float v) { return v < 0 ? 0 : v > 0.999f ? 0.999f : v; }

static inline void dm_swipe_begin(dm_swipe *s, uint64_t now, float nx, float ny) {
    s->active = 1; s->last_ns = now; s->x = dm_swipe_clamp(nx); s->y = dm_swipe_clamp(ny); s->travel_y = 0;
}
// -> 1 when the contact's position changed, with the new normalized position in *out_x / *out_y. The travel is in view
// points on the picture, so a swipe moves the contact across the same pixels the fingers moved on the screen, and on
// iOS the pointer (which is the contact's position) travels exactly that far.
static inline int dm_swipe_move(dm_swipe *s, uint64_t now, float dx, float dy, float picture_w, float picture_h,
                                float gain, float *out_x, float *out_y) {
    s->last_ns = now;
    if (!s->active || !(picture_w > 0 && picture_h > 0)) { *out_x = s->x; *out_y = s->y; return 0; }
    float nx = dm_swipe_clamp(s->x + gain * dx / picture_w);
    float ny = dm_swipe_clamp(s->y + gain * dy / picture_h);
    int moved = nx != s->x || ny != s->y;
    s->x = nx; s->y = ny; s->travel_y += gain * dy;
    *out_x = nx; *out_y = ny;
    return moved;
}
// The contact has been on screen without an event for too long: the caller must end it.
static inline int dm_swipe_idle(const dm_swipe *s, uint64_t now) {
    return s->active && now - s->last_ns >= DM_SWIPE_IDLE_NS;
}
static inline void dm_swipe_end(dm_swipe *s) { s->active = 0; }

// One axis of a scroll event, in "fingers moved" terms: positive is down (Y) or right (X), whichever way the user's
// natural-scrolling preference runs. NSEvent's isDirectionInvertedFromDevice is exactly that preference, and without
// this the swipe would drag the opposite way for half the users.
static inline float dm_swipe_component(double delta, int inverted) {
    return (float)(inverted ? delta : -delta);
}
