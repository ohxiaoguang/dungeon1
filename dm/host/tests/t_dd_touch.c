// Policy-level test for the Darkest Dungeon touch adapter (dm/host/hle_dd_touch.c
// built with DM_DD_TOUCH_TEST). It drives the same gates the guest executes, in
// the order the guest executes them, against a fake module image, a fake
// action-wrapper at 0xe39fe0 and a fake action class:
//
//   contact snapshot (hle_touch.c)  ->  frame gate (0x8b5dac)
//   the game's click: wrapper 0xe39fe0 -> eligibility byte -> action vtable +0x30
//                     -> the toggle entry, which re-enters the filter (0xe3b5a0)
//
// The wrapper stub is real ARM64 code with the same loads and branch as the
// game's (ldr [x0,#0x10]; ldrb [x8,#0x12d]; cmp #1; b.ne ret; ldr [x0,#0x40];
// ldr [x0,#0x50]; ldr w [x0,#0x58]; ldr [action]; ldr [vtable,#0x30]; blr), so a
// replay the adapter sends through the wrapper is refused by the same check a
// real locked/withdrawn skill takes. The action class is fake: it counts entries,
// re-enters the filter as the gate does, and can refuse the change internally
// (a locked skill or a full selection), while the action vtable's own copy
// (+0x10) and release (+0x28) slots behave like the game's pair.
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <stdint.h>
#include <time.h>
#include <unistd.h>
#include <sys/mman.h>
#include "dm.h"
#include "front.h"

module_t g_mod[MAX_MOD];
int g_nmod;
void gate_obs_set(int id, void (*fn)(const uint64_t *)) { (void)id; (void)fn; }
static int obs_missing = -1;   // test: pretend the prepared module has no gate for this id
int gate_obs_present(int id) { return id != obs_missing; }
void gate_filter_set(int id, int (*fn)(const uint64_t *)) { (void)id; (void)fn; }
int gate_filter_present(int id, uint64_t off) { (void)id; (void)off; return 1; }

void dd_test_init(uintptr_t base);
void dd_test_frame(void);
int dd_test_holds(void);
int dd_test_filter(uintptr_t action, uintptr_t hero, uint32_t skill);
void dd_test_panel(uintptr_t panel);
void dd_test_enable(int on);
void dd_test_camp(int on);
void dd_test_shop(int on);
int dd_test_shop_filter(uintptr_t action);
void dd_test_upgrade(int on);
int dd_test_unlock(uint32_t kind, uint32_t id);
int dd_test_upgrade_tree(uint32_t kind, uint32_t id);
void dd_test_upgrade_key(uint32_t kind, uint32_t id);
int dd_test_upgrade_filter(void);
void dd_test_upgrade_rows(void);
uint64_t dd_test_upgrade_live(void);
uint64_t dd_test_upgrade_generation(void);
void dd_test_shop_build(uintptr_t binding);
uint64_t dd_test_tap_generation(void);
uint64_t dd_test_shop_live(void);
void dd_test_roster(int on);
void dd_test_roster_click(uintptr_t elem, uintptr_t fp);
int dd_test_validate(void);
void dd_test_shop_update(uintptr_t elem, uintptr_t fp);
int dd_test_probe_ok(void);
int dd_test_probe_lines(void);
int dd_test_probe_rows(void);
int dd_test_probe_requested(void);
void dd_test_probe(int on);
void dd_test_probe_frame(uint64_t f);
int dd_test_valid(void);
int dd_test_ios(void);

// The recognizer (hle_touch.c) as the guest's poll reads it.
int gesture_fill(void *out, int n, uint64_t now_ns);
typedef struct { int64_t samp, ctx; int32_t type, dir, x, y, dx, dy; float vx, vy; uint32_t attr; float scale, rot; int32_t npt, pt[4][2]; } gesture_state;
enum { GT_TOUCH = 3, GT_PRESS = 4, GT_TAP = 5 };

enum { IMG_LEN = 0x27e1000 };          // the adapter reads up to main+0x27e0898
static uint8_t *img;
static uintptr_t action_obj, camp_obj, hero_val = 0x1122334455ull, panel_val, skill_val = 3;
static int fails, cases;
static int entries, changed, refused, clones, releases;   // the fake native side
static int camp_entries, camp_changed, camp_clones, camp_releases;   // the camping grid's class
static int native_refuses;                                // a locked skill / full selection

static void chk(const char *what, int ok) {
    cases++;
    if (!ok) { fails++; printf("FAIL %s\n", what); } else printf("ok   %s\n", what);
}
static void put32(uintptr_t off, uint32_t w) { memcpy(img + off, &w, sizeof w); }
static void down(float x, float y) { dm_touch t = {0, x, y}; dm_touch_set_from(&t, 1, DM_CONTACT_IOS); }
static void up(void) { dm_touch_set_from(NULL, 0, DM_CONTACT_IOS); }
static void hold_ms(int ms) { usleep((useconds_t)ms * 1000); }
// The recognizer's history is process-wide: bring it back to Idle between
// scenarios so a contact starts as a new gesture.
static void gesture_idle(void) {
    gesture_state t[4];
    up();
    for (int i = 0; i < 3; i++) { int n = gesture_fill(t, 4, dm_touch_now_ns()); if (n && t[0].type == 0) break; }
}
static void eligible(int on) { ((uint8_t *)panel_val)[0x12d] = (uint8_t)on; }
static void panel_state(uint32_t st) { *(uint32_t *)(panel_val + 0x2c0) = st; }

// The action class's own slots (the game's are 0xe3b520 / 0xe3b590 / 0xe3b5a0).
static uintptr_t fake_clone(uintptr_t action) {
    uintptr_t *p = malloc(2 * sizeof(uintptr_t));
    p[0] = *(uintptr_t *)action; p[1] = *(uintptr_t *)(action + 8);
    clones++;
    return (uintptr_t)p;
}
static void fake_release(uintptr_t action) { releases++; free((void *)action); }
static void fake_toggle(uintptr_t action, uintptr_t *hero, uint32_t *skill) {
    entries++;                               // the toggle's first instruction is the filter gate
    if (dd_test_filter(action, *hero, *skill)) {
        if (native_refuses) refused++; else changed++;
    }
}
// The game's own click: the wrapper enters the action only when eligible.
static void game_click(void) {
    uintptr_t w[12] = {0};
    w[0] = (uintptr_t)img + 0x11956b8; w[2] = panel_val; w[8] = action_obj;
    w[10] = hero_val; *(uint32_t *)&w[11] = skill_val;
    ((void (*)(void *))((uintptr_t)img + 0xe39fe0))(w);
}

// The camping grid's action class (the game's is 0xe3a650 / 0xe3a6c0 / 0xe3a6d0 at
// vtable 0x11955b8). The same wrapper object and the same filter serve both grids.
static uintptr_t camp_clone(uintptr_t action) {
    uintptr_t *p = malloc(2 * sizeof(uintptr_t));
    p[0] = *(uintptr_t *)action; p[1] = *(uintptr_t *)(action + 8);
    camp_clones++;
    return (uintptr_t)p;
}
static void camp_release(uintptr_t action) { camp_releases++; free((void *)action); }
static void camp_toggle(uintptr_t action, uintptr_t *hero, uint32_t *skill) {
    camp_entries++;
    if (dd_test_filter(action, *hero, *skill)) camp_changed++;
}
static void game_camp_click(void) {
    uintptr_t w[12] = {0};
    w[0] = (uintptr_t)img + 0x11956b8; w[2] = panel_val; w[8] = camp_obj;
    w[10] = hero_val; *(uint32_t *)&w[11] = skill_val;
    ((void (*)(void *))((uintptr_t)img + 0xe39fe0))(w);
}

// The Nomad merchandise wrapper class (the game's vtables are 0x11933a8 /
// 0x1193428, operator() 0xe18410 / 0xe181f0, purchase callback vtable 0x117a678).
// The stub at img+0xe18410 is real ARM64 with the game's own shape: the patched
// entry runs the filter gate first (gate_shop, as the host's gate patch does),
// skips the body when refused, then chooses the bound callable at +0x70 and
// calls its vtable +0x30 with a pointer to the parameter word. The purchase
// callback counts calls; the price/stock/confirm decisions belong to the game.
//
// The click is modelled as the frame's action queue does it: a fresh deep copy
// of the control's std::function per click, the entry call, then the entry is
// destroyed and poisoned (main 0x8b5e9c..0x8b5e1c). The adapter must never keep
// any of it.
static uintptr_t shop_obj, purchase_obj;
static int shop_purchases, shop_gate_calls, shop_gate_allows;
static int gate_shop(uintptr_t action) {
    shop_gate_calls++;
    int allow = dd_test_shop_filter(action);
    if (allow) shop_gate_allows++;
    return allow;
}
static void fake_purchase(uintptr_t lambda, uint32_t *slot) {
    (void)lambda; (void)slot;        // the game's own price/stock/confirm decisions
    shop_purchases++;
}
// The patched entry (img+0xe18410 tail-jumps here): the host's gate runs first
// and a refusal ends the call, then the wrapper's own shape decides the bound
// callable (+0x70, or +0xd0 when the mode byte at +0x300 is 1) and calls its
// vtable +0x30 with a pointer to the parameter word copied from +0x304.
static void fake_entry_patched(uintptr_t obj) {
    if (!gate_shop(obj)) return;
    uint8_t *o = (uint8_t *)obj;
    uintptr_t callable = *(uintptr_t *)(o + (*(volatile uint8_t *)(o + 0x300) == 1 ? 0xd0 : 0x70));
    if (!callable) return;
    uint32_t param = *(uint32_t *)(o + 0x304);
    uintptr_t fn = *(uintptr_t *)(*(uintptr_t *)callable + 0x30);   // the callable's vtable +0x30
    ((void (*)(uintptr_t, uint32_t *))fn)(callable, &param);
}
// The command-vector drain path: the game's control hands a copy of its
// std::function to the frame's action queue, the drain calls the entry, and the
// entry is destroyed right afterwards (main 0x8b5e9c..0x8b5e1c); the next frame
// rebuilds it. The fixture reproduces that: a fresh deep copy per click,
// destroyed and poisoned when the call returns, so an adapter that kept a game
// pointer would read poison, not the live control.
// Town roster queue fixture (adapter 0x73bcc0 path): the game's push_back is
// replaced by a stub that clones the details function into the queue, exactly
// as 0x717370 does (inline copy, __f_ = the entry). The primary entry is put in
// the queue by the test to model the click that 0x73b6d0 just enqueued.
static int roster_pushes, roster_details_calls, roster_primary_calls;
static uintptr_t fake_push(uintptr_t queue, uintptr_t fn) {
    (void)queue;
    uintptr_t end = *(uintptr_t *)(img + 0x257e538);
    uintptr_t *e = (uintptr_t *)end;
    e[0] = *(uintptr_t *)fn; e[1] = *(uintptr_t *)(fn + 8);
    *(uintptr_t *)(end + 0x20) = end;
    *(uintptr_t *)(img + 0x257e538) = end + 0x30;
    roster_pushes++;
    return end + 0x30;
}
static void fake_roster_primary(uintptr_t lambda) { (void)lambda; roster_primary_calls++; }
static void fake_roster_details(uintptr_t lambda) { (void)lambda; roster_details_calls++; }
static uint8_t qobj[0x310], qlam[0x50];
static void game_shop_click(void) {
    uintptr_t vt = *(uintptr_t *)shop_obj;
    if (!vt) return;   // a destroyed control cannot dispatch
    memset(qobj, 0, sizeof qobj); memset(qlam, 0, sizeof qlam);
    uintptr_t *ol = *(uintptr_t **)(shop_obj + 0x70);
    uintptr_t *nl = (uintptr_t *)qlam;
    nl[0] = ol[0]; nl[2] = ol[2]; nl[3] = ol[3];     // vtable and the shared captures
    uintptr_t *q = (uintptr_t *)qobj;
    q[0] = vt;
    q[0x70 / 8] = (uintptr_t)nl;
    q[0x300 / 8] = *(uintptr_t *)(shop_obj + 0x300);
    *(uint32_t *)((uint8_t *)q + 0x304) = *(uint32_t *)(shop_obj + 0x304);
    ((void (*)(uintptr_t))(*(uintptr_t *)(vt + 0x30)))((uintptr_t)q);   // the drain's call
    memset(qobj, 0xAA, sizeof qobj); memset(qlam, 0xAA, sizeof qlam);    // the drain's destroying destructor
}

int main(void) {
    setvbuf(stdout, NULL, _IONBF, 0);
    // The fake image: one page of real wrapper code, and the action's vtable.
    img = mmap(NULL, IMG_LEN, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANON, -1, 0);
    uintptr_t *act = calloc(2, sizeof(uintptr_t));
    uint8_t *panel = calloc(0x2e0, 1);
    if (img == MAP_FAILED || !act || !panel) { printf("allocation failed\n"); return 1; }
    panel_val = (uintptr_t)panel; action_obj = (uintptr_t)act;
    *(uintptr_t *)panel = (uintptr_t)img + 0x11946c0;   // CharacterDisplay vtable
    *(uintptr_t *)(panel + 0x120) = hero_val; panel_state(1); eligible(1);
    act[0] = (uintptr_t)img + 0x1195228;   // DD_SKILL_VT
    act[1] = panel_val;                    // the captured CharacterDisplay

    static const uint32_t stub[] = {   // 0xe39fe0, the wrapper's own checks and call
        0xf81e0ffe, 0xf9400808, 0x3944b508, 0x7100051f, 0x54000181, 0xf9402009,
        0xf9402801, 0xf9000be1, 0xb9405801, 0xb9001be1, 0xaa0903e0, 0xf940012a,
        0xf940194a, 0x910043e1, 0x910063e2, 0xd63f0140, 0xf84207fe, 0xd65f03c0,
    };
    memcpy(img + 0xe39fe0, stub, sizeof stub);
    uintptr_t vt = (uintptr_t)img + 0x1195228;   // the fake action vtable
    *(uintptr_t *)(vt + 0x10) = (uintptr_t)fake_clone;
    *(uintptr_t *)(vt + 0x28) = (uintptr_t)fake_release;
    *(uintptr_t *)(vt + 0x30) = (uintptr_t)fake_toggle;
    long pg = sysconf(_SC_PAGESIZE);
    uintptr_t lo = ((uintptr_t)img + 0xe39fe0) & ~(uintptr_t)(pg - 1);
    if (mprotect((void *)lo, (size_t)pg, PROT_READ | PROT_EXEC)) { printf("mprotect failed\n"); return 1; }

    dm_touch_policy_activate(1);
    dd_test_init((uintptr_t)img);

    // 0. The wrapper itself: eligible runs the action, not eligible does not. No
    //    contact is published yet, so the adapter must not touch either.
    game_click();
    chk("wrapper: an eligible click reaches the action", entries == 1 && changed == 1);
    eligible(0); game_click();
    chk("wrapper: an ineligible click never reaches the action", entries == 1 && changed == 1);
    eligible(1);
    entries = changed = 0;

    // 1. A short tap: the game's click is withheld, the capture is released, and
    //    the lift click does not run either.
    down(0.5f, 0.5f); dd_test_frame();
    game_click();
    chk("tap: the game's click is withheld", changed == 0 && entries == 1);
    chk("tap: the click was captured as an owned copy", dd_test_holds() && clones == 1);
    up(); dd_test_frame();
    chk("tap: the capture was released at lift", !dd_test_holds() && releases == 1);
    game_click();
    chk("tap: no click on lift", changed == 0 && entries == 2);

    // 2. Hold, the game's click arrives on touch-down: withheld, then replayed
    //    once at 0.5 s through the wrapper; no second call on lift.
    down(0.4f, 0.4f); dd_test_frame(); game_click();
    chk("hold: click at touch-down is withheld", changed == 0 && entries == 3);
    hold_ms(600); dd_test_frame();
    chk("hold: the original wrapper ran the toggle once at 0.5 s", changed == 1 && entries == 4);
    chk("hold: the replays's copy was released after the call", !dd_test_holds() && releases == 2);
    game_click();
    chk("hold: a second click during the hold is withheld", changed == 1);
    up(); dd_test_frame(); game_click();
    chk("hold: no click on lift after the replay", changed == 1);

    // 3. Hold where the game reports its click only on lift.
    down(0.3f, 0.3f); dd_test_frame();
    hold_ms(600); dd_test_frame();
    chk("lift-only: nothing runs at Press", changed == 1);
    up(); dd_test_frame();
    game_click();
    chk("lift-only: the lift click runs once", changed == 2);
    game_click();
    chk("lift-only: a repeat lift click does not run", changed == 2);

    // 4. Eligibility withdrawn between the click and the press: the wrapper would
    //    refuse, so the adapter must not even enter it.
    down(0.5f, 0.5f); dd_test_frame(); game_click();
    chk("withdrawn: click withheld and captured", changed == 2 && dd_test_holds());
    int e = entries;
    eligible(0); hold_ms(600); dd_test_frame();
    chk("withdrawn: no wrapper entry at Press (eligibility false)", changed == 2 && entries == e);
    chk("withdrawn: the capture was released", !dd_test_holds() && releases == 3);
    eligible(1); up(); dd_test_frame(); game_click();
    chk("withdrawn: the lift click after a withdrawn eligibility does not run", changed == 2);

    // 5. Withdrawn, then eligible again: once the adapter has seen the refusal the
    //    capture is gone, so a later press cannot resurrect it.
    down(0.5f, 0.5f); dd_test_frame(); game_click();
    eligible(0); dd_test_frame();
    int e5 = entries;
    chk("revoked: the capture was dropped as soon as eligibility read 0", !dd_test_holds());
    eligible(1); hold_ms(600); dd_test_frame();
    chk("revoked then restored: still no replay", changed == 2 && entries == e5);
    up(); dd_test_frame(); game_click();
    chk("revoked then restored: the lift click does not run either", changed == 2);

    // 6. An ineligible skill (locked): the game never delivers a click, so there
    //    is nothing to arm and the hold cannot toggle.
    eligible(0);
    down(0.5f, 0.5f); dd_test_frame(); e = entries; game_click();
    chk("locked: the click never reaches the toggle or the filter", entries == e && !dd_test_holds());
    hold_ms(600); dd_test_frame();
    chk("locked: no toggle at Press", changed == 2 && entries == e);
    up(); dd_test_frame(); game_click();
    chk("locked: no toggle on lift", changed == 2 && entries == e);
    eligible(1);

    // 7. The native toggle refuses the change itself (a locked skill or the
    //    selection limit): the replay reaches it once and is not retried.
    native_refuses = 1;
    down(0.5f, 0.5f); dd_test_frame(); game_click();
    hold_ms(600); dd_test_frame();
    chk("native refusal: the wrapper ran the toggle once", refused == 1 && changed == 2);
    game_click();
    chk("native refusal: a duplicate click does not retry", refused == 1);
    up(); dd_test_frame();
    native_refuses = 0;

    // 8. A click on a CharacterDisplay that is not open (state 2) is withheld and
    //    not capturable: no replay at Press.
    panel_state(2);
    down(0.5f, 0.5f); dd_test_frame(); game_click();
    chk("panel not open: click withheld, nothing captured", changed == 2 && !dd_test_holds());
    hold_ms(600); dd_test_frame();
    chk("panel not open: no toggle at Press", changed == 2);
    panel_state(1); up(); dd_test_frame(); game_click();
    chk("panel not open: no toggle on lift", changed == 2);

    // 9. The panel closing discards the capture.
    down(0.2f, 0.2f); dd_test_frame(); game_click();
    chk("panel close: captured", dd_test_holds());
    dd_test_panel(panel_val);
    chk("panel close: capture discarded at once", !dd_test_holds());
    hold_ms(600); dd_test_frame();
    chk("panel closed: no toggle at Press", changed == 2);
    up(); dd_test_frame(); game_click();
    chk("panel closed: no toggle on lift", changed == 2);

    // 10. Movement beyond the 8 px slop cancels the contact.
    down(0.5f, 0.5f); dd_test_frame(); game_click();
    dm_touch mv = {0, 0.5f + 40.0f / 1280.0f, 0.5f}; dm_touch_set_from(&mv, 1, DM_CONTACT_IOS);
    dd_test_frame(); hold_ms(600); dd_test_frame();
    chk("move > 8 px: no toggle at Press", changed == 2 && !dd_test_holds());
    up(); dd_test_frame(); game_click();
    chk("move > 8 px: no toggle on lift", changed == 2);

    // 11. A second finger cancels the contact.
    down(0.5f, 0.5f); dd_test_frame(); game_click();
    dm_touch two[2] = {{0, 0.5f, 0.5f}, {1, 0.6f, 0.6f}}; dm_touch_set_from(two, 2, DM_CONTACT_IOS);
    dd_test_frame(); hold_ms(600); dd_test_frame();
    chk("second finger: no toggle at Press", changed == 2 && !dd_test_holds());
    dm_touch one[1] = {{0, 0.5f, 0.5f}}; dm_touch_set_from(one, 1, DM_CONTACT_IOS);
    up(); dd_test_frame(); game_click();
    chk("second finger: no toggle after it lifts", changed == 2);

    // 12. Policy off: every click is the original one and nothing is captured.
    int c0 = clones;
    dd_test_init((uintptr_t)img);
    dm_touch_policy_activate(0); dd_test_enable(0);
    down(0.5f, 0.5f); dd_test_frame(); game_click();
    chk("policy off: the game's click runs unchanged", changed == 3);
    hold_ms(600); dd_test_frame();
    chk("policy off: no capture and no replay", clones == c0 && changed == 3);
    up(); dd_test_frame(); game_click();
    chk("policy off: a lift click also runs unchanged", changed == 4);
    dd_test_enable(1); dm_touch_policy_activate(1); dd_test_init((uintptr_t)img);

    // 13. The host-clock Press exists only while a policy is active: the snapshot
    //     itself - the recognizer history every game reads - is not touched.
    dm_touch_policy_activate(0);
    down(0.5f, 0.5f); dd_test_frame(); hold_ms(600);
    dm_contact_snapshot s0; dm_touch_contact_snapshot(&s0);
    chk("policy off: a held finger stays DOWN/HOLDING in the snapshot", s0.phase == DM_CONTACT_DOWN || s0.phase == DM_CONTACT_HOLDING);
    dm_touch_policy_activate(1);
    dm_contact_snapshot s1; dm_touch_contact_snapshot(&s1);
    chk("policy on: the same held finger reads as PRESS", s1.phase == DM_CONTACT_PRESS);
    up(); dd_test_frame();

    // 14. A lift that follows a shorter hold keeps the selection.
    down(0.5f, 0.5f); dd_test_frame(); game_click();
    hold_ms(200); up(); dd_test_frame(); game_click();
    chk("short hold: no click on lift", changed == 4);

    // 15. Camping has its own action vtable/filter; the combat class alone
    // cannot authorize it. Exercise the actual shared policy with that class.
    uintptr_t *camp = calloc(2, sizeof(uintptr_t));
    camp_obj = (uintptr_t)camp;
    camp[0] = (uintptr_t)img + 0x11955b8; camp[1] = panel_val;
    uintptr_t cvt = camp[0];
    *(uintptr_t *)(cvt + 0x10) = (uintptr_t)camp_clone;
    *(uintptr_t *)(cvt + 0x28) = (uintptr_t)camp_release;
    *(uintptr_t *)(cvt + 0x30) = (uintptr_t)camp_toggle;
    dd_test_init((uintptr_t)img);
    down(0.5f, 0.5f); dd_test_frame(); game_camp_click();
    chk("camp tap: native action withheld and captured", camp_changed == 0 && dd_test_holds());
    up(); dd_test_frame(); game_camp_click();
    chk("camp tap: release does not change selection", camp_changed == 0 && !dd_test_holds());
    down(0.5f, 0.5f); dd_test_frame(); game_camp_click();
    hold_ms(600); dd_test_frame();
    chk("camp hold: original wrapper executes exactly once", camp_changed == 1);
    game_camp_click(); up(); dd_test_frame(); game_camp_click();
    chk("camp hold: duplicate and release do not repeat", camp_changed == 1);
    down(0.5f, 0.5f); dd_test_frame(); hold_ms(600);
    up(); dd_test_frame(); game_camp_click(); game_camp_click();
    chk("camp lift-only: one original release action", camp_changed == 2);
    down(0.5f, 0.5f); dd_test_frame(); game_camp_click();
    eligible(0); dd_test_frame(); hold_ms(600); eligible(1);
    up(); dd_test_frame(); game_camp_click();
    chk("camp eligibility withdrawn: no late action", camp_changed == 2);
    down(0.5f, 0.5f); dd_test_frame(); game_camp_click();
    dm_touch_cancel_from(DM_CONTACT_IOS); dd_test_frame();
    hold_ms(600); game_camp_click();
    chk("camp cancel: no action and no retained copy", camp_changed == 2 && !dd_test_holds());
    up(); dd_test_frame();
    dd_test_camp(0);
    down(0.5f, 0.5f); dd_test_frame(); game_camp_click();
    chk("old modules without camp gate: original camping action", camp_changed == 3);
    up(); dd_test_frame();
    dd_test_camp(1); dd_test_enable(0); dm_touch_policy_activate(0);
    down(0.5f, 0.5f); game_camp_click();
    chk("policy off: original camping action", camp_changed == 4);
    up(); dd_test_enable(1); dm_touch_policy_activate(1);
    chk("camp owned copies balanced", camp_clones == camp_releases);
    free(camp);

    // Nomad merchandise dispatch is recognized by the nested purchase binding,
    // not the reused inventory action type. Other owners and input sources pass.
    uintptr_t *shop = calloc(1, 0x310);
    uintptr_t *purchase = calloc(1, 0x50);
    if (!shop || !purchase) { printf("allocation failed\n"); return 1; }
    shop_obj = (uintptr_t)shop; purchase_obj = (uintptr_t)purchase;
    purchase[0] = (uintptr_t)img + 0x117a678;   // the purchase callback's vtable
    *(uintptr_t *)(img + 0x117a678 + 0x30) = (uintptr_t)fake_purchase;
    *(uintptr_t *)(img + 0x117a7c0 + 0x30) = (uintptr_t)img + 0xc31e00;   // the Comet supply's operator()
    shop[0] = (uintptr_t)img + 0x11933a8;
    shop[0x70 / 8] = (uintptr_t)purchase;
    shop[0x300 / 8] = 0;                        // mode: the +0x70 callable path
    *(uint32_t *)((uint8_t *)shop + 0x304) = 2; // the parameter the entry passes through
    *(uintptr_t *)(img + 0x11933a8 + 0x30) = (uintptr_t)img + 0xe18410;
    static const uint32_t shop_stub[] = {   // 0xe18410: tail-jump to the patched entry
        0x58000090,  // ldr x16, [pc, #16]
        0xd61f0200,  // br x16
        0xd503201f, 0xd503201f,  // nop (keeps the literal 8-aligned)
    };
    memcpy(img + 0xe18410, shop_stub, sizeof shop_stub);
    *(uintptr_t *)(img + 0xe18410 + sizeof shop_stub) = (uintptr_t)fake_entry_patched;   // the trampoline's literal
    uintptr_t slo = ((uintptr_t)img + 0xe18410) & ~(uintptr_t)(pg - 1);
    if (mprotect((void *)slo, (size_t)pg, PROT_READ | PROT_EXEC)) { printf("mprotect failed\n"); return 1; }

    dd_test_init((uintptr_t)img); dm_touch_policy_activate(1); dd_test_enable(1); dd_test_shop(1);
    down(0.5f, 0.5f); dd_test_frame();
    purchase[0] = (uintptr_t)img + 0x117a7c0;
    chk("Comet merchandise iOS action withheld before dispatch", !dd_test_shop_filter(shop_obj));
    purchase[0] = (uintptr_t)img + 0x1193c08;
    chk("ordinary inventory binding retains original operation", dd_test_shop_filter(shop_obj));
    shop[0x70 / 8] = 0;
    chk("empty slot binding retains original operation", dd_test_shop_filter(shop_obj));
    shop[0x70 / 8] = (uintptr_t)purchase; purchase[0] = (uintptr_t)img + 0x117a678;
    shop[0] = (uintptr_t)img + 0x1193428;
    chk("Nomad iOS secondary action withheld before dispatch", !dd_test_shop_filter(shop_obj));
    shop[0] = (uintptr_t)img + 0x11933a8;
    dm_touch mt = {0, 0.5f, 0.5f}; dm_touch_set_from(&mt, 1, DM_CONTACT_MAC_LEFT);
    chk("Mac merchandise operation unchanged", dd_test_shop_filter(shop_obj));
    down(0.5f, 0.5f); *(uint8_t *)(img + 0x27dec24) = 1;
    chk("controller-owned merchandise operation unchanged", dd_test_shop_filter(shop_obj));
    *(uint8_t *)(img + 0x27dec24) = 0; dd_test_shop(0);
    chk("old modules without shop gates retain operation", dd_test_shop_filter(shop_obj));
    dd_test_shop(1); dd_test_enable(0);
    chk("policy off retains merchandise operation", dd_test_shop_filter(shop_obj));
    dd_test_enable(1); up(); dd_test_frame();
    shop[0x300 / 8] = 1;
    down(0.5f, 0.5f); dd_test_frame();
    chk("mode-1 (+0xd0) dispatch retains original operation", dd_test_shop_filter(shop_obj));
    shop[0] = (uintptr_t)img + 0x1193428;
    chk("secondary binding is withheld regardless of that byte", !dd_test_shop_filter(shop_obj));
    shop[0] = (uintptr_t)img + 0x11933a8;
    up(); dd_test_frame(); shop[0x300 / 8] = 0;

    // 1. A touch-down click is withheld and the adapter never calls the purchase
    //    callback itself: a held contact with no game click or with only a
    //    touch-down click buys nothing, and a closed panel therefore cannot be
    //    bought from (no deferred call exists).
    down(0.5f, 0.5f); dd_test_frame(); game_shop_click();
    chk("shop touch-down click: withheld, nothing purchased", shop_purchases == 0);
    hold_ms(600); dd_test_frame();
    chk("shop hold without a game click: nothing purchased", shop_purchases == 0);
    up(); dd_test_frame();
    chk("shop lift without a game click: nothing purchased", shop_purchases == 0);

    // 2. The game's own live press click (>=0.5 s) is allowed once; a repeat and
    //    the following lift click are refused.
    down(0.4f, 0.4f); dd_test_frame(); hold_ms(600); dd_test_frame();
    game_shop_click();
    chk("shop press click: the game's own click purchases once", shop_purchases == 1);
    game_shop_click();
    chk("shop press click: a duplicate is refused", shop_purchases == 1);
    up(); dd_test_frame(); game_shop_click();
    chk("shop press click: the lift click is refused after it", shop_purchases == 1);

    // 3. A tap: the touch-down click and the short lift click are both refused.
    down(0.5f, 0.5f); dd_test_frame(); game_shop_click(); hold_ms(200); up(); dd_test_frame(); game_shop_click();
    chk("shop tap: no purchase", shop_purchases == 1);

    // 4. A lift click after a >=0.5 s hold is the game's own click and buys once;
    //    a repeat is refused. This is the native long-press release path, with no
    //    deferred call and no stored game object.
    down(0.3f, 0.3f); dd_test_frame(); hold_ms(600); up(); dd_test_frame(); game_shop_click();
    chk("shop long lift: the game's own click purchases once", shop_purchases == 2);
    game_shop_click();
    chk("shop long lift: a repeat is refused", shop_purchases == 2);

    // 5. A short lift click after a short hold does not buy.
    down(0.3f, 0.3f); dd_test_frame(); hold_ms(200); up(); dd_test_frame(); game_shop_click();
    chk("shop short lift: no purchase", shop_purchases == 2);

    // 6. Movement, cancel and a second finger keep the wallet closed.
    down(0.5f, 0.5f); dd_test_frame(); game_shop_click();
    dm_touch swipe = {0, 0.5f + 40.0f / 1280.0f, 0.5f}; dm_touch_set_from(&swipe, 1, DM_CONTACT_IOS);
    dd_test_frame(); hold_ms(600); dd_test_frame(); game_shop_click();
    chk("shop move > 8 px: no purchase", shop_purchases == 2);
    up(); dd_test_frame(); game_shop_click();
    chk("shop move > 8 px: no purchase on lift", shop_purchases == 2);
    down(0.5f, 0.5f); dd_test_frame(); game_shop_click();
    dm_touch_cancel_from(DM_CONTACT_IOS); dd_test_frame(); hold_ms(600); game_shop_click();
    chk("shop cancel: no purchase", shop_purchases == 2);
    up(); dd_test_frame();
    down(0.5f, 0.5f); dd_test_frame(); game_shop_click();
    dm_touch shop_two[2] = {{0, 0.5f, 0.5f}, {1, 0.6f, 0.6f}}; dm_touch_set_from(shop_two, 2, DM_CONTACT_IOS);
    dd_test_frame(); hold_ms(600); dd_test_frame(); game_shop_click();
    chk("shop second finger: no purchase", shop_purchases == 2);
    dm_touch shop_one[1] = {{0, 0.5f, 0.5f}}; dm_touch_set_from(shop_one, 1, DM_CONTACT_IOS); up(); dd_test_frame();

    // 6b. A cancellation and the release in the same frame, with no frame tick
    //     in between: the release must not launder the bad contact into a buy.
    int same_buys = shop_purchases;
    down(0.5f, 0.5f); hold_ms(600);
    dm_touch same_mv = {0, 0.5f + 40.0f / 1280.0f, 0.5f}; dm_touch_set_from(&same_mv, 1, DM_CONTACT_IOS);
    up(); game_shop_click();
    chk("shop same-frame move+up: no purchase", shop_purchases == same_buys);
    down(0.5f, 0.5f); hold_ms(600);
    dm_touch_cancel_from(DM_CONTACT_IOS); up(); game_shop_click();
    chk("shop same-frame cancel+up: no purchase", shop_purchases == same_buys);
    down(0.5f, 0.5f); hold_ms(600);
    dm_touch same_two[2] = {{0, 0.5f, 0.5f}, {1, 0.6f, 0.6f}}; dm_touch_set_from(same_two, 2, DM_CONTACT_IOS);
    dm_touch_set_from(NULL, 0, DM_CONTACT_IOS); game_shop_click();
    chk("shop same-frame second finger+all up: no purchase", shop_purchases == same_buys);

    // 7. The gate is only entered by the game's own clicks: holding and lifting
    //    with no dispatch does not call the wrapper, and a press click after a
    //    withheld touch-down click is decided on its own live copy (the earlier
    //    queue entry was destroyed and poisoned by the fixture).
    int gates = shop_gate_calls;
    down(0.5f, 0.5f); dd_test_frame(); game_shop_click();
    chk("shop state: the withheld click is the only gate call", shop_gate_calls == gates + 1 && qobj[0] == 0xAA);
    hold_ms(600); dd_test_frame();
    chk("shop state: no adapter call into the wrapper during the hold", shop_gate_calls == gates + 1);
    game_shop_click();
    chk("shop state: the press click is decided on the live click", shop_purchases == 3 && shop_gate_calls == gates + 2);
    up(); dd_test_frame();

    // 8. The supply display's own gate (OBS 30) arms the recognizer's hold-tap
    //    for the contact that went down on it: the still finger is not promoted
    //    to Press, and its release is the Tap the game turns into the row's own
    //    click. Only the Nomad purchase binding marks the screen.
    uintptr_t binding_vt = shop[0], bound_cb = purchase[0];
    dd_test_init((uintptr_t)img); dm_touch_policy_activate(1); dd_test_enable(1); dd_test_shop(1);
    gesture_idle();
    shop[0] = (uintptr_t)img + 0x1193428;   // the secondary wrapper: not the one the click dispatches
    dd_test_shop_build(shop_obj);
    chk("display gate: the secondary binding does not mark the display", dd_test_shop_live() == 0);
    shop[0] = binding_vt; shop[0x300 / 8] = 1;
    dd_test_shop_build(shop_obj);
    chk("display gate: the drag mode (+0xd0 path) does not mark the display", dd_test_shop_live() == 0);
    shop[0x300 / 8] = 0; purchase[0] = (uintptr_t)img + 0x117a7c0;
    dd_test_shop_build(shop_obj);
    chk("display gate: the Comet purchase binding marks the display", dd_test_shop_live() != 0);
    dd_test_init((uintptr_t)img); dm_touch_policy_activate(1); dd_test_enable(1); dd_test_shop(1);
    purchase[0] = (uintptr_t)img + 0x1193c08;   // the inventory grid's own callable
    dd_test_shop_build(shop_obj);
    chk("display gate: a foreign bound callback does not mark the display", dd_test_shop_live() == 0);
    purchase[0] = bound_cb;
    dd_test_shop_build(shop_obj);
    chk("display gate: the Nomad purchase binding marks the display", dd_test_shop_live() != 0);

    // A contact that goes down while the rows are drawn is armed; the finger's
    // 0.6 s hold stays a Touch (no Press), so the release is a Tap, and the
    // game's own click on that release buys exactly once.
    int buys = shop_purchases;
    down(0.5f, 0.5f); dd_test_frame();
    uint64_t armed = dd_test_tap_generation();
    chk("hold-tap: the contact that went down on the display is armed", armed != 0 && dd_test_shop_live() != 0);
    gesture_state gs[4]; int n = gesture_fill(gs, 4, dm_touch_now_ns());
    chk("hold-tap: the first gesture read is a Touch", n > 0 && gs[0].type == 3);
    hold_ms(600);
    n = gesture_fill(gs, 4, dm_touch_now_ns());
    chk("hold-tap: 0.6 s later the finger is still not a Press", n > 0 && gs[0].type == 3);
    up(); dd_test_frame();
    n = gesture_fill(gs, 4, dm_touch_now_ns());
    chk("hold-tap: the release is the game's own Tap", n > 0 && gs[0].type == 5);
    game_shop_click();
    chk("hold-tap: that click runs the purchase binding once", shop_purchases == buys + 1);
    game_shop_click();
    chk("hold-tap: a repeated click is refused", shop_purchases == buys + 1);

    // A short tap in the same place still only focuses: the Tap it makes is
    // withheld by the filter (under 0.5 s).
    dd_test_init((uintptr_t)img); dm_touch_policy_activate(1); dd_test_enable(1); dd_test_shop(1);
    gesture_idle();
    dd_test_shop_build(shop_obj);
    down(0.5f, 0.5f); dd_test_frame(); hold_ms(120); up(); dd_test_frame();
    gesture_fill(gs, 4, dm_touch_now_ns());
    game_shop_click();
    chk("hold-tap: a short tap purchases nothing", shop_purchases == buys + 1);

    // Cancellation and a move disarm the contact: the game's click that follows
    // may not buy even though the display is still live.
    dd_test_init((uintptr_t)img); dm_touch_policy_activate(1); dd_test_enable(1); dd_test_shop(1);
    gesture_idle();
    dd_test_shop_build(shop_obj);
    down(0.5f, 0.5f); dd_test_frame();
    chk("hold-tap: armed before the cancel", dd_test_tap_generation() != 0);
    dm_touch_cancel_from(DM_CONTACT_IOS); dd_test_frame();
    chk("hold-tap: a cancelled contact is disarmed", dd_test_tap_generation() == 0);
    chk("hold-tap: a cancelled contact's click is refused", !dd_test_shop_filter(shop_obj));
    up(); dd_test_frame();
    dd_test_init((uintptr_t)img); dm_touch_policy_activate(1); dd_test_enable(1); dd_test_shop(1);
    gesture_idle();
    dd_test_shop_build(shop_obj);
    down(0.5f, 0.5f); dd_test_frame();
    dm_touch mv2 = {0, 0.5f + 40.0f / 1280.0f, 0.5f}; dm_touch_set_from(&mv2, 1, DM_CONTACT_IOS);
    dd_test_frame();
    chk("hold-tap: a moved contact is disarmed", dd_test_tap_generation() == 0);
    up(); dd_test_frame();

    // A contact that goes down while the display is not drawing (shop closed,
    // another screen) is never armed, and a module without the shop gates
    // records nothing at all.
    dd_test_init((uintptr_t)img); dm_touch_policy_activate(1); dd_test_enable(1); dd_test_shop(1);
    down(0.5f, 0.5f); dd_test_frame();
    chk("hold-tap: a contact outside the display is not armed", dd_test_tap_generation() == 0 && dd_test_shop_live() == 0);
    up(); dd_test_frame();
    dd_test_shop(0);
    dd_test_shop_build(shop_obj);
    chk("display gate: a module without the shop gates records nothing", dd_test_shop_live() == 0);
    dd_test_shop(1);

    free(shop); free(purchase);

    // ---- Prepared-module self-check: the same dd_validate() the real init
    // runs must accept a module whose 0xc60084 was rewritten to the gate branch
    // (the adapter must not check that word at run time) with the original
    // neighbours, frame prologue and vtables; a changed neighbour, prologue,
    // missing gate or changed operator slot must refuse the roster.
    memset(g_mod, 0, sizeof g_mod);
    strcpy(g_mod[0].name, "main"); g_mod[0].base = img; g_mod[0].size = IMG_LEN;
    strcpy(g_mod[0].build_id, "ff2bf22565188d11ea0981ee0e2b53ce");
    strcpy(g_mod[1].name, "sdk"); strcpy(g_mod[1].build_id, "b33804825108340e4cad9d080a636a3f");
    g_nmod = 2;
    put32(0xc5c6c0, 0x6db82beb); put32(0xc5c6c8, 0xa9027bfd); put32(0xc5c6cc, 0x910083fd);
    put32(0xc5c6e4, 0xd128c3ff);
    put32(0xc60080, 0x97eb6d94); put32(0xc60088, 0xeb14001f);
    put32(0xc60084, 0x14000000);            // prepared: the gate branch, not the original ldr
    put32(0x73b6d0, 0x6db82beb); put32(0x717370, 0xd10203ff);
    *(uintptr_t *)(img + 0x117cd40 + 0x30) = (uintptr_t)img + 0xc61890;
    *(uintptr_t *)(img + 0x117cdc0 + 0x30) = (uintptr_t)img + 0xc615b0;
    obs_missing = -1;
    chk("prepared module: the real validation accepts the roster gate", dd_test_validate() == 1);
    chk("prepared module: the common policy is valid", dd_test_valid() == 1);
    put32(0xc60080, 0);                      // a changed bl neighbour
    chk("prepared module: a changed bl neighbour refuses the roster", dd_test_validate() == 0);
    put32(0xc60080, 0x97eb6d94);
    put32(0xc5c6e4, 0xd1028bff);             // a changed frame prologue
    chk("prepared module: a changed frame prologue refuses the roster", dd_test_validate() == 0);
    put32(0xc5c6e4, 0xd128c3ff);
    obs_missing = 28;                        // OBS_DD_ROSTER_CLICK: the module has no such gate
    chk("prepared module: a missing roster gate refuses the roster", dd_test_validate() == 0);
    obs_missing = -1;
    chk("prepared module: the roster is available again", dd_test_validate() == 1);
    put32(0xc60084, 0xf9404be0);             // restore for the rest of the fixture

    // ---- Nomad shop diagnostic (OBS 29, 0xe15690): the site is accepted only
    // with the retail neighbours of the row update (the query, the click byte's
    // default and copy, and the dispatch's keepalive), and a changed neighbour
    // must refuse it.
    put32(0xe1568c, 0x9400c35d); put32(0xe15694, 0x36000228);
    put32(0xe15698, 0xf940eb40); put32(0xe1569c, 0xb4000140);
    put32(0xe134d0, 0x52802008); put32(0xe134d4, 0x781a73a8); put32(0xe134fc, 0xd63f0120);
    put32(0xe1350c, 0x395603e8); put32(0xe13514, 0x381a83a8);
    chk("prepared module: the real validation accepts the shop diagnostic site", dd_test_validate() == 1 && dd_test_probe_ok() == 1);
    obs_missing = 29;
    chk("prepared module: a missing shop-update gate withdraws the diagnostic", dd_test_validate() == 1 && dd_test_probe_ok() == 0);
    obs_missing = -1;
    put32(0xe15698, 0xf940eb00);             // a changed ldr x0,[x26,#0x1d0]
    chk("prepared module: a changed dispatch neighbour withdraws the diagnostic", dd_test_validate() == 1 && dd_test_probe_ok() == 0);
    put32(0xe15698, 0xf940eb40);
    put32(0xe13514, 0x381a83a0);             // a changed click-byte store
    chk("prepared module: a changed click-byte store withdraws the diagnostic", dd_test_probe_ok() == 0);
    put32(0xe13514, 0x381a83a8);
    chk("prepared module: the diagnostic is available again", dd_test_validate() == 1 && dd_test_probe_ok() == 1);

    // The diagnostic itself: read-only, off unless asked for, one line per row
    // per change, inside a single iPhone contact, only for the verified Nomad
    // binding, and capped.
    uintptr_t *wshop = calloc(1, 0x310), *wbuy = calloc(1, 0x50);
    uintptr_t prow = (uintptr_t)calloc(1, 0x300);
    uint8_t *pstk = calloc(1, 0x200);
    uintptr_t pfp = (uintptr_t)pstk + 0x100;
    if (!wshop || !wbuy || !prow || !pstk) { printf("allocation failed\n"); return 1; }
    wshop[0] = (uintptr_t)img + 0x11933a8;
    wshop[0x70 / 8] = (uintptr_t)wbuy;
    wbuy[0] = (uintptr_t)img + 0x117a678;
    *(uintptr_t *)(prow + 0x1d0) = (uintptr_t)wshop;
    *(uint8_t *)(prow + 0xe0) = 1; *(uint8_t *)(prow + 0xe2) = 0x40;
    *(uint8_t *)(pfp - 0x98) = 1;  *(uint8_t *)(pfp - 0x58) = 0;
    uint8_t snap[0x20]; memcpy(snap, (void *)prow, sizeof snap);
    dd_test_init((uintptr_t)img); dm_touch_policy_activate(1); dd_test_enable(1);
    dd_test_probe(0);
    down(0.5f, 0.5f); dd_test_frame(); hold_ms(600); dd_test_frame();
    dd_test_shop_update(prow, pfp);
    chk("shop probe: inert unless DM_DD_SHOP_PROBE is set", dd_test_probe_lines() == 0);
    dd_test_probe(1);
    dd_test_shop_update(prow, pfp);
    chk("shop probe: a held iPhone contact on the Nomad row records one line", dd_test_probe_rows() == 1);
    dd_test_shop_update(prow, pfp);
    chk("shop probe: an unchanged row is not recorded again", dd_test_probe_rows() == 1);
    *(uint8_t *)(prow + 0xe1) = 2;
    dd_test_shop_update(prow, pfp);
    chk("shop probe: a changed row byte records a line", dd_test_probe_rows() == 2);
    *(uint8_t *)(pfp - 0x58) = 1;                // the game's own click arrives
    dd_test_shop_update(prow, pfp);
    chk("shop probe: the click byte is recorded as it changes", dd_test_probe_rows() == 3);
    *(uint8_t *)(pfp - 0x58) = 0;
    wbuy[0] = (uintptr_t)img + 0x117a7c0;        // Comet's callable: not the Nomad purchase
    dd_test_shop_update(prow, pfp);
    chk("shop probe: a rebound purchase callback records a line", dd_test_probe_rows() == 4);
    wbuy[0] = (uintptr_t)img + 0x117a678;
    up(); dd_test_frame(); hold_ms(20);
    dd_test_shop_update(prow, pfp);
    chk("shop probe: a released contact is still recorded", dd_test_probe_rows() == 5);
    dm_touch pmm = {0, 0.5f, 0.5f}; dm_touch_set_from(&pmm, 1, DM_CONTACT_MAC_LEFT);
    dd_test_frame(); hold_ms(20);
    dd_test_shop_update(prow, pfp);
    chk("shop probe: the Mac's left button is not recorded", dd_test_probe_rows() == 5);
    up(); dd_test_frame();
    down(0.5f, 0.5f); dd_test_frame(); hold_ms(600);
    dm_touch pmv = {0, 0.5f + 40.0f / 1280.0f, 0.5f}; dm_touch_set_from(&pmv, 1, DM_CONTACT_IOS);
    dd_test_frame(); hold_ms(20);
    dd_test_shop_update(prow, pfp);
    chk("shop probe: a moved/cancelled contact is not recorded", dd_test_probe_rows() == 5);
    up(); dd_test_frame();
    memcpy(snap, (void *)prow, sizeof snap);
    int wrote = 0;
    down(0.5f, 0.5f); dd_test_frame(); hold_ms(600); dd_test_frame();
    for (int i = 0; i < 4; i++) dd_test_shop_update(prow, pfp);
    if (memcmp(snap, (void *)prow, sizeof snap)) wrote = 1;
    chk("shop probe: nothing in the row is written", !wrote && *(uintptr_t *)(prow + 0x1d0) == (uintptr_t)wshop);
    up(); dd_test_frame();
    // The cap: a row that changes every frame stops at DD_PROBE_MAX + one notice.
    dd_test_probe(1);
    down(0.5f, 0.5f); dd_test_frame(); hold_ms(600); dd_test_frame();
    for (int i = 0; i < 200; i++) { *(uint8_t *)(prow + 0xe3) = (uint8_t)i; dd_test_shop_update(prow, pfp); }
    chk("shop probe: the line budget is capped", dd_test_probe_lines() == 121);
    up(); dd_test_frame();
    // A reused live control address must not hide another merchandise slot.
    dd_test_probe(1);
    down(0.5f, 0.5f); dd_test_frame();
    *(uint32_t *)((uintptr_t)wshop + 0x304) = 0;
    dd_test_shop_update(prow, pfp);
    *(uint32_t *)((uintptr_t)wshop + 0x304) = 1;
    dd_test_shop_update(prow, pfp);
    chk("shop probe: reused control with another item slot is recorded", dd_test_probe_rows() == 2);
    *(uint32_t *)((uintptr_t)wshop + 0x304) = 0;
    dd_test_shop_update(prow, pfp);
    chk("shop probe: revisiting an unchanged item slot is deduplicated", dd_test_probe_rows() == 2);
    up(); dd_test_frame();
    // A row whose dispatch callable is not a Nomad binding: the callable's own
    // vtable is the datum that names the row class, so the first one is recorded
    // once and only counted afterwards. Its slots are read, never written.
    uintptr_t *wforeign = calloc(1, 0x310);
    if (!wforeign) { printf("allocation failed\n"); return 1; }
    wforeign[0] = (uintptr_t)img + 0x117c8d0;
    *(uintptr_t *)(prow + 0x1d0) = (uintptr_t)wforeign;
    *(uintptr_t *)(prow + 0x170) = (uintptr_t)wforeign;
    dd_test_probe(1);
    down(0.5f, 0.5f); dd_test_frame(); hold_ms(600);
    dd_test_shop_update(prow, pfp);
    chk("shop probe: a foreign dispatch callable records one vtable line", dd_test_probe_rows() == 0 && dd_test_probe_lines() == 1);
    int flines = dd_test_probe_lines();
    dd_test_shop_update(prow, pfp);
    chk("shop probe: the same foreign callable is not recorded again", dd_test_probe_lines() == flines);
    wforeign[0] = (uintptr_t)img + 0x117cfd0;      // a second shape: one more line
    dd_test_shop_update(prow, pfp);
    chk("shop probe: a different callable shape is recorded", dd_test_probe_lines() == flines + 1);
    *((uintptr_t *)(prow + 0x1d0)) = (uintptr_t)wshop; *((uintptr_t *)(prow + 0x170)) = 0;
    free(wforeign);
    // The periodic summary: frame 25 writes one line whatever the counters say,
    // and the next frame does not repeat it.
    dd_test_probe(1);
    dd_test_probe_frame(24);
    int slines = dd_test_probe_lines();
    dd_test_frame();
    chk("shop probe: the summary is written at frame 25", dd_test_probe_lines() == slines + 1);
    dd_test_frame();
    chk("shop probe: the next frame writes no summary", dd_test_probe_lines() == slines + 1);
    up(); dd_test_frame();
    const char *probe_env = getenv("DM_DD_SHOP_PROBE");
    char *saved_probe_env = probe_env ? strdup(probe_env) : NULL;
    unsetenv("DM_DD_SHOP_PROBE");
    chk("shop probe: absent environment switch is off", !dd_test_probe_requested());
    setenv("DM_DD_SHOP_PROBE", "0", 1);
    chk("shop probe: environment value zero is off", !dd_test_probe_requested());
    setenv("DM_DD_SHOP_PROBE", "1", 1);
    chk("shop probe: exact environment value one enables diagnostics", dd_test_probe_requested());
    if (saved_probe_env) { setenv("DM_DD_SHOP_PROBE", saved_probe_env, 1); free(saved_probe_env); }
    else unsetenv("DM_DD_SHOP_PROBE");
    dd_test_probe(0); dd_test_init((uintptr_t)img);
    free(wshop); free(wbuy); free((void *)prow); free(pstk);

    // ---- Town roster long press: append the original details callable to the
    // game's own action queue (section 20 of the audit). The fixture mirrors the
    // frame's queue entry pushed by 0x73b6d0 (primary, inline {vtable, element})
    // and the same frame's details std::function at sp+0x70 = x29-0x9e0
    // (fp = sp+0xa50 from the real prologue; the decoy at fp+0xd0 is the old bug).
    uintptr_t elem2 = (uintptr_t)calloc(1, 0x300);
    uintptr_t list2 = (uintptr_t)calloc(1, 0x100);
    uintptr_t vec2 = (uintptr_t)calloc(2, 0x40);
    uintptr_t fsp = (uintptr_t)calloc(1, 0xc00);   // the roster frame's sp
    uintptr_t frame = fsp + 0xa50;                 // the frame's x29 (prologue: x29 = sp+0xa50)
    uintptr_t qbuf = (uintptr_t)calloc(4, 0x30);
    uintptr_t *q = (uintptr_t *)qbuf;
    uintptr_t details = fsp + 0x70, primary = fsp + 0xa0;
    uintptr_t decoy = frame + 0xd0;                // the old, wrong offset: must never be used
    if (!elem2 || !list2 || !vec2 || !fsp || !qbuf) { printf("allocation failed\n"); return 1; }
    *(uintptr_t *)elem2 = (uintptr_t)img + 0x117c8d0;
    *(uintptr_t *)(elem2 + 0x80) = list2;
    *(uintptr_t *)list2 = (uintptr_t)img + 0x117cfd0;
    *(uintptr_t *)(list2 + 0x90) = vec2; *(uintptr_t *)(list2 + 0x98) = vec2 + 2 * 0x40;
    *(uintptr_t *)vec2 = elem2; *(uintptr_t *)(vec2 + 0x40) = 0x1234;
    *(uintptr_t *)details = (uintptr_t)img + 0x117cdc0; *(uintptr_t *)(details + 8) = elem2;
    *(uintptr_t *)(details + 0x20) = details;                 // inline __f_
    *(uintptr_t *)primary = (uintptr_t)img + 0x117cd40; *(uintptr_t *)(primary + 8) = elem2;
    *(uintptr_t *)(primary + 0x20) = primary;
    q[0] = (uintptr_t)img + 0x117cd40; q[1] = elem2; q[4] = qbuf;   // the primary the game just pushed
    *(uintptr_t *)(img + 0x257e530) = qbuf;                  // queue begin
    *(uintptr_t *)(img + 0x257e538) = qbuf + 0x30;           // queue end (one entry)
    *(uintptr_t *)(img + 0x257e540) = qbuf + 4 * 0x30;
    *(uintptr_t *)(img + 0x117cd40 + 0x30) = (uintptr_t)fake_roster_primary;
    *(uintptr_t *)(img + 0x117cdc0 + 0x30) = (uintptr_t)fake_roster_details;
    static const uint32_t push_stub[] = { 0x58000090, 0xd61f0200, 0xd503201f, 0xd503201f };
    memcpy(img + 0x717370, push_stub, sizeof push_stub);
    *(uintptr_t *)(img + 0x717370 + sizeof push_stub) = (uintptr_t)fake_push;
    uintptr_t plo = ((uintptr_t)img + 0x717370) & ~(uintptr_t)(pg - 1);
    if (mprotect((void *)plo, (size_t)pg, PROT_READ | PROT_EXEC)) { printf("mprotect failed\n"); return 1; }

    dd_test_init((uintptr_t)img); dm_touch_policy_activate(1); dd_test_roster(1);
    roster_pushes = roster_details_calls = roster_primary_calls = 0;

    // 1. A held contact: the game's own click queued the primary; the adapter
    //    appends the details callable once and the drain would run both.
    down(0.4f, 0.4f); hold_ms(600);
    dd_test_roster_click(elem2, frame);
    chk("roster hold: the details callable was appended once", roster_pushes == 1);
    chk("roster hold: the queue grew by one entry", *(uintptr_t *)(img + 0x257e538) == qbuf + 2 * 0x30);
    chk("roster hold: the appended entry is the details callable for this element",
        *(uintptr_t *)(qbuf + 0x30) == (uintptr_t)img + 0x117cdc0 &&
        *(uintptr_t *)(qbuf + 0x38) == elem2);
    chk("roster hold: the old x29+0xd0 offset is not the source",
        *(uintptr_t *)(qbuf + 0x30) != (uintptr_t)img + 0x117cdc0 || decoy != details);
    dd_test_roster_click(elem2, frame);
    chk("roster hold: one action per contact", roster_pushes == 1);
    // drain: each entry's vtable +0x30 runs (the game's own drain semantics)
    for (uintptr_t e = *(uintptr_t *)(img + 0x257e530); e < *(uintptr_t *)(img + 0x257e538); e += 0x30) {
        uintptr_t f = *(uintptr_t *)(e + 0x20);
        ((void (*)(uintptr_t))(*(uintptr_t *)(*(uintptr_t *)f + 0x30)))(f);
    }
    chk("roster hold: the drain ran the primary and the details once",
        roster_primary_calls == 1 && roster_details_calls == 1);
    up();

    // 2. A short contact: no append.
    down(0.4f, 0.4f); hold_ms(200);
    dd_test_roster_click(elem2, frame);
    chk("roster tap: no details action", roster_pushes == 1);
    up();

    // 3. A release after >=0.5 s (the game's click on lift) appends once.
    roster_pushes = roster_details_calls = roster_primary_calls = 0;
    *(uintptr_t *)(img + 0x257e538) = qbuf + 0x30;
    down(0.4f, 0.4f); hold_ms(600); up();
    dd_test_roster_click(elem2, frame);
    chk("roster long lift: the details callable was appended once", roster_pushes == 1);

    // 4. The live target checks: empty queue, another element's primary,
    //    details already queued, wrong details vtable, wrong element/list.
    *(uintptr_t *)(img + 0x257e538) = qbuf;                    // empty (no click)
    roster_pushes = 0;
    down(0.4f, 0.4f); hold_ms(600); dd_test_roster_click(elem2, frame);
    chk("roster: no click in the queue, no action", roster_pushes == 0);
    *(uintptr_t *)(img + 0x257e538) = qbuf + 0x30;
    q[1] = 0x5678;                                              // primary for another element
    dd_test_roster_click(elem2, frame);
    chk("roster: another element's primary, no action", roster_pushes == 0);
    q[1] = elem2;
    *(uintptr_t *)(qbuf + 0x30) = (uintptr_t)img + 0x117cdc0; *(uintptr_t *)(qbuf + 0x38) = elem2;
    *(uintptr_t *)(qbuf + 0x50) = qbuf + 0x30;
    *(uintptr_t *)(img + 0x257e538) = qbuf + 2 * 0x30;          // details already queued
    dd_test_roster_click(elem2, frame);
    chk("roster: the game already queued the details, no duplicate", roster_pushes == 0);
    *(uintptr_t *)(img + 0x257e538) = qbuf + 0x30;
    *(uintptr_t *)details = 0;                                  // wrong details vtable
    dd_test_roster_click(elem2, frame);
    chk("roster: unverified details callable, no action", roster_pushes == 0);
    *(uintptr_t *)details = (uintptr_t)img + 0x117cdc0;
    *(uintptr_t *)elem2 = 0;                                    // wrong element
    dd_test_roster_click(elem2, frame);
    chk("roster: unverified element, no action", roster_pushes == 0);
    *(uintptr_t *)elem2 = (uintptr_t)img + 0x117c8d0;
    // Only a decoy at the old wrong offset (x29+0xd0), with a valid-looking
    // details callable: the adapter must not use it.
    *(uintptr_t *)decoy = (uintptr_t)img + 0x117cdc0; *(uintptr_t *)(decoy + 8) = elem2;
    *(uintptr_t *)(decoy + 0x20) = decoy;
    *(uintptr_t *)details = 0;                 // the real sp+0x70 function is gone
    roster_pushes = 0; *(uintptr_t *)(img + 0x257e538) = qbuf + 0x30;
    dd_test_roster_click(elem2, frame);
    chk("roster: a callable only at the old x29+0xd0 offset is refused", roster_pushes == 0);
    *(uintptr_t *)details = (uintptr_t)img + 0x117cdc0; *(uintptr_t *)(details + 8) = elem2;
    *(uintptr_t *)(details + 0x20) = details;
    up();

    // 4b. The same cancellation+release in one frame, with no frame tick in
    //     between: the roster must not append after a moved/cancelled contact.
    *(uintptr_t *)(img + 0x257e538) = qbuf + 0x30;
    roster_pushes = 0;
    down(0.4f, 0.4f); hold_ms(600);
    dm_touch r_mv = {0, 0.4f + 40.0f / 1280.0f, 0.4f}; dm_touch_set_from(&r_mv, 1, DM_CONTACT_IOS);
    up(); dd_test_roster_click(elem2, frame);
    chk("roster same-frame move+up: no action", roster_pushes == 0);
    down(0.4f, 0.4f); hold_ms(600);
    dm_touch_cancel_from(DM_CONTACT_IOS); up(); dd_test_roster_click(elem2, frame);
    chk("roster same-frame cancel+up: no action", roster_pushes == 0);
    down(0.4f, 0.4f); hold_ms(600);
    dm_touch r_two[2] = {{0, 0.4f, 0.4f}, {1, 0.5f, 0.5f}}; dm_touch_set_from(r_two, 2, DM_CONTACT_IOS);
    dm_touch_set_from(NULL, 0, DM_CONTACT_IOS); dd_test_roster_click(elem2, frame);
    chk("roster same-frame second finger+all up: no action", roster_pushes == 0);

    // 5. Cancelled / moved / Mac / controller / policy off: no append.
    down(0.4f, 0.4f); hold_ms(600);
    dm_touch_cancel_from(DM_CONTACT_IOS); dd_test_frame();
    roster_pushes = 0;
    dd_test_roster_click(elem2, frame);
    chk("roster cancel: no action", roster_pushes == 0);
    roster_pushes = 0; *(uintptr_t *)(img + 0x257e538) = qbuf + 0x30;
    dm_touch mt2 = {0, 0.4f, 0.4f}; dm_touch_set_from(&mt2, 1, DM_CONTACT_MAC_LEFT);
    hold_ms(600); dd_test_frame();             // the frame tick must not block a Mac left contact
    dm_touch_set_from(NULL, 0, DM_CONTACT_MAC_LEFT);
    dd_test_roster_click(elem2, frame);
    chk("roster Mac left hold: the roster details action is enabled", roster_pushes == 1);
    roster_pushes = 0; *(uintptr_t *)(img + 0x257e538) = qbuf + 0x30;
    down(0.4f, 0.4f); hold_ms(600);
    *(uint8_t *)(img + 0x27dec24) = 1;
    dd_test_roster_click(elem2, frame);
    chk("roster controller-owned: no action", roster_pushes == 0);
    *(uint8_t *)(img + 0x27dec24) = 0;
    dd_test_roster(0);
    dd_test_roster_click(elem2, frame);
    chk("roster policy off: original behaviour", roster_pushes == 0);
    dd_test_roster(1);
    up();

    free((void *)elem2); free((void *)list2); free((void *)vec2); free((void *)fsp); free((void *)qbuf);

    // ---- Guild upgrade confirmation (filter 0xc16320, arming observation 0xc16d20) -----------
    // The game dispatches the confirmation from its upgrade tree when the player clicks a skill
    // row; in this build that click is the Tap of a lifting finger. A short tap must be withheld
    // (the row stays focused, its own hover/price/description are untouched) and a release after
    // 0.5 s must run the game's own confirmation exactly once.
    dd_test_upgrade(1);
    *(uint8_t *)(img + 0x27dec24) = 0;
    down(0.5f, 0.5f); dd_test_frame();
    chk("upgrade: a fresh contact is withheld (focus only)", !dd_test_upgrade_filter());
    up(); dd_test_frame();
    chk("upgrade: the short tap's release is still withheld", !dd_test_upgrade_filter());
    down(0.5f, 0.5f); dd_test_frame(); hold_ms(600); dd_test_frame();
    up(); dd_test_frame();
    chk("upgrade: the release after a >=0.5 s hold runs the game's own confirmation", dd_test_upgrade_filter());
    chk("upgrade: and only once for that contact", !dd_test_upgrade_filter());
    down(0.5f, 0.5f); dd_test_frame(); hold_ms(600);
    dm_touch_cancel_from(DM_CONTACT_IOS); dd_test_frame();
    chk("upgrade: a cancelled contact never buys", !dd_test_upgrade_filter());
    up(); dd_test_frame();
    dm_touch up_two[2] = {{0, 0.5f, 0.5f}, {1, 0.6f, 0.6f}};
    dm_touch_set_from(up_two, 2, DM_CONTACT_IOS); dd_test_frame(); hold_ms(600); dd_test_frame();
    up(); dd_test_frame();
    chk("upgrade: a second finger keeps the confirmation withheld", !dd_test_upgrade_filter());
    // The arming observation: while the rows are being described, a contact that goes down is
    // latched so its held release stays the game's Tap instead of becoming Press.
    gesture_idle();
    dd_test_upgrade_rows();
    chk("upgrade: describing the rows marks the list on screen", dd_test_upgrade_live() != 0);
    down(0.5f, 0.5f); dd_test_frame();
    chk("upgrade: a contact that went down with the rows drawn is latched", dd_test_upgrade_generation() != 0);
    gesture_state ug[4];
    gesture_fill(ug, 4, dm_touch_now_ns());
    hold_ms(600); dd_test_frame();
    int un = gesture_fill(ug, 4, dm_touch_now_ns());
    chk("upgrade gesture: held contact remains Touch", un > 0 && ug[0].type == GT_TOUCH);
    up(); dd_test_frame();
    un = gesture_fill(ug, 4, dm_touch_now_ns());
    chk("upgrade gesture: release produces Tap", un > 0 && ug[0].type == GT_TAP);
    chk("upgrade gesture: release callback buys once", dd_test_upgrade_filter());
    chk("upgrade gesture: repeat callback is blocked", !dd_test_upgrade_filter());
    dm_touch mt3 = {0, 0.4f, 0.4f}; dm_touch_set_from(&mt3, 1, DM_CONTACT_MAC_LEFT);
    chk("upgrade: a Mac left click is unchanged", dd_test_upgrade_filter());
    dm_touch_set_from(NULL, 0, DM_CONTACT_MAC_LEFT); dd_test_frame();
    down(0.5f, 0.5f); dd_test_frame(); hold_ms(600); dd_test_frame();
    *(uint8_t *)(img + 0x27dec24) = 1;
    chk("upgrade: a controller-owned contact is unchanged", dd_test_upgrade_filter());
    *(uint8_t *)(img + 0x27dec24) = 0;
    dd_test_upgrade(0);
    chk("upgrade policy off: original behaviour", dd_test_upgrade_filter());
    up(); dd_test_upgrade(1);
    gesture_idle(); dd_test_upgrade_key(17, 3);
    down(0.5f, 0.5f); dd_test_frame(); up(); dd_test_frame();
    chk("prepurchase: guild click is blocked before the tree body", !dd_test_upgrade_tree(17, 3));
    chk("prepurchase: another facility's identifier passes", dd_test_upgrade_tree(18, 3));
    gesture_idle(); dd_test_upgrade_key(17, 3);
    down(0.5f, 0.5f); dd_test_frame(); hold_ms(600); up(); dd_test_frame();
    chk("prepurchase: guild held click enters the tree body", dd_test_upgrade_tree(17, 3));
    chk("prepurchase: repeated tree callback blocked", !dd_test_upgrade_tree(17, 3));

    gesture_idle(); dd_test_upgrade_key(17, 3);
    down(0.5f, 0.5f); dd_test_frame(); up(); dd_test_frame();
    chk("unlock: short tap blocked before initial purchase", !dd_test_unlock(17, 3));
    chk("unlock: unrendered key is blocked by actual tree binding", !dd_test_unlock(17, 999));
    chk("unlock: other facility unchanged", dd_test_unlock(18, 3));
    gesture_idle(); dd_test_upgrade_key(17, 3);
    down(0.5f, 0.5f); dd_test_frame(); hold_ms(600); up(); dd_test_frame();
    chk("unlock: hold release allows initial purchase", dd_test_unlock(17, 3));
    chk("unlock: repeated callback blocked", !dd_test_unlock(17, 3));
    chk("unlock: level callback cannot buy again for same contact", !dd_test_upgrade_tree(17, 3));
    gesture_idle(); dd_test_upgrade_key(17, 3);
    down(0.5f, 0.5f); dd_test_frame(); dm_touch_cancel_from(DM_CONTACT_IOS); up(); dd_test_frame();
    chk("unlock: cancelled contact blocked", !dd_test_unlock(17, 3));

    printf("== %d checks, %d failed (clones %d, releases %d) ==\n", cases, fails, clones, releases);
    if (clones != releases) { printf("FAIL capture leak: %d clones, %d releases\n", clones, releases); fails++; }
    return fails != 0;
}
