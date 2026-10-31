// Darkest Dungeon's optional pointer-only handoff policy. This is not a PC mouse
// event dispatcher: clicks/drags still use the game's existing Switch gestures.
#pragma once
#include "dm_input.h"
static inline int dd_pointer_take(uint64_t *seen, const dm_pointer_snapshot *p, uint32_t mode, int controller) {
    if (!p->revision || p->revision == *seen) return 0;
    *seen = p->revision; // consume even when a controller owns focus: never replay stale movement
    return mode == 0 && !controller;
}
