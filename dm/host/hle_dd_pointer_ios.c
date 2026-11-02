// Build-restricted, opt-in pointer-only handoff for the iOS virtual trackpad. It is the iPhone/iPad counterpart of
// hle_dd_pointer_mac.c and writes the same two coordinates of the game's own pointer, nothing else: no click, no
// drag state, no button, no touch point.
//
// Why it exists: on this build the only instruction that stores the pointer (0x74c238) runs for a Tap, and a Tap is
// also what the game turns into a click. A trackpad therefore cannot hover through the touch/gesture path at all - a
// swipe is a Pan (no pointer write) and a Tap is a click by definition. The Mac bridge has the same problem and
// solves it the same way; this file only changes where the position comes from (the front-end cursor, dm_cursor_set,
// which the overlay moves with the finger's delta) and which switch enables it.
//
// It is off unless the player chose the virtual trackpad (DM_TOUCH_INPUT=trackpad), so the two other modes publish
// nothing here and keep the untouched touch behaviour. It is also refused unless the game's build, its gate and the
// gate's neighbours are the prepared ones, and unless the game still owns the pointer (dd_pointer.h: mode 0 and no
// controller) - the same terms as the Mac bridge. Validation is deliberately a copy of the Mac file's, not a shared
// helper: the Mac path is acceptance-tested as it stands, and a game with another prepared module must keep
// refusing both.
#include <TargetConditionals.h>
#if TARGET_OS_IPHONE
#include "hle.h"
#include "dd_pointer.h"
static void dd_cursor_impl(const uint64_t *regs) {
    (void)regs;
    static int enabled = -1, valid;
    static module_t *main_module;
    static pthread_t owner;
    static uint64_t seen;
    if (enabled < 0) {
        enabled = dm_touch_input_mode(getenv("DM_TOUCH_INPUT")) == DM_TOUCH_INPUT_TRACKPAD;
        if (!enabled) return;
        int sdk_ok = 0;
        for (int i = 0; i < g_nmod; i++) {
            module_t *m = &g_mod[i];
            if (!strcmp(m->name, "main") && !strcmp(m->build_id, "ff2bf22565188d11ea0981ee0e2b53ce")) main_module = m;
            if (!strcmp(m->name, "sdk") && !strcmp(m->build_id, "b33804825108340e4cad9d080a636a3f")) sdk_ok = 1;
        }
        // No cursor is required here: the player may touch the screen long after the game started, so validity
        // depends only on the module and the gate (the body below waits for the first published position).
        valid = main_module && sdk_ok && main_module->size > 0x27e0898 && gate_obs_present(OBS_DD_POINTER);
        // The gate instruction itself is checked by the rewriter; validate its unchanged neighbours again against
        // the actual mapped module.
        if (valid) valid = *(uint32_t *)(main_module->base + 0x8b5dbc) == 0x97fa53ad &&
                           *(uint32_t *)(main_module->base + 0x8b5dc4) == 0x9400c353;
        owner = pthread_self();
        LOG("DD pointer-only trackpad handoff: %s (left touch retained; click still the game's own Tap)", valid ? "enabled" : "REFUSED: build/gate/instructions mismatch");
    }
    if (!enabled || !valid || !pthread_equal(owner, pthread_self())) return;
    dm_pointer_snapshot p;
    if (!dm_cursor_snapshot(&p)) return;
    uint8_t *b = main_module->base;
    uint32_t mode; memcpy(&mode, b + 0x27dee2c, sizeof mode);
    if (!dd_pointer_take(&seen, &p, mode, b[0x27dec24])) return;
    float xy[2] = {p.connected ? (float)p.x : -500, p.connected ? (float)p.y : -500};
    memcpy(b + 0x27e0890, xy, sizeof xy);
}
static void dd_cursor_poll(const uint64_t *regs) {
    static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
    pthread_mutex_lock(&lock); dd_cursor_impl(regs); pthread_mutex_unlock(&lock);
}
__attribute__((constructor)) static void dd_cursor_register(void) {
    gate_obs_set(OBS_DD_POINTER, dd_cursor_poll);
}
#endif
