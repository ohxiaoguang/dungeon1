// Build-restricted, opt-in pointer-only experiment. No game input-mode or button
// state is written. In particular this does not claim native PC click semantics.
#include "hle.h"
#include "dd_pointer.h"
static void dd_pointer_impl(const uint64_t *regs) {
    (void)regs;
    static int enabled = -1, valid;
    static module_t *main_module;
    static pthread_t owner;
    static uint64_t seen;
    if (enabled < 0) {
        const char *e = getenv("DM_DD_MOUSE_POINTER");
        enabled = e && !strcmp(e, "1");
        if (!enabled) return;
        int sdk_ok = 0;
        for (int i = 0; i < g_nmod; i++) {
            module_t *m = &g_mod[i];
            if (!strcmp(m->name, "main") && !strcmp(m->build_id, "ff2bf22565188d11ea0981ee0e2b53ce")) main_module = m;
            if (!strcmp(m->name, "sdk") && !strcmp(m->build_id, "b33804825108340e4cad9d080a636a3f")) sdk_ok = 1;
        }
        valid = main_module && sdk_ok && main_module->size > 0x27e0898 &&
            gate_obs_present(OBS_DD_POINTER) && dm_mouse_enabled();
        // The gate instruction itself is checked by the rewriter; validate its
        // unchanged neighbours again against the actual mapped module.
        if (valid) valid = *(uint32_t *)(main_module->base + 0x8b5dbc) == 0x97fa53ad &&
                           *(uint32_t *)(main_module->base + 0x8b5dc4) == 0x9400c353;
        owner = pthread_self();
        LOG("DD pointer-only experiment: %s (left touch retained; right/wheel not bridged)", valid ? "enabled" : "REFUSED: build/gate/instructions/Mouse HID mismatch");
    }
    if (!enabled || !valid || !pthread_equal(owner, pthread_self())) return;
    dm_pointer_snapshot p;
    if (!dm_mouse_snapshot(&p)) return;
    uint8_t *b = main_module->base;
    uint32_t mode; memcpy(&mode, b + 0x27dee2c, sizeof mode);
    if (!dd_pointer_take(&seen, &p, mode, b[0x27dec24])) return;
    float xy[2] = {p.connected ? (float)p.x : -500, p.connected ? (float)p.y : -500};
    memcpy(b + 0x27e0890, xy, sizeof xy);
}
static void dd_pointer_poll(const uint64_t *regs) {
    static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
    pthread_mutex_lock(&lock); dd_pointer_impl(regs); pthread_mutex_unlock(&lock);
}
__attribute__((constructor)) static void dd_pointer_register(void) {
    gate_obs_set(OBS_DD_POINTER, dd_pointer_poll);
}
