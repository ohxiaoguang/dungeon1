// Optional Darkest Dungeon 1.3.0 touch policy. Only CharacterDisplay's combat
// and camping skill bindings plus the uniquely bound Nomad merchandise actions
// are enabled. Roster and other trinket scenes have no guessed fallback.
//
// Qualification is the game's own click: the filters below sit at the first
// instruction of the two native skill toggles (0xe3b5a0 combat, 0xe3a6d0
// camping), which the game only reaches through its own action wrapper
// (0xe39fe0, vtable 0x11956b8 slot +0x30). Both grids are drawn by the one
// ShowSkillGrid renderer, so that wrapper is shared and each grid binds its own
// action class: 0x1195228 ($_5 of ShowCombatSkillGrid) and 0x11955b8 ($_5 of
// ShowCampingSkillGrid). A short contact keeps either click withheld (the
// selection stays as it was); a finger held still for 0.5 s replays it once.
//
// The replay does not enter a toggle directly: it runs the wrapper's own
// operator() with a host-side copy of the wrapper object, so the wrapper's own
// eligibility check (`ldrb [ [this+0x10] + 0x12d ]`, return unless 1) runs against
// the live CharacterDisplay and the wrapper itself makes the call
// `action->vtable[0x30](action, &hero, &skill)` that the game's queue drain makes.
// The action it calls is an owned clone of the action object the game itself
// called, made with that class's own copy slot (+0x10) and released with its own
// release slot (+0x28) - the same pair the wrapper's copy constructor and
// destructor use. Nothing here writes the input mode, the controller flag, the
// GUI, the action vector or any game file.
//
// The merchandise bindings (std::__function::__func of
// Inventory::Display::InventoryButtonInGrid's $_0/$_1, vtables 0x11933a8 and
// 0x1193428, operator() at 0xe18410 / 0xe181f0) are refused for iOS contacts
// before dispatch on both supply pages - the Nomad supply and the DLC/Comet
// page - while focus, tooltip and the renderer stay untouched.
//
// A purchase is the game's own click, never a call of this adapter's. The only
// event this build turns into the pointer's click is a Tap entry (main 0x74c238:
// only the gesture codes 3/4 reach the pointer's click state), and the shop row
// that owns the pointer is the one whose query reports the click, so the click
// arrives at 0xe18410 for the item under the finger with mode 0 (the +0x70
// purchase callable) all by itself. What a held finger needed was that Tap: a
// still finger becomes Press (code 5), whose release is Complete, and this build
// turns Press into the pointer's drag state only (main 0x74c484) - no click.
// While a supply display (the Nomad page or the DLC/Comet page it switches to)
// is drawing its rows, this policy therefore asks
// the recognizer for a hold-tap (dm_touch_hold_tap, hle_touch.c): the still
// finger stays Touch instead of becoming Press, so its release is the Tap the
// game itself clicks with. The request is latched only for a contact that went
// down while those rows were on screen, and dm_touch_hold_tap is off for every
// other screen, so no other panel of this title sees a different gesture stream.
// A Tap made that way carries no double-tap attribute and does not move the
// double-tap clock.
//
// The filter still decides the click: a short tap is withheld (focus only), and a
// lift after >=0.5 s is allowed once per contact - the threshold the recognizer
// uses for Press. Nothing is deferred, no game object is stored between frames
// and the purchase callback is never called by this adapter, so a closed panel
// cannot be bought from and a contact cannot buy twice. The purchase callback
// (vtable 0x117a678 =
// __func<TrinketSupplyDisplay::PreChildrenShowInternal()::$_1, void(unsigned)>,
// operator() 0xc30760; the Comet supply's own at vtable 0x117a7c0,
// __func<CometTrinketSupplyDisplay::PreChildrenShowInternal()::$_1, operator()
// 0xc31e00) keeps the price, stock, capacity and confirm-dialog decisions
// entirely to itself.
//
// Which screen is it? OBS 30 sits where the display builds a row's purchase
// binding (0xe177ac, after the 0x310-byte object of vtable 0x11933a8 received its
// mode/slot word): only a row bound to that vtable with mode 0 and one of the two
// supply callables at +0x70 counts, so the inventory grids and the trinket box MOD
// (other callables) do not arm anything. The Comet supply (the DLC page the same
// nomad wagon switches to) builds its rows through the same builder and binds the
// callable of its own class, so both pages reach the tab the same way.
#include "hle.h"
#include "front.h"
#include <TargetConditionals.h>
#include <stdarg.h>
#include <stddef.h>

#define DD_HOLD_NS 500000000ull   // 0.5 s: the same threshold the recognizer's Press uses
#define DD_WRAPPER 0xe39fe0u      // ShowSkillGrid::$_0::operator()(), vtable 0x11956b8 +0x30
#define DD_WRAPPER_VT 0x11956b8u  // __func<ShowSkillGrid::$_0, void()>
#define DD_SKILL_VT 0x1195228u    // __func<ShowCombatSkillGrid::$_5, bool(Hero*, unsigned)>
#define DD_PANEL_VT 0x11946c0u    // CharacterDisplay
#define DD_TOGGLE 0xe3b5a0u       // the combat action's operator()(Hero**, unsigned*)
#define DD_ELIGIBLE 0x12du        // CharacterDisplay byte the wrapper returns unless 1
#define DD_WRAPPER_LEN 0x60u      // the wrapper object's allocation size (0xe39070)
#define DD_CLONE 0x10u            // action vtable: the class's own copy (0xe3b520)
#define DD_RELEASE 0x28u          // action vtable: the class's own release (0xe3b590)
#define DD_SLOT 0x30u             // both vtables: the callable's operator()
#define DD_CAMP_VT 0x11955b8u     // __func<ShowCampingSkillGrid::$_5, bool(Hero*, unsigned)>
#define DD_CAMP_TOGGLE 0xe3a6d0u  // the camping action's operator()(Hero**, unsigned*)
#define DD_CAMP_CLONE 0xe3a650u   // its copy slot
#define DD_CAMP_RELEASE 0xe3a6c0u // its release slot
#define DD_SHOP_PRIMARY 0xe18410u      // InventoryButtonInGrid::$_0::operator()(), vtable 0x11933a8 +0x30
#define DD_SHOP_PRIMARY_VT 0x11933a8u
#define DD_SHOP_SECONDARY 0xe181f0u    // InventoryButtonInGrid::$_1::operator()(), vtable 0x1193428 +0x30
#define DD_SHOP_SECONDARY_VT 0x1193428u
#define DD_SHOP_PURCHASE_VT 0x117a678u // TrinketSupplyDisplay's purchase callback; +0x30 is 0xc30760
#define DD_SHOP_COMET_VT 0x117a7c0u    // CometTrinketSupplyDisplay's purchase callback; +0x30 is 0xc31e00
#define DD_SHOP_BUILD_SITE 0xe177acu   // OBS 30: `add x0,sp,#0x80`, the row builder just bound a purchase row
#define DD_SHOP_NEAR_NS 300000000ull   // a purchase row was built this recently: the supply display is on screen
#define DD_SHOP_FORGET_NS 1000000000ull // ... and this much silence drops the contact's hold-tap latch again
// The merchandise row's own update (0xe13120) runs per frame and per row from
// the grid's draw path (0xe16e34 -> 0xe171c0 builds the row and calls
// 0xe1788c -> 0xe13120; the element's own update also serves other grids
// through 0xce30f0, 0xcf108c, 0xcfa894). Inside it: 0xe134d0 defaults the click
// byte, 0xe134fc runs the row's interaction query, 0xe13500..0xe13534 copy the
// result to x29-0x98..x29-0x58 (click byte = result+0x40), and the click byte is
// read at 0xe135e8 (tooltip), 0xe13ef8, 0xe14d8c (highlight) and last at
// 0xe15690, where the dispatch to [x26+0x1d0] follows at 0xe15698/0xe156b4.
// OBS 29 sits at 0xe15690, right after the update's `bl 0xe46400`, so one row's
// whole per-frame click state is readable there and the gate replays the original
// ldurb. Nothing is written.
//
// x26 at that point is the update's own first argument (0xe131f4 stores x0 and
// 0xe13384 reloads it): a descriptor each caller builds on *its* stack and fills
// in before the call, not the persistent button. Its +0x1b0 holds a std::function
// (0xd21780 compares its word at +0x20 with the object's own address, i.e. the
// small-buffer layout), so +0x1d0 is that function's __f_ word: null for an empty
// function and otherwise the callable the row dispatches. The row builder copies
// it there from its data object (0xe17588 reads [x22+0x260], 0xe176f0 hands
// +0x1b0 to the copy), while the InventoryButtonInGrid callable this policy knows
// (vtable 0x11933a8, allocated at 0xe17788) is passed to the update as argument
// x2 in a separate std::function at sp+0x6b0. Nothing inside 0xe13120 writes
// +0x1b0/+0x1d0 (the only access is the load at 0xe15698), so the slot names the
// row's own click handler - which is the one datum the diagnostic records.
#define DD_SHOP_ELEM_WRAPPER 0x1d0u   // element+0x1d0: __f_ of the row's click callable at +0x1b0
#define DD_SHOP_FP_RES      0x98u     // x29-0x98: query result byte 0 (the candidate hover byte)
#define DD_SHOP_FP_CLICK    0x58u     // x29-0x58: the click byte 0xe15694 tests
#define DD_SHOP_ELEM_FLAGS  0xe0u     // element+0xe0..+0xe5: the row's own per-frame flags
#define DD_PROBE_MAX        120
// Town roster (section 17/19 of the audit): the click's primary action is queued
// by 0x73b6d0; the details action is the same frame's second std::function. The
// adapter appends that original callable to the game's own action queue.
#define DD_ROSTER_ELEMENT_VT 0x117c8d0u   // TownUI::Panel::RosterElement
#define DD_ROSTER_LIST_VT 0x117cfd0u      // TownUI::Panel::RosterList
#define DD_ROSTER_PRIMARY_VT 0x117cd40u   // __func<RosterElement::PreChildrenShowInternal()::$_1, void()>
#define DD_ROSTER_DETAILS_VT 0x117cdc0u   // ...::$_2, operator() 0xc615b0
#define DD_ROSTER_PRIMARY_OP 0xc61890u
#define DD_ROSTER_DETAILS_OP 0xc615b0u
#define DD_QUEUE 0x257e530u               // the frame's std::vector<std::function<void()>> (begin/end/cap at +0/+8/+16)
#define DD_PUSH 0x717370u                 // its push_back(vector*, const function*); clones and returns the new end
// The observation at 0xc60084 sits inside PreChildrenShowInternal (0xc5c6c0),
// whose prologue is: stp d11,d10,[sp,#-0x80]!; stp x29,x30,[sp,#0x20];
// add x29,sp,#0x20; ...; sub sp,sp,#0xa30. So x29 = S-0x60, sp = S-0xab0 =
// x29-0xa50, and the two std::function objects are at sp+0xa0 (primary) and
// sp+0x70 (details), i.e. x29-0x9b0 and x29-0x9e0 - NOT x29+0xd0. The prologue
// words are validated in dd_validate() before the offset is used.
#define DD_ROSTER_FP_TO_SP 0xa50u

// The hover target the combat grid reports (only used for the cursor handoff).
typedef struct { uintptr_t panel, hero; uint32_t skill; uint64_t generation, seen_frame; } dd_hover;
// One captured click of the game's combat skill action for the current contact.
typedef struct {
    int armed, fired;
    uint64_t generation;
    uintptr_t action,   // the game's own action object at the click (identity only)
              copy,     // our owned clone of it: the only object the replay calls
              panel, hero;
    uint32_t skill;
} dd_hold;
// The wrapper object 0xe39fe0 reads: vtable, the eligibility owner at +0x10, the
// action at +0x40, the hero at +0x50 and the skill at +0x58, in 0x60 bytes.
typedef struct {
    uintptr_t vt, r08, owner, r18, r20, r28, r30, r38, action, r48, hero;
    uint32_t skill, r5c;
} dd_wobj;
_Static_assert(offsetof(dd_wobj, owner) == 0x10, "wrapper owner");
_Static_assert(offsetof(dd_wobj, action) == 0x40, "wrapper action");
_Static_assert(offsetof(dd_wobj, hero) == 0x50, "wrapper hero");
_Static_assert(offsetof(dd_wobj, skill) == 0x58, "wrapper skill");
_Static_assert(sizeof(dd_wobj) == DD_WRAPPER_LEN, "wrapper size");

static module_t *dd_main;
static uintptr_t dd_base;
static pthread_once_t dd_once = PTHREAD_ONCE_INIT;
static pthread_mutex_t dd_mu = PTHREAD_MUTEX_INITIALIZER;   // serializes every gate; no thread identity is assumed
static int dd_valid, dd_camp, dd_shop, dd_roster, dd_ios;   // independently available prepared bindings
static uint64_t dd_frame;
static dd_hover dd_hover_state;
static dd_hold dd_hold_state;
static uintptr_t dd_replay;   // the copy a replay in flight calls; dd_mu guards it
// Host-side per-contact state only (no game pointer): a contact may run one
// game-dispatched purchase click; later clicks of the same contact are refused,
// and a contact the policy saw cancelled/moved/second-fingered/taken is refused
// for the rest of its life (the lift click of a moved contact must not buy).
static uint64_t dd_shop_click_generation, dd_blocked_generation;
static uint64_t dd_roster_fired;   // the contact whose details callable this adapter already appended
static int dd_shop_click_used;
// The Nomad supply display: when its purchase rows were last built, and the
// contact that went down while they were on screen (its release is the Tap the
// game's own click comes from). Host-side values only, no game pointer.
static uint64_t dd_shop_live_ns, dd_tap_generation;
static int dd_build_probe = -1, dd_build_probe_lines;   // DM_DD_SHOP_BUILD=1: how often the display rebuilds its rows
static uint64_t dd_build_probe_frame;
static int dd_diag = -1, dd_diag_lines;
// Nomad shop diagnostic (OBS 29). Default off (DM_DD_SHOP_PROBE=1 enables it);
// read-only, capped. It exists to settle which byte says "this row is under the
// finger" and which callable the row dispatches. Every candidate is recorded
// side by side with the game's own click byte. It is not a fix and writes nothing.
//
// Every layer that can swallow a record counts itself, so a silent run is
// readable instead of ambiguous: gate entries, the contact's source and phase,
// the row's argument sanity, the dispatch slot, and the dispatch callable's own
// vtable. A row whose callable is not one of the two Nomad bindings is recorded
// once per distinct vtable (that number is what identifies the real row class);
// the per-row detail lines stay limited to the two verified bindings.
static int dd_probe = -1, dd_probe_ok;
static int dd_probe_lines, dd_probe_rows, dd_probe_summaries;
static uint64_t dd_probe_generation, dd_probe_summary_frame;   // the contact the table below belongs to
static struct { uintptr_t elem; uint32_t slot; uint64_t sig; } dd_probe_seen[16];
static struct {
    uint64_t hits, ios, other_src, cancelled, not_one, bad_row, no_fn, nomad, other_vt, rows;
} dd_stat;
#define DD_PROBE_VT 6
static struct { uintptr_t vt, disp; uint64_t n; int said; } dd_vt_seen[DD_PROBE_VT];
static int dd_vt_n;
#define DD_SUMMARY_MAX 16
static void dd_probe_summary(const dm_contact_snapshot *s);
static int dd_probe_requested(void) {
    const char *e = getenv("DM_DD_SHOP_PROBE");
    return e && !strcmp(e, "1");
}

static uintptr_t dd_ptr(uintptr_t p) { uintptr_t v; memcpy(&v, (const void *)p, sizeof v); return v; }
static uint32_t dd_word(uintptr_t p) { uint32_t v; memcpy(&v, (const void *)p, sizeof v); return v; }
static uint8_t dd_byte(uintptr_t p) { uint8_t v; memcpy(&v, (const void *)p, sizeof v); return v; }
static int dd_instruction(size_t off, uint32_t word) { return dd_main && off + 4 <= dd_main->size && dd_word((uintptr_t)dd_main->base + off) == word; }
// Only the action classes this policy was verified against: the combat grid's
// $_5 and, once the module carries its filter, the camping grid's $_5.
static int dd_action_ok(uintptr_t action) {
    if (!action) return 0;
    uintptr_t vt = dd_ptr(action);
    return vt == dd_base + DD_SKILL_VT || (dd_camp && vt == dd_base + DD_CAMP_VT);
}
// DM_DD_TOUCH_DEBUG=1 (acceptance diagnostics): every decision once, capped, never a per-frame stream.
static void dd_note(const char *fmt, ...) {
    if (dd_diag < 0) dd_diag = getenv("DM_DD_TOUCH_DEBUG") != NULL;
    if (!dd_diag || dd_diag_lines >= 120) return;
    if (++dd_diag_lines == 120) { LOG("DD touch policy: diagnostic cap reached (%d lines)", dd_diag_lines); return; }
    char b[192]; va_list ap; va_start(ap, fmt); vsnprintf(b, sizeof b, fmt, ap); va_end(ap);
    LOG("DD touch policy: %s", b);
}
// Validation of the prepared module. The town roster action is shared by Mac
// and iOS (its contact source is the only difference); the skill and shop
// bindings are iOS-only. dd_valid is the common core that the roster needs,
// dd_ios marks the iOS-only bindings.
static void dd_validate(void) {
    int sdk = 0;
    dd_main = NULL;
    for (int i = 0; i < g_nmod; i++) {
        module_t *m = &g_mod[i];
        if (!strcmp(m->name, "main") && !strcmp(m->build_id, "ff2bf22565188d11ea0981ee0e2b53ce")) dd_main = m;
        if (!strcmp(m->name, "sdk") && !strcmp(m->build_id, "b33804825108340e4cad9d080a636a3f")) sdk = 1;
    }
    uintptr_t base = dd_main ? (uintptr_t)dd_main->base : 0;
    int core = dd_main && sdk && dd_main->size > 0x27e0898 &&
        gate_obs_present(OBS_DD_TOUCH_FRAME);   // the blocked-generation bookkeeping
    int ios = core &&
        gate_filter_present(FILTER_DD_SKILL, DD_TOGGLE) &&
        gate_obs_present(OBS_DD_SKILL_AFTER) &&
        gate_obs_present(OBS_DD_PANEL_CLOSE) && gate_obs_present(OBS_DD_PANEL_DESTROY) &&
        dd_instruction(0xe3910c, 0x913783e4) && dd_instruction(0xe39114, 0x97e40d9b) &&
        dd_instruction(0xe3911c, 0xaa1403e0) && dd_instruction(0xe3b5a4, 0x6d0323e9) &&
        dd_instruction(0xe39fe0, 0xd10083ff) && dd_instruction(0xe39fe4, 0xa9017bfd) &&
        dd_instruction(0xe39fec, 0xf9400808) && dd_instruction(0xe39ff0, 0x3944b508) &&   // ldr x8,[x0,#0x10]; ldrb w8,[x8,#0x12d]
        dd_instruction(0xe39ff4, 0x7100051f) && dd_instruction(0xe39ffc, 0xf9402808) &&
        dd_instruction(0xe3a008, 0xf9402000) && dd_instruction(0xe3a020, 0xf9401908) &&   // ldr x8,[x8,#0x30]
        dd_instruction(0xe3a024, 0xd63f0100) &&                                            // blr x8
        dd_instruction(0x717370, 0xd10203ff) && dd_instruction(0x717374, 0xa9037bfd) &&
        dd_instruction(0x8b5dd4, 0xa9405113) &&
        dd_ptr(base + DD_WRAPPER_VT + DD_SLOT) == base + DD_WRAPPER &&
        dd_ptr(base + DD_SKILL_VT + DD_CLONE) == base + 0xe3b520 &&
        dd_ptr(base + DD_SKILL_VT + DD_RELEASE) == base + 0xe3b590 &&
        dd_ptr(base + DD_SKILL_VT + DD_SLOT) == base + DD_TOGGLE;
    int camp_gate = ios && gate_filter_present(FILTER_DD_CAMP, DD_CAMP_TOGGLE);
    int camp = camp_gate && dd_main &&
        dd_instruction(0xe3a6d4, 0xa9037bfd) &&
        dd_instruction(0xe3a6e8, 0xf9400033) &&   // ldr x19,[x1]      the hero
        dd_instruction(0xe3a6ec, 0xb9400057) &&   // ldr w23,[x2]      the skill index
        dd_instruction(0xe3a6fc, 0xf9400414) &&   // ldr x20,[x0,#8]   the panel
        dd_ptr(base + DD_CAMP_VT + DD_CLONE) == base + DD_CAMP_CLONE &&
        dd_ptr(base + DD_CAMP_VT + DD_RELEASE) == base + DD_CAMP_RELEASE &&
        dd_ptr(base + DD_CAMP_VT + DD_SLOT) == base + DD_CAMP_TOGGLE;
    ios = ios && (!camp_gate || camp);
    dd_camp = ios && camp;
    dd_shop = ios && gate_filter_present(FILTER_DD_SHOP_PRIMARY, 0xe18410) &&
        gate_filter_present(FILTER_DD_SHOP_SECONDARY, 0xe181f0) &&
        gate_obs_present(OBS_DD_SHOP_BUILD) && gate_obs_present(OBS_DD_SHOP_UPDATE) &&
        dd_instruction(0xe1841c, 0x394c0008) && dd_instruction(0xe18440, 0xf9403808) &&
        dd_instruction(0xe18200, 0xaa0003f3) && dd_instruction(0xe18204, 0xf9409800) &&
        // The row builder 0xe171c0 around OBS 30: the object allocation that
        // precedes it, the mode/slot store it runs after, and the two words that
        // follow it. The gated instruction itself is a branch in a prepared
        // module, so its neighbours pin the site instead.
        dd_instruction(0xe17784, 0x940148bf) &&   // bl operator new(0x310)
        dd_instruction(0xe177a4, 0xf9036bf8) &&   // str x24,[sp,#0x6d0]
        dd_instruction(0xe177a8, 0xf9018308) &&   // str x8,[x24,#0x300]  the mode/slot word
        dd_instruction(0xe177b0, 0x911b83e1) &&   // add x1,sp,#0x6e0
        dd_instruction(0xc30760, 0xd10343ff) &&
        dd_ptr(base + 0x11933a8 + DD_SLOT) == base + 0xe18410 &&
        dd_ptr(base + 0x1193428 + DD_SLOT) == base + 0xe181f0 &&
        dd_ptr(base + 0x117a678 + DD_SLOT) == base + 0xc30760 &&
        dd_ptr(base + 0x117a7c0 + DD_SLOT) == base + 0xc31e00;
    dd_ios = ios;
    // The shop diagnostic's site (OBS 29, 0xe15690). Its neighbours must be the
    // retail words: the dispatch that follows is then the game's own, and the two
    // stack offsets the callback reads are the ones this update uses for its
    // query result and its click byte. It changes no behaviour and is not part of
    // dd_ios.
    dd_probe_ok = gate_obs_present(OBS_DD_SHOP_UPDATE) &&
        dd_instruction(0xe1568c, 0x9400c35d) &&   // bl 0xe46400            (unpatched)
        dd_instruction(0xe15694, 0x36000228) &&   // tbz w8,#0 -> 0xe156d8  (unpatched)
        dd_instruction(0xe15698, 0xf940eb40) &&   // ldr x0,[x26,#0x1d0]   (unpatched)
        dd_instruction(0xe1569c, 0xb4000140) &&   // cbz x0
        dd_instruction(0xe134d0, 0x52802008) &&   // mov w8,#0x100   the click byte's default
        dd_instruction(0xe134d4, 0x781a73a8) &&   // sturh w8,[x29,#-0x59]
        dd_instruction(0xe134fc, 0xd63f0120) &&   // blr x9          the row's own query
        dd_instruction(0xe1350c, 0x395603e8) &&   // ldrb w8,[sp,#0x580]
        dd_instruction(0xe13514, 0x381a83a8);     // sturb w8,[x29,#-0x58]
    dd_valid = core;
    // Town roster (Mac and iOS). A prepared module replaces the instruction at
    // 0xc60084 with a branch to the observation gate, so the original word there
    // must not be checked at runtime: the gate table (OBS 28) and the two
    // neighbouring, unpatched instructions pin the site. The frame prologue
    // words pin the fp->sp offset the callback uses:
    //   c5c6c0 stp d11,d10,[sp,#-0x80]!   sp = S-0x80
    //   c5c6c8 stp x29,x30,[sp,#0x20]     saved x29
    //   c5c6cc add x29,sp,#0x20           x29 = S-0x60
    //   c5c6e4 sub sp,sp,#0xa30           sp = S-0xab0 = x29-0xa50
    // The details std::function is at sp+0x70 (x29-0x9e0), the primary at
    // sp+0xa0 (x29-0x9b0); 0x3f8 is never used as a guard.
    dd_roster = core && gate_obs_present(OBS_DD_ROSTER_CLICK) &&
        dd_instruction(0xc60080, 0x97eb6d94) &&   // bl 0x73b6d0 (unpatched)
        dd_instruction(0xc60088, 0xeb14001f) &&   // cmp x0,x20 (unpatched)
        dd_instruction(0xc5c6c0, 0x6db82beb) && dd_instruction(0xc5c6c8, 0xa9027bfd) &&
        dd_instruction(0xc5c6cc, 0x910083fd) && dd_instruction(0xc5c6e4, 0xd128c3ff) &&
        dd_instruction(0x73b6d0, 0x6db82beb) && dd_instruction(DD_PUSH, 0xd10203ff) &&
        dd_ptr(base + DD_ROSTER_PRIMARY_VT + DD_SLOT) == base + DD_ROSTER_PRIMARY_OP &&
        dd_ptr(base + DD_ROSTER_DETAILS_VT + DD_SLOT) == base + DD_ROSTER_DETAILS_OP;
    dd_base = base;
}
static void dd_init(void) {
    const char *e = getenv("DM_DD_TOUCH_POLICY");
    if (!e || strcmp(e, "1") || strcmp(DM_GAME_ID, "01008F1008DA6000")) return;
    dd_validate();
    dd_probe = dd_probe_requested();   // diagnostic: exact opt-in only
#if TARGET_OS_IPHONE
    // The iOS gesture policy (Press promotion, contact ownership) belongs to the
    // skill and shop bindings; the roster action does not need it.
    dm_touch_policy_activate(dd_valid && dd_ios);
    LOG("DD touch policy: %s (iOS character skills: %s; Nomad merchandise: %s; town roster long-press details: %s)",
        dd_valid ? "enabled, not runtime-validated" : "REFUSED: build/gates/instructions mismatch",
        dd_camp ? "combat and camping" : "combat only, no camping gate in this module",
        dd_shop ? "tap focuses, hold releases the game's own click once" : "unavailable, original behavior",
        dd_roster ? "enabled, not runtime-validated" : "unavailable, original behavior");
    if (dd_probe_ok)
        LOG("DD shop probe: %s (DM_DD_SHOP_PROBE=1 records one line per change inside one iPhone contact; read-only)",
            dd_probe == 1 ? "enabled" : "off");
#else
    // Mac: only the town roster hold is enabled. Its contact snapshot is the
    // same one (MAC_LEFT source, down duration, lift), while the iOS gesture
    // policy is deliberately not activated, so the Mac touch/gesture stream and
    // the pointer bridge keep their original behaviour.
    dm_touch_policy_activate(0);
    LOG("DD touch policy: %s (Mac: town roster long-press details %s; iOS skill/shop policies inactive; original gesture stream retained)",
        dd_valid ? "enabled, not runtime-validated" : "REFUSED: build/gates/instructions mismatch",
        dd_roster ? "enabled, not runtime-validated" : "unavailable, original behavior");
#endif
}
// Every gate runs inside the game's own code, so the caller is whichever guest
// thread executed it; dd_mu serializes the shared policy state instead.
static int dd_ready(void) { pthread_once(&dd_once, dd_init); return dd_valid; }
static int dd_pointer_owner(void) {
    uintptr_t b = dd_base;
    return dd_word(b + 0x27dee2c) == 0 && !*(uint8_t *)(b + 0x27dec24);
}
static int dd_same(const dd_hover *a, const dd_hover *b) {
    return a->panel == b->panel && a->hero == b->hero && a->skill == b->skill && a->generation == b->generation;
}
static int dd_live(const dd_hover *k) {
    // CharacterDisplay has a current hero at +120, opens in state 1 and starts
    // closing in state 2 (+2c0). Destruction/close gates invalidate before use.
    return k->panel && dd_ptr(k->panel) == dd_base + DD_PANEL_VT && dd_ptr(k->panel + 0x120) == k->hero && dd_word(k->panel + 0x2c0) == 1;
}
// Both calls are the action class's own slots, the pair 0xe39fe0's copy
// constructor (0xe39ea4) and destructor (0xe39fb8) use.
static uintptr_t dd_action_clone(uintptr_t action) {
    return ((uintptr_t (*)(uintptr_t))dd_ptr(dd_ptr(action) + DD_CLONE))(action);
}
static void dd_action_release(uintptr_t copy) {
    if (!copy) return;
    if (!dd_action_ok(copy)) { LOG("[RED] DD touch policy: action copy lost its vtable; not releasing it"); return; }
    ((void (*)(uintptr_t))dd_ptr(dd_ptr(copy) + DD_RELEASE))(copy);
}
// The target the replay may still call: our own action copy, the live
// CharacterDisplay it was captured from, and that panel's current eligibility
// byte - the byte the wrapper itself reads at +0x12d.
static int dd_target_live(const dd_hold *h) {
    if (!dd_action_ok(h->copy) || dd_ptr(h->copy + 8) != h->panel) return 0;
    if (!h->panel || dd_ptr(h->panel) != dd_base + DD_PANEL_VT) return 0;
    if (dd_ptr(h->panel + 0x120) != h->hero) return 0;
    if (dd_word(h->panel + 0x2c0) != 1) return 0;
    return dd_byte(h->panel + DD_ELIGIBLE) == 1;
}
static void dd_hold_clear(const char *why, int block) {
    if (dd_hold_state.armed || dd_hold_state.copy) dd_note("%s: capture discarded", why);
    dd_action_release(dd_hold_state.copy);
    uint64_t g = dd_hold_state.generation;
    memset(&dd_hold_state, 0, sizeof dd_hold_state);
    dd_hold_state.generation = g;
    // block: the game's own lift click may not run after this either.
    dd_hold_state.fired = block;
}
static void dd_hold_drop(const char *why) { dd_hold_clear(why, 1); }
// The merchandise bindings: an InventoryButtonInGrid wrapper object whose +0x70
// holds the purchase callback (vtable 0x117a678 for the Nomad supply, 0x117a7c0
// for the Comet supply). The secondary wrapper carries the same bound callback,
// so the identification covers both.
static int dd_shop_binding_ok(uintptr_t action) {
    uintptr_t vt = dd_ptr(action);
    if (vt == dd_base + DD_SHOP_PRIMARY_VT) {
        if (dd_byte(action + 0x300) != 0) return 0;   // mode 1 would dispatch +0xd0, another operation
    } else if (vt != dd_base + DD_SHOP_SECONDARY_VT) return 0;
    uintptr_t callback = dd_ptr(action + 0x70);
    if (!callback) return 0;
    uintptr_t cbvt = dd_ptr(callback);
    return cbvt == dd_base + DD_SHOP_PURCHASE_VT || cbvt == dd_base + DD_SHOP_COMET_VT;
}
// OBS 30 (0xe177ac, `add x0,sp,#0x80` in the row builder 0xe171c0): each
// merchandise row of the Nomad supply display allocates a 0x310-byte binding at
// 0xe17788 (vtable 0x11933a8), stores the mode/slot word at +0x300 and is then
// handed to the row update as that row's click action. Reaching this with the
// purchase binding identifies the display itself: the 0x11933a8 object is only
// ever built here, and its +0x70 callable is a verified TrinketSupplyDisplay or
// CometTrinketSupplyDisplay purchase lambda. Inventory grids and the trinket
// box MOD have other bound callbacks and never mark the screen. The
// callback only records the time: nothing is written into the game.
// Diagnostic (DM_DD_SHOP_BUILD): one line per distinct binding shape the builder
// makes, so the log shows which displays are drawing and with which callable.
// The Nomad supply and the DLC/Comet supply share this builder; their +0x70
// callables are different objects.
static uint64_t dd_census_sig[8]; static int dd_census_n;
static void dd_build_census(uintptr_t binding) {
    if (dd_build_probe < 0) dd_build_probe = getenv("DM_DD_SHOP_BUILD") != NULL;
    if (!dd_build_probe || dd_census_n >= 8) return;
    uintptr_t vt = dd_ptr(binding), cb = dd_ptr(binding + 0x70), cbvt = cb ? dd_ptr(cb) : 0;
    uint64_t sig = (uint64_t)((vt - dd_base) & 0xffffffffu) << 32 ^ (uint64_t)((cbvt - dd_base) & 0xffffffffu) ^ (uint64_t)dd_byte(binding + 0x300) << 60;
    for (int i = 0; i < dd_census_n; i++) if (dd_census_sig[i] == sig) return;
    dd_census_sig[dd_census_n++] = sig;
    LOG("DD shop census: binding vt %#llx mode %u cb %#llx cbvt %#llx", (unsigned long long)(vt - dd_base), dd_byte(binding + 0x300), (unsigned long long)(cb - dd_base), (unsigned long long)(cbvt - dd_base));
}
static void dd_shop_build(const uint64_t *r) {
    if (!dd_ready() || !dd_shop) return;
    uintptr_t binding = r[24];
    if (binding) dd_build_census(binding);
    if (!binding || !dd_shop_binding_ok(binding) || dd_ptr(binding) != dd_base + DD_SHOP_PRIMARY_VT) return;
    if (dd_build_probe < 0) dd_build_probe = getenv("DM_DD_SHOP_BUILD") != NULL;
    if (dd_build_probe && dd_build_probe_frame != dd_frame && dd_build_probe_lines < 300) {
        dd_build_probe_frame = dd_frame; dd_build_probe_lines++;
        LOG("DD supply display: purchase row built at frame %llu (%d logged)", (unsigned long long)dd_frame, dd_build_probe_lines);
    }
    pthread_mutex_lock(&dd_mu);
    dd_shop_live_ns = dm_touch_now_ns();
    pthread_mutex_unlock(&dd_mu);
}
static void dd_frame_tick(const uint64_t *r) {
    (void)r;
    if (!dd_ready()) return;
    pthread_mutex_lock(&dd_mu);
    dd_frame++;
    dm_contact_snapshot s; dm_touch_contact_snapshot(&s);
    dd_probe_summary(&s);   // default off: prints only with DM_DD_SHOP_PROBE
    int ios = s.source == DM_CONTACT_IOS;
    int roster_src = ios || s.source == DM_CONTACT_MAC_LEFT;
    int own = roster_src && dd_pointer_owner();
    if (dd_hold_state.generation != s.generation) {
        int had = dd_hold_state.armed || dd_hold_state.fired || dd_hold_state.copy;
        dd_action_release(dd_hold_state.copy);
        memset(&dd_hold_state, 0, sizeof dd_hold_state);
        dd_hold_state.generation = s.generation;
        if (had) dd_note("contact %llu ended: hold state cleared", (unsigned long long)s.generation);
    }
    if (dd_hover_state.generation != s.generation) memset(&dd_hover_state, 0, sizeof dd_hover_state);
    // The supply display (Nomad page, or the DLC/Comet page behind its switch):
    // while its purchase rows are being built, a
    // contact that goes down on the iPhone gets the recognizer's hold-tap, so its
    // empty-handed release is the Tap the game turns into the item's own click.
    // The latch is per contact and survives a frame without a row build (a
    // purchase dialog or a redraw); a moved/cancelled contact drops it, and so
    // does a second of silence from the display.
    uint64_t now = dm_touch_now_ns();
    if (s.phase == DM_CONTACT_CANCELLED) {
        dd_tap_generation = 0;
    } else if (ios && own && dd_shop && s.count == 1 && s.phase != DM_CONTACT_RELEASED &&
               dd_shop_live_ns && now - dd_shop_live_ns < DD_SHOP_NEAR_NS) {
        if (dd_tap_generation != s.generation)
            dd_note("supply display: contact %llu held in the game's own tap mode (release clicks the item)", (unsigned long long)s.generation);
        dd_tap_generation = s.generation;
    } else if (dd_tap_generation == s.generation && (!dd_shop_live_ns || now - dd_shop_live_ns > DD_SHOP_FORGET_NS)) {
        dd_tap_generation = 0;
    }
    dm_touch_hold_tap(s.generation && dd_tap_generation == s.generation);
    if (!own || s.phase == DM_CONTACT_CANCELLED || (s.count != 1 && s.phase != DM_CONTACT_RELEASED)) {
        // A moved, second-fingered or controller-taken contact may not run the
        // toggle again, not even through the click the game sends on lift. The
        // shop policy never defers a call, so this is only the host-side memory
        // that the contact went bad: its later lift click must not buy either.
        dd_blocked_generation = s.generation;
        memset(&dd_hover_state, 0, sizeof dd_hover_state);
        if (dd_hold_state.armed || dd_hold_state.copy) dd_hold_drop("contact moved, cancelled or taken");
        else dd_hold_state.fired = 1;
    } else if (s.phase == DM_CONTACT_RELEASED) {
        // The hold never fires after the lift; the game's own click on lift is
        // still allowed by the filter when the finger had been down 0.5 s.
        if (dd_hold_state.armed || dd_hold_state.copy) dd_hold_clear("lift", dd_hold_state.fired);
    }
    if (ios && own && s.phase == DM_CONTACT_PRESS && s.count == 1 && dd_hold_state.armed &&
        dd_hold_state.generation == s.generation && dd_target_live(&dd_hold_state)) {
        // The press fires here so the action runs once whether the game reports a
        // click on touch-down, on lift, or both. The wrapper is the game's own
        // function: it re-reads the eligibility byte and makes the action call.
        // The clone leaves dd_hold_state before the lock is dropped, so no other
        // gate can release it while the wrapper is using it.
        uintptr_t copy = dd_hold_state.copy, panel = dd_hold_state.panel, hero = dd_hold_state.hero;
        uint32_t skill = dd_hold_state.skill;
        dd_wobj w; memset(&w, 0, sizeof w);
        w.vt = dd_base + DD_WRAPPER_VT; w.owner = panel; w.action = copy; w.hero = hero; w.skill = skill;
        dd_hold_state.copy = 0; dd_hold_state.armed = 0; dd_hold_state.fired = 1;
        dd_replay = copy;
        dd_note("press (0.5 s): entering the original wrapper once (contact %llu, skill %u)", (unsigned long long)s.generation, skill);
        pthread_mutex_unlock(&dd_mu);
        ((void (*)(void *))(dd_base + DD_WRAPPER))(&w);   // 0xe39fe0: eligibility, then action->vtable[0x30]
        pthread_mutex_lock(&dd_mu);
        dd_replay = 0;
        pthread_mutex_unlock(&dd_mu);
        dd_action_release(copy);   // guest code, so outside the lock
        return;
    }
    if (dd_hold_state.armed && !dd_hold_state.fired && dd_hold_state.generation == s.generation && !dd_target_live(&dd_hold_state)) {
        // Eligibility (or the panel/target) changed while the finger is still
        // down: the click cannot be replayed at all, not even later on this touch.
        dd_hold_drop("eligibility or target withdrawn");
    }
    int live = dd_hover_state.panel && dd_live(&dd_hover_state);
    if (dd_hover_state.panel && (!live || dd_hover_state.seen_frame + 1 < dd_frame)) memset(&dd_hover_state, 0, sizeof dd_hover_state);
    // Coordinate handoff only for a contact the game has itself confirmed on a
    // live CharacterDisplay skill control. Every other screen keeps the game's
    // own pointer path untouched: no tooltip/cursor write outside this target.
    if (live && dd_hover_state.generation == s.generation && (s.count == 1 || s.phase == DM_CONTACT_RELEASED)) {
        float xy[2] = {(float)s.x, (float)s.y};
        memcpy(dd_main->base + 0x27e0890, xy, sizeof xy);
    }
    pthread_mutex_unlock(&dd_mu);
}
static void dd_panel_gone(const uint64_t *r) {
    if (!dd_ready()) return;
    pthread_mutex_lock(&dd_mu);
    if (dd_hover_state.panel == r[0]) memset(&dd_hover_state, 0, sizeof dd_hover_state);
    if (dd_hold_state.panel == r[0] && (dd_hold_state.armed || dd_hold_state.copy)) dd_hold_drop("panel closed or destroyed");
    pthread_mutex_unlock(&dd_mu);
}
static void dd_skill_after(const uint64_t *r) {
    // Hover observation: identifies the skill control the pointer is on, for the
    // cursor handoff only. r[0] is the return of the grid's layout call (a 48-bit
    // object pointer, never a hit flag); it is used exactly as before.
    if (!dd_ready()) return;
    pthread_mutex_lock(&dd_mu);
    dm_contact_snapshot s; dm_touch_contact_snapshot(&s);
    if (s.source != DM_CONTACT_IOS || s.count != 1 || s.phase == DM_CONTACT_CANCELLED || !dd_pointer_owner()) { pthread_mutex_unlock(&dd_mu); return; }
    uintptr_t callable = r[20];
    if (!callable || dd_ptr(callable) != dd_base + DD_WRAPPER_VT) { pthread_mutex_unlock(&dd_mu); return; }
    uintptr_t action = dd_ptr(callable + 0x40);
    if (!dd_action_ok(action)) { pthread_mutex_unlock(&dd_mu); return; }
    dd_hover k = {.panel = dd_ptr(action + 8), .hero = dd_ptr(callable + 0x50),
                  .skill = dd_word(callable + 0x58), .generation = s.generation};
    if (!(r[0] & 1) || !dd_live(&k)) { if (dd_same(&dd_hover_state, &k)) memset(&dd_hover_state, 0, sizeof dd_hover_state); pthread_mutex_unlock(&dd_mu); return; }
    if (dd_hover_state.generation != s.generation) memset(&dd_hover_state, 0, sizeof dd_hover_state);
    if (dd_hover_state.panel && !dd_same(&dd_hover_state, &k)) { memset(&dd_hover_state, 0, sizeof dd_hover_state); pthread_mutex_unlock(&dd_mu); return; }
    dd_hover_state = k; dd_hover_state.seen_frame = dd_frame;
    pthread_mutex_unlock(&dd_mu);
}
static int dd_skill_filter(const uint64_t *r) {
    if (!dd_ready()) return 1;   // off, Mac, or an unsupported build: the original call and arguments
    pthread_mutex_lock(&dd_mu);
    dm_contact_snapshot s; dm_touch_contact_snapshot(&s);
    uintptr_t action = r[0], hero = r[1] ? dd_ptr(r[1]) : 0;
    uint32_t skill = r[2] ? dd_word(r[2]) : 0;
    int ios = s.source == DM_CONTACT_IOS, allow = 1;
    if (!ios || !dd_pointer_owner()) {
        allow = 1;   // the game's own controller state, any non-iOS source, or a finger the game owns itself: unchanged
    } else if (dd_replay && action == dd_replay) {
        allow = 1;   // our own replay, entered through the original wrapper
    } else if (!dd_action_ok(action)) {
        // An action class this policy was not verified against: the game's own
        // behaviour, never a swallowed click.
        allow = 1;
        dd_note("toggle of an unrecognised action class: original call");
    } else {
        allow = 0;
        if (dd_hold_state.generation != s.generation) {
            dd_action_release(dd_hold_state.copy);
            memset(&dd_hold_state, 0, sizeof dd_hold_state);
            dd_hold_state.generation = s.generation;
        }
        if (!dd_hold_state.fired && (s.count == 1 || s.phase == DM_CONTACT_RELEASED) && dd_action_ok(action)) {
            if (s.phase == DM_CONTACT_PRESS) {
                allow = 1; dd_hold_state.fired = 1;
                dd_note("press: the game's own click ran the toggle once (contact %llu)", (unsigned long long)s.generation);
            } else if (s.phase == DM_CONTACT_RELEASED && s.down_ns && dm_touch_now_ns() - s.down_ns >= DD_HOLD_NS) {
                allow = 1; dd_hold_state.fired = 1;
                dd_note("lift after a 0.5 s hold: the game's own click ran the toggle once (contact %llu)", (unsigned long long)s.generation);
            } else if ((s.phase == DM_CONTACT_DOWN || s.phase == DM_CONTACT_HOLDING) && !dd_hold_state.armed) {
                uintptr_t panel = dd_ptr(action + 8);
                dd_hover k = {.panel = panel, .hero = hero, .skill = skill, .generation = s.generation};
                uintptr_t copy = 0;
                // Arm only with a target the game itself resolved and that is
                // still live and eligible; the copy is the class's own clone of
                // the very action object the game just called.
                if (dd_live(&k) && dd_byte(panel + DD_ELIGIBLE) == 1 &&
                    (copy = dd_action_clone(action)) != 0 &&
                    dd_action_ok(copy) && dd_ptr(copy) == dd_ptr(action) && dd_ptr(copy + 8) == panel) {
                    dd_hold_state.armed = 1; dd_hold_state.generation = s.generation;
                    dd_hold_state.action = action; dd_hold_state.copy = copy;
                    dd_hold_state.panel = panel; dd_hold_state.hero = hero; dd_hold_state.skill = skill;
                    dd_note("contact down: toggle withheld, hold armed (contact %llu, skill %u)", (unsigned long long)s.generation, skill);
                } else {
                    dd_action_release(copy);
                    dd_hold_state.fired = 1;
                    dd_note("click withheld and not replayable: target not live, not eligible or not copyable");
                }
            } else {
                dd_note("toggle withheld (phase %d, count %d, armed %d, fired %d)", s.phase, s.count, dd_hold_state.armed, dd_hold_state.fired);
            }
        }
    }
    pthread_mutex_unlock(&dd_mu);
    return allow;
}
static int dd_shop_filter(const uint64_t *r) {
    if (!dd_ready() || !dd_shop) return 1;
    dm_contact_snapshot s; dm_touch_contact_snapshot(&s);
    if (s.source != DM_CONTACT_IOS || !dd_pointer_owner()) return 1;
    uintptr_t action = r[0];
    if (!action || !dd_shop_binding_ok(action)) return 1;   // not an identified supply binding: original behaviour
    int primary = dd_ptr(action) == dd_base + DD_SHOP_PRIMARY_VT;
    // The bound merchandise click is withheld before dispatch. Only the game's
    // own live click is ever allowed through, and only once per contact: on the
    // lift of a contact held >=0.5 s, which is the Tap the recognizer's hold-tap
    // mode gives the game for a still finger over the supply display's rows (a
    // build that dispatches a click while the finger is down is covered too). A
    // short tap, a moved/second-fingered/cancelled contact and the secondary
    // binding stay withheld. No game object is stored between frames and the
    // purchase callback is never called by the adapter, so a closed panel cannot
    // be bought from.
    pthread_mutex_lock(&dd_mu);
    if (dd_shop_click_generation != s.generation) { dd_shop_click_generation = s.generation; dd_shop_click_used = 0; }
    int allow = 0;
    // The contact's own phase is the authority here, not only the frame tick's
    // memory of it: a move, a cancel or a second finger in the same frame as the
    // release must not launder the click into a purchase.
    if (s.phase == DM_CONTACT_CANCELLED || (dd_blocked_generation && dd_blocked_generation == s.generation)) {
        dd_note("moved, cancelled or second-fingered contact: the game's click is withheld (contact %llu)", (unsigned long long)s.generation);
        pthread_mutex_unlock(&dd_mu);
        return 0;
    }
    if (!dd_shop_click_used && primary && (s.count == 1 || s.phase == DM_CONTACT_RELEASED)) {
        if (s.phase == DM_CONTACT_PRESS) {
            allow = 1; dd_shop_click_used = 1;
            dd_note("press (>=0.5 s): the game's own click runs the purchase binding once (contact %llu)", (unsigned long long)s.generation);
        } else if (s.phase == DM_CONTACT_RELEASED && s.down_ns && dm_touch_now_ns() - s.down_ns >= DD_HOLD_NS) {
            allow = 1; dd_shop_click_used = 1;
            dd_note("lift after a >=0.5 s hold: the game's own click runs the purchase binding once (contact %llu)", (unsigned long long)s.generation);
        } else if (s.phase == DM_CONTACT_RELEASED) {
            dd_note("short tap: the game's click is withheld, focus only");
        }
    }
    if (!allow && (s.phase == DM_CONTACT_DOWN || s.phase == DM_CONTACT_HOLDING))
        dd_note("contact down: purchase click withheld; the lift after >=0.5 s is the game's own click");
    pthread_mutex_unlock(&dd_mu);
    return allow;
}
// Nomad shop diagnostic (OBS 29). Read-only: it records the game's own click
// byte next to every candidate "row under the finger" byte, so one tap and one
// hold on the same row settle which byte is the hover/current-target flag. It is
// enabled only by DM_DD_SHOP_PROBE (default off), only inside a single iOS
// contact, one line per row per change, capped.
//
// Every layer that can swallow a record counts itself (dd_stat) and a periodic
// summary prints the counters, so a run with no row line says which layer
// stopped it instead of leaving it to a guess. The dispatch callable's own vtable
// is the one datum the retail instructions cannot supply: the row hands the
// update a std::function (element+0x1b0, its __f_ word at +0x1d0) and dispatches
// through it at 0xe156b0, so that word - not a constant - names the real row
// class. A row whose callable is neither Nomad binding records that vtable once
// and then only counts; the per-row detail stays limited to the two bindings.
// Absence of a row line is NOT evidence that a byte is clear.
static uint64_t dd_probe_sig(int click, int res, int mode, const uint8_t *f, const dm_contact_snapshot *s, int owner) {
    uint64_t v = (uint64_t)(click & 1) | (uint64_t)(res & 0xffu) << 1 |
                 (uint64_t)(s->phase & 7) << 9 | (uint64_t)(s->count & 3) << 12 |
                 (uint64_t)(owner & 1) << 14 | (uint64_t)(mode & 1) << 15;
    for (int i = 0; i < 6; i++) v |= (uint64_t)f[i] << (16 + i * 8);
    return v;
}
static void dd_probe_vt_name(uintptr_t vt, char *b, size_t n) {
    if (dd_main && vt >= dd_base && vt < dd_base + dd_main->size)
        snprintf(b, n, "+%#zx", (size_t)(vt - dd_base));
    else snprintf(b, n, "%#zx outside", (size_t)vt);
}
// One line per distinct dispatch vtable that is not a Nomad binding: the number
// is what tells the real row class from the one this policy was written against.
// The element's other two slots are read too - the game itself dereferences each
// of them (0xe13400 for +0x170, 0xe155f8 for +0x110, 0xe156b0 for +0x1d0) - so
// the line names every callable the row holds, whatever slot the binding is in.
static uintptr_t dd_probe_slot(uintptr_t elem, uintptr_t off) {
    uintptr_t p = dd_ptr(elem + off);
    return p < 0x10000 ? 0 : dd_ptr(p);
}
static void dd_probe_vt_line(uintptr_t elem, uintptr_t fn, uintptr_t vt, const dm_contact_snapshot *s, int click, int res) {
    uintptr_t v170 = dd_probe_slot(elem, 0x170), v110 = dd_probe_slot(elem, 0x110);
    uint64_t key = (uint64_t)vt ^ ((uint64_t)v170 << 1) ^ ((uint64_t)v110 << 2) ^ (uint64_t)(click & 1);
    int i = 0;
    for (; i < dd_vt_n; i++) if (dd_vt_seen[i].vt == key) { dd_vt_seen[i].n++; if (dd_vt_seen[i].said) return; dd_vt_seen[i].said = 1; break; }
    if (i == dd_vt_n) {
        if (dd_vt_n >= DD_PROBE_VT) return;
        dd_vt_seen[dd_vt_n].vt = key; dd_vt_seen[dd_vt_n].disp = vt; dd_vt_seen[dd_vt_n].n = 1; dd_vt_seen[dd_vt_n].said = 1;
        dd_vt_n++;
    }
    if (dd_probe_lines >= DD_PROBE_MAX) return;
    dd_probe_lines++;
    char b[24], b2[24], b3[24];
    dd_probe_vt_name(vt, b, sizeof b); dd_probe_vt_name(v170, b2, sizeof b2); dd_probe_vt_name(v110, b3, sizeof b3);
    LOG("DD shop probe: row %#llx dispatch %#llx vt %s (+0x170 vt %s, +0x110 vt %s) is not a Nomad binding (gen %llu phase %d count %d click %d res0 %02x)",
        (unsigned long long)elem, (unsigned long long)fn, b, b2, b3,
        (unsigned long long)s->generation, s->phase, s->count, click, res);
}
// The periodic summary: every 25 frames up to frame 1000 and every 100 after
// that, at most DD_SUMMARY_MAX lines, so a long session cannot flood the log.
static void dd_probe_summary(const dm_contact_snapshot *s) {
    if (dd_probe != 1 || dd_probe_summaries >= DD_SUMMARY_MAX) return;
    uint64_t every = dd_frame <= 1000 ? 25 : 100;
    if (dd_frame < 25 || dd_frame % every || dd_frame == dd_probe_summary_frame) return;
    dd_probe_summary_frame = dd_frame;
    dd_probe_summaries++; dd_probe_lines++;   // its own budget, DD_SUMMARY_MAX
    char v[120]; size_t m = 0; v[0] = 0;
    for (int i = 0; i < dd_vt_n && m + 32 < sizeof v; i++) {
        char b[24]; dd_probe_vt_name(dd_vt_seen[i].disp, b, sizeof b);
        m += (size_t)snprintf(v + m, sizeof v - m, "%s%s x%llu", i ? ", " : "", b, (unsigned long long)dd_vt_seen[i].n);
    }
    LOG("DD shop probe: summary frame %llu gen %llu phase %d count %d src %d | gate %llu ios %llu other-source %llu cancelled %llu not-one %llu bad-row %llu no-fn %llu nomad %llu other-vt %llu rows %llu | dispatch vt %s",
        (unsigned long long)dd_frame, (unsigned long long)s->generation, s->phase, s->count, s->source,
        dd_stat.hits, dd_stat.ios, dd_stat.other_src, dd_stat.cancelled, dd_stat.not_one,
        dd_stat.bad_row, dd_stat.no_fn, dd_stat.nomad, dd_stat.other_vt, dd_stat.rows, dd_vt_n ? v : "none seen");
}
static void dd_shop_update(const uint64_t *r) {
    if (dd_probe < 0) dd_probe = dd_probe_requested();
    if (!dd_probe || !dd_ready() || !dd_probe_ok) return;
    dd_stat.hits++;
    dm_contact_snapshot s; dm_touch_contact_snapshot(&s);
    if (s.source != DM_CONTACT_IOS) { dd_stat.other_src++; return; }   // the iPhone touch, not the Mac's left button
    dd_stat.ios++;
    if (s.phase == DM_CONTACT_CANCELLED) { dd_stat.cancelled++; return; }   // a moved/second-fingered contact has no target
    if (s.count != 1 && s.phase != DM_CONTACT_RELEASED) { dd_stat.not_one++; return; }
    if (dd_probe_generation != s.generation) {   // a new contact: its rows are recorded from scratch
        dd_probe_generation = s.generation;
        memset(dd_probe_seen, 0, sizeof dd_probe_seen);
    }
    uintptr_t elem = r[26], fp = r[29];
    if (elem < 0x10000 || (elem & 7) || fp < 0x10000) { dd_stat.bad_row++; return; }
    uintptr_t fn = dd_ptr(elem + DD_SHOP_ELEM_WRAPPER);
    if (fn < 0x10000) { dd_stat.no_fn++; return; }
    uintptr_t vt = dd_ptr(fn);   // the word the game itself loads at 0xe156b0
    uint8_t f[6];
    for (int i = 0; i < 6; i++) f[i] = dd_byte(elem + DD_SHOP_ELEM_FLAGS + (uintptr_t)i);
    int click = dd_byte(fp - DD_SHOP_FP_CLICK) & 1, res = dd_byte(fp - DD_SHOP_FP_RES), own = dd_pointer_owner();
    int primary = vt == dd_base + DD_SHOP_PRIMARY_VT, secondary = vt == dd_base + DD_SHOP_SECONDARY_VT;
    if (!primary && !secondary) { dd_stat.other_vt++; dd_probe_vt_line(elem, fn, vt, &s, click, res); return; }
    dd_stat.nomad++;
    // Both bindings are the game's own 0x310-byte objects (allocated at 0xe17788 /
    // 0xe177d0), so +0x300/+0x304/+0x70 are inside them; 0xe18410 reads exactly
    // these three words. The mode and the bound callback are recorded rather than
    // used as a filter, so a row that is the binding but not a purchase is visible.
    uint8_t mode = primary ? dd_byte(fn + 0x300) : 0;
    uintptr_t cb = dd_ptr(fn + 0x70), cbvt = cb ? dd_ptr(cb) : 0;
    uint32_t item_slot = dd_word(fn + 0x304);
    uint64_t sig = dd_probe_sig(click, res, mode, f, &s, own) ^
                   (uint64_t)(cbvt - (uintptr_t)dd_base) * 0x9E3779B97F4A7C15ull;   // a rebound callback is a change
    int slot = 0;
    for (int i = 0; i < 16; i++) {
        if (dd_probe_seen[i].elem == elem && dd_probe_seen[i].slot == item_slot) {
            if (dd_probe_seen[i].sig == sig) return;             // unchanged: no line
            slot = i;
            break;
        }
        if (!dd_probe_seen[i].elem) { slot = i; break; }
    }
    dd_probe_seen[slot].elem = elem; dd_probe_seen[slot].slot = item_slot; dd_probe_seen[slot].sig = sig;
    dd_stat.rows++;
    if (dd_probe_lines >= DD_PROBE_MAX) {
        if (dd_probe_lines == DD_PROBE_MAX) {
            dd_probe_lines++;
            LOG("DD shop probe: cap reached (%d lines); later changes are not recorded", DD_PROBE_MAX);
        }
        return;
    }
    dd_probe_lines++; dd_probe_rows++;
    char vb[24]; dd_probe_vt_name(cbvt, vb, sizeof vb);
    float xy[2]; memcpy(xy, (const void *)(dd_base + 0x27e0890), sizeof xy);
    LOG("DD shop probe: row %#llx slot %u gen %llu host (%d,%d) ui (%.1f,%.1f) dwell %llu ms phase %d count %d owner %d click %d res0 %02x flags %02x %02x %02x %02x %02x %02x ptr %02x %s mode %d cb %#llx cbvt %s",
        (unsigned long long)elem, item_slot, (unsigned long long)s.generation, s.x, s.y, xy[0], xy[1],
        (unsigned long long)(s.down_ns ? (dm_touch_now_ns() - s.down_ns) / 1000000ull : 0ull),
        s.phase, s.count, own, click, res, f[0], f[1], f[2], f[3], f[4], f[5],
        dd_byte(dd_base + 0x27e0901), primary ? "primary" : "secondary", mode, (unsigned long long)cb, vb);
}
// Town roster: the per-element dispatch (0xc60084) runs every frame with the
// element in x24 and the dispatch frame in x29. The game's own click on the
// element has just queued its primary action (0x73b6d0's bit-8 branch); that
// queued primary is the same-frame live target. For a held contact the adapter
// appends the *original* details callable - the same frame's second
// std::function at sp+0x70 = x29-0x9e0 - to the game's own action queue
// with the game's own push_back (0x717370), so the normal drain runs it
// (0xc615b0 -> 0xcb59a0 -> RosterList::ShowCharacterDisplay). Nothing is stored
// across frames, no double-tap state is written and no UI function is called
// directly. A moved/cancelled/second-fingered/controller-taken contact, a
// source other than the iPhone touch or the Mac left button, and a control
// whose element or list is not the live town roster are refused. The 0x3f8
// byte is deliberately NOT a guard: it is 0 on real interactive elements
// (audit 19.1).
static void dd_roster_click(const uint64_t *r) {
    if (!dd_ready() || !dd_roster) return;
    dm_contact_snapshot s; dm_touch_contact_snapshot(&s);
    // Both the iPhone touch source and the Mac's left-button source (the only
    // one the Mac front publishes as a touch); never a controller or script
    // source. mode/auto are only read, never written, so the pointer bridge is
    // untouched.
    if (s.source != DM_CONTACT_IOS && s.source != DM_CONTACT_MAC_LEFT) return;
    if (!dd_pointer_owner()) return;
    if (s.phase != DM_CONTACT_PRESS && s.phase != DM_CONTACT_RELEASED) return;
    if (s.count != 1 && s.phase != DM_CONTACT_RELEASED) return;
    if (!s.down_ns || dm_touch_now_ns() - s.down_ns < DD_HOLD_NS) return;
    uintptr_t elem = r[24], fp = r[29];
    if (!elem || !fp) return;
    pthread_mutex_lock(&dd_mu);
    if ((dd_blocked_generation && dd_blocked_generation == s.generation) || dd_roster_fired == s.generation) {
        pthread_mutex_unlock(&dd_mu);
        return;
    }
    // The live element and its list; membership is re-checked exactly as the
    // details callable itself would need it.
    int ok = dd_ptr(elem) == dd_base + DD_ROSTER_ELEMENT_VT;
    uintptr_t list = ok ? dd_ptr(elem + 0x80) : 0;
    ok = ok && list && dd_ptr(list) == dd_base + DD_ROSTER_LIST_VT;
    if (ok) {
        uintptr_t b = dd_ptr(list + 0x90), e = dd_ptr(list + 0x98);
        int member = 0;
        if (b && e > b)
            for (uintptr_t p = b; p < e && p - b < 0x40 * 64; p += 0x40)
                if (dd_ptr(p) == elem) { member = 1; break; }
        ok = member;
    }
    // The two std::function objects this frame built for the element: the
    // details one at sp+0x70 and the primary at sp+0xa0. fp is the frame's x29,
    // and the validated prologue makes sp = fp - 0xa50. The old x29+0xd0 guess
    // pointed into the caller's stack and is refused by construction.
    uintptr_t sp = fp - DD_ROSTER_FP_TO_SP;
    uintptr_t details = sp + 0x70, primary = sp + 0xa0;
    ok = ok && dd_ptr(details) == dd_base + DD_ROSTER_DETAILS_VT &&
         dd_ptr(details + 0x20) == details && dd_ptr(details + 8) == elem &&
         dd_ptr(primary) == dd_base + DD_ROSTER_PRIMARY_VT &&
         dd_ptr(primary + 0x20) == primary && dd_ptr(primary + 8) == elem;
    // The queue must have just received this element's primary, and must not
    // already hold the details action (that is the game's own double click).
    uintptr_t begin = dd_ptr(dd_base + DD_QUEUE), end = dd_ptr(dd_base + DD_QUEUE + 8);
    int details_queued = 0;
    if (ok && begin && end >= begin + 0x30) {
        for (uintptr_t e = begin; e < end && e - begin < 0x30 * 64; e += 0x30) {
            uintptr_t f = dd_ptr(e + 0x20);
            if (f && dd_ptr(f) == dd_base + DD_ROSTER_DETAILS_VT) { details_queued = 1; break; }
        }
    }
    uintptr_t last = (begin && end >= begin + 0x30) ? end - 0x30 : 0;
    uintptr_t pf = last ? dd_ptr(last + 0x20) : 0;
    ok = ok && !details_queued && pf && dd_ptr(pf) == dd_base + DD_ROSTER_PRIMARY_VT && dd_ptr(pf + 8) == elem;
    if (!ok) {
        pthread_mutex_unlock(&dd_mu);
        return;
    }
    dd_roster_fired = s.generation;
    pthread_mutex_unlock(&dd_mu);
    // The game's own push_back clones the callable into the queue; the source
    // stays in the live frame and the game's epilogue destroys it. Guest code
    // runs outside the lock.
    ((uintptr_t (*)(uintptr_t, uintptr_t))(dd_base + DD_PUSH))(dd_base + DD_QUEUE, details);
    dd_note("roster: appended the original details callable for a held contact (generation %llu)",
            (unsigned long long)s.generation);
}
#ifdef DM_DD_TOUCH_TEST
// Policy tests (dm/host/tests/t_dd_touch.c) drive these gates with a fake module
// image, a fake wrapper at 0xe39fe0 and a fake action class, in the order the
// guest runs them. Test builds only.
void dd_test_roster(int on) { dd_roster = on; }
// Runs the same validation the real init runs (module table, gate table, words,
// vtables) so a test exercises the prepared-module checks instead of only
// setting dd_valid by hand.
int dd_test_validate(void) { dd_validate(); return dd_roster; }
int dd_test_valid(void) { return dd_valid; }
int dd_test_ios(void) { return dd_ios; }
void dd_test_roster_click(uintptr_t elem, uintptr_t fp) { uint64_t r[32] = {0}; r[24] = elem; r[29] = fp; dd_roster_click(r); }
void dd_test_init(uintptr_t base) { dd_base = base; dd_valid = 1; dd_camp = dd_shop = dd_roster = 1; dd_replay = 0; dd_shop_click_generation = dd_blocked_generation = dd_roster_fired = 0; dd_shop_click_used = 0; dd_shop_live_ns = dd_tap_generation = 0; memset(&dd_hold_state, 0, sizeof dd_hold_state); memset(&dd_hover_state, 0, sizeof dd_hover_state); }
void dd_test_shop(int on) { dd_shop = on; }
int dd_test_shop_filter(uintptr_t action) { uint64_t r[32] = {action}; return dd_shop_filter(r); }
// OBS 30: the site passes the row's freshly built binding in x24.
void dd_test_shop_build(uintptr_t binding) { uint64_t r[32] = {0}; r[24] = binding; dd_shop_build(r); }
uint64_t dd_test_tap_generation(void) { return dd_tap_generation; }
uint64_t dd_test_shop_live(void) { return dd_shop_live_ns; }
// The shop diagnostic: driven like the guest's gate, with the row in x26 and the
// frame pointer in x29.
void dd_test_shop_update(uintptr_t elem, uintptr_t fp) { uint64_t r[32] = {0}; r[26] = elem; r[29] = fp; dd_shop_update(r); }
int dd_test_probe_ok(void) { return dd_probe_ok; }
int dd_test_probe_lines(void) { return dd_probe_lines; }
int dd_test_probe_rows(void) { return dd_probe_rows; }
int dd_test_probe_requested(void) { return dd_probe_requested(); }
void dd_test_probe_frame(uint64_t f) { dd_frame = f; }
void dd_test_probe(int on) {
    dd_probe = on; dd_probe_lines = dd_probe_rows = dd_probe_summaries = 0; dd_probe_generation = dd_probe_summary_frame = 0;
    memset(dd_probe_seen, 0, sizeof dd_probe_seen);
    memset(&dd_stat, 0, sizeof dd_stat); memset(dd_vt_seen, 0, sizeof dd_vt_seen); dd_vt_n = 0;
}
void dd_test_enable(int on) { dd_valid = on; }
void dd_test_camp(int on) { dd_camp = on; }
void dd_test_frame(void) { dd_frame_tick(NULL); }
int dd_test_holds(void) { return dd_hold_state.copy != 0; }
int dd_test_filter(uintptr_t action, uintptr_t hero, uint32_t skill) {
    uintptr_t h = hero; uint32_t k = skill; uint64_t r[32] = {0};
    r[0] = action; r[1] = (uintptr_t)&h; r[2] = (uintptr_t)&k;
    return dd_skill_filter(r);
}
void dd_test_panel(uintptr_t panel) { uint64_t r[32] = {0}; r[0] = panel; dd_panel_gone(r); }
#endif
__attribute__((constructor)) static void dd_touch_register(void) {
    gate_obs_set(OBS_DD_TOUCH_FRAME, dd_frame_tick);
    gate_obs_set(OBS_DD_PANEL_CLOSE, dd_panel_gone); gate_obs_set(OBS_DD_PANEL_DESTROY, dd_panel_gone);
    gate_obs_set(OBS_DD_SKILL_AFTER, dd_skill_after);
    gate_obs_set(OBS_DD_ROSTER_CLICK, dd_roster_click);
    gate_obs_set(OBS_DD_SHOP_UPDATE, dd_shop_update);   // diagnostic only; inert unless DM_DD_SHOP_PROBE
    gate_obs_set(OBS_DD_SHOP_BUILD, dd_shop_build);     // the Nomad supply display is drawing its purchase rows
    gate_filter_set(FILTER_DD_SKILL, dd_skill_filter);
    gate_filter_set(FILTER_DD_CAMP, dd_skill_filter);   // the same decision covers both grids' toggles
    gate_filter_set(FILTER_DD_SHOP_PRIMARY, dd_shop_filter);
    gate_filter_set(FILTER_DD_SHOP_SECONDARY, dd_shop_filter);
}
