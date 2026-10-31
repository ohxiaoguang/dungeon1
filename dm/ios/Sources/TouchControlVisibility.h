// SPDX-License-Identifier: MIT
// The touch overlay's pure policy, in one place so it can be unit-tested without UIKit (dm/ios/tests).
// Visibility only for the two below: physical pad state and touch-to-game routing remain separate.
static inline int dm_touch_pad_visible(int enabled, int physical) { return enabled && !physical; }
static inline int dm_touch_right_visible(int enabled, int full) { return enabled && full; }
// The layout button's cycle, the same in handheld and docked mode: 2D (0) → 3D (1) → Tap (2) → 2D. Values are the ones
// DmPadLayout persists (DM_GAME_PAD_LAYOUT's numbers); anything unrecognised falls back to 3D, as an unset layout did.
static inline int dm_touch_next_layout(int layout) { return layout == 1 ? 2 : layout == 2 ? 0 : 1; }
