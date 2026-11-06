// Hero status panel: game-thread collector and thread-safe shared snapshot.
//
// The Buff rows are produced by the GAME'S OWN tooltip code, not re-implemented
// here. Nothing in this file translates effect ids, guesses number formats,
// merges rows by label or drops effects. Per sample the collector, on the game
// thread, replays the tray-tooltip recipe the game itself uses
// (main+0xcd400c .. main+0xcd748c, Build-ID gated):
//
//   1. collect Buff::Instance* = raw element + 8, exactly what the game
//      stores at main+0xcd4080 / 0xcd7398 when it builds the tray list. The
//      tray functor's polarity split (buff icon vs debuff icon) is not
//      applied: it drops whole stat kinds the tray icons render without
//      text, and the panel wants every effect;
//   2. call main+0xcd8540 — the game's aggregate -> admission -> localize ->
//      format routine.
//      That head is the std::vector<char[0x100]> the game's line append
//      (main+0x703ef0) expects: begin/end/capacity, nothing else is read;
//      inside, main+0xdeba10 aggregates with its own identity fields and
//      merge rule, and main+0xdebdc0 writes the finished localized line
//      through the game's own lookup main+0x98fdb0 and formatter
//      main+0x993000;
//   4. copy the finished lines into the snapshot under the mutex.
//
// The line vector is kept between samples and only its end pointer rewinds:
// the elements are plain char[0x100], so rewinding is the vector's own clear
// and the capacity is allocated once by the game's allocator.
//
// Guest data links (main-image offsets, all verified on 1.3.0 builds
// ff2bf22565188d11ea0981ee0e2b53ce / b33804825108340e4cad9d080a636a3f):
//   main+0xd6b428  ldr x10,[0xb1a27000,#0x190]   global game singleton
//   main+0xd6b430  ldr x8, [x10,#0x3e8]          current selected hero Actor*
//   Actor+0x460 / +0x468  raw buff vector, element step 0x1d8
//   the tooltip chain's Buff::Instance* is raw element + 8, so its +0x48
//   (amount) / +0x4c (turns) / +0x50 (duration_type) sit at raw +0x50 /
//   +0x54 / +0x58 — the values the live dumps confirmed.
#include "hle.h"
#include "dm.h"
#include "front.h"
#include "dd_hero.h"
#include <TargetConditionals.h>
#include <pthread.h>
#include <sys/mman.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define DD_HERO_MAIN_BUILD "ff2bf22565188d11ea0981ee0e2b53ce"
#define DD_HERO_SDK_BUILD  "b33804825108340e4cad9d080a636a3f"

#define DD_HERO_SINGLETON   0xb1a27190ull
#define DD_HERO_SINGLETON_ACTOR 0x3e8ull
#define DD_HERO_VEC_BEGIN   0x460ull
#define DD_HERO_VEC_END     0x468ull
#define DD_HERO_ELEM_STEP   0x1d8ull
#define DD_HERO_SAMPLE_EVERY 6          // ~10 Hz at 60 fps; keeps the gate cheap

// The player's own look path: tapping a hero portrait opens the game's
// CharacterDisplay sheet, which holds the hero it is showing at +0x120 (the
// field the touch policy's dd_live validates). The skill-grid renderer's
// shared wrapper (drawn while the sheet is open) reaches the same panel
// through its action's +8. Both are observed read-only; nothing is injected.
#define DD_FMT              0x993000ull // the game's own printf-style formatter
#define DD_PANEL_VT         0x11946c0ull // CharacterDisplay
#define DD_PANEL_HERO       0x120ull     // the hero the sheet is showing
#define DD_WRAPPER_VT       0x11956b8ull // __func<ShowSkillGrid::$_0, void()>
#define DD_SKILL_VT         0x1195228ull // the combat grid's action class
#define DD_CAMP_VT          0x11955b8ull // the camping grid's action class
#define DD_BLOCK_COUNT      0x128cull    // remaining block uses (tray case 0x16, main+0xcd4cbc)
#define DD_BLOCK_ARG        0x11a4ull    // the case's other formatter argument

// Hero identity and bars, on the same Actor (verified by differential
// observation on two heroes with different values, 2026-11-05):
#define DD_HERO_NAME        0x8ull      // localized hero name, C string
#define DD_HERO_HP          0x80ull     // float current HP
#define DD_HERO_STRESS      0x1274ull   // float current stress
#define DD_HERO_STRESS_MAX  0xab8ull    // float stress cap (200)
#define DD_HERO_GROUP       0x5cull     // element word: 1 = combat effect, 5 = quirk
#define DD_HERO_CLASS_KEY   "heroClass" // property-bag key -> length-prefixed class id
#define DD_AFFLICTION_KEY   "affliction_type_id" // property-bag key -> overstress id string

// The original chain, as main-image offsets (see the audit, rounds 6 and 9):
#define DD_ORC_AGGREGATE    0xdeba10ull // aggregate + de-dup the instance list
#define DD_ORC_LINE_FULL    0xdec330ull // one full row: name + amount + duration
#define DD_ORC_FREE         0xe69a20ull // the game's vector deallocate(begin, bytes)
#define DD_ORC_ROW_STEP     0x1d0ull    // aggregated row size
#define DD_ORC_LOOKUP       0x98fdb0ull // the game's localization lookup


static pthread_mutex_t g_hero_lock = PTHREAD_MUTEX_INITIALIZER;
static dd_hero_snapshot_t g_hero_snap;
static uint64_t g_hero_generation;
static uint64_t g_hero_sample;
static uint64_t g_hero_tick;
static _Atomic int g_hero_enabled = -1;   // -1 = not read yet
static int g_hero_cleared_when_off;

// Read guest memory from the game thread's gate callback. A mach memory call is
// not usable here (the existing HLE readers all use a plain memcpy for the same
// reason), so each page is first proved present with mincore() and only then
// dereferenced. A page that is not mapped makes the sample invalid instead of
// touching it, which is what keeps a destroyed Actor from crashing the host.
static int hero_page_ok(uint64_t a) {
    char present = 0;
    return mincore((void *)(uintptr_t)(a & ~0xfffull), 0x1000, &present) == 0;
}

static uint64_t g_hero_base_log;

static int hero_rd(uint64_t a, void *out, size_t n) {
    if (a < 0x1000 || !n || a + n < a) return 0;
    if (!hero_page_ok(a) || !hero_page_ok(a + n - 1)) {
        static int once;
        if (!once) { once = 1; LOG("hero panel: page %#llx unmapped (base %#llx)", (unsigned long long)a, (unsigned long long)g_hero_base_log); }
        return 0;
    }
    memcpy(out, (const void *)(uintptr_t)a, n);
    return 1;
}

// The buff icon tooltip builder (main+0xcd3d10) receives the Actor* it describes
// in x1, once per icon per frame. OBS 35 records it so the panel can tell which
// unit the game is drawing that frame. Read-only: the gate replays the original
// prologue, and nothing here writes guest memory or registers.
static _Atomic uint64_t g_gate_actor;

static void hero_actor_gate(const uint64_t *r) {
    atomic_store_explicit(&g_gate_actor, r[1], memory_order_relaxed);
}

__attribute__((constructor)) static void hero_gate_register(void) {
    gate_obs_set(OBS_DD_HERO_ACTOR, hero_actor_gate);
}

int dm_hero_panel_enabled(void) {
    int e = atomic_load_explicit(&g_hero_enabled, memory_order_acquire);
    if (e >= 0) return e;
    const char *v = getenv("DM_DD_HERO_PANEL");
    e = (v && atoi(v) != 0) ? 1 : 0;
    LOG("hero panel: switch DM_DD_HERO_PANEL=%s -> %s", v ? v : "(unset)", e ? "on" : "off");
    atomic_store_explicit(&g_hero_enabled, e, memory_order_release);
    return e;
}

void dm_hero_snapshot_take(dd_hero_snapshot_t *out) {
    if (!out) return;
    pthread_mutex_lock(&g_hero_lock);
    *out = g_hero_snap;
    pthread_mutex_unlock(&g_hero_lock);
}

static void hero_note(const char *why) {
    static const char *last;
    if (last == why) return;
    last = why;
    LOG("hero panel: %s", why);
}

static void hero_publish_invalid(void) {
    pthread_mutex_lock(&g_hero_lock);
    if (g_hero_snap.valid) {
        memset(&g_hero_snap, 0, sizeof g_hero_snap);
        g_hero_snap.generation = ++g_hero_generation;
    } else {
        g_hero_snap.valid = 0;
    }
    pthread_mutex_unlock(&g_hero_lock);
}

static void hero_publish(const dd_hero_snapshot_t *built) {
    pthread_mutex_lock(&g_hero_lock);
    dd_hero_snapshot_t prev = g_hero_snap;
    prev.generation = 0;
    prev.sample = 0;
    dd_hero_snapshot_t now = *built;
    if (memcmp(&prev, &now, sizeof now) != 0) g_hero_generation++;
    now.generation = g_hero_generation;
    now.sample = ++g_hero_sample;
    g_hero_snap = now;
    pthread_mutex_unlock(&g_hero_lock);
}

typedef void *(*dd_aggregate_fn)(void *out_vec, void **inst_begin, void **inst_end,
                                void *actor);
typedef void (*dd_line_fn)(char *out_0x100, void *row, void *actor, uint32_t w3);
typedef void (*dd_free_fn)(void *p, uint64_t bytes);

// The game's localization lookup returns the text pointer in x0 and a packed
// length/flags word in x1; a 16-byte struct return maps both registers (AAPCS).
typedef struct { void *ptr; uint64_t packed; } dd_loc_ret;
typedef dd_loc_ret (*dd_loc_fn)(const char *key);
// 0x993000: the game's printf-style formatter. x0 is the 16-byte text
// descriptor the game builds from the lookup result ({ptr, w1, (x1>>32)&0xff},
// exactly the stores at main+0xcd4ce0..0xcd4cec), x1 the 0x100 output buffer,
// w2 the capacity, then the integer arguments in w3, w4, ...
typedef struct { void *ptr; uint32_t w1; uint32_t w8; } dd_fmt_desc;
typedef void (*dd_fmt_fn)(const dd_fmt_desc *d, char *out, uint32_t cap,
                          uint32_t a3, uint32_t a4);

// ---- The player's own look target --------------------------------------
// Tapping a hero portrait opens the game's CharacterDisplay sheet; the sheet
// holds the hero it shows at +0x120. While the sheet is open its skill grid
// draws through the shared wrapper (the touch policy's OBS 24 site), and when
// it closes the panel-close gates fire (OBS 26/27) with the panel in x0. Both
// paths end here and pin that hero as the panel's inspection target — the
// look object stays fixed until the player picks another hero or the target
// dies / the raid ends. Read-only throughout: no input is injected, no game
// memory written, and the acting hero at G+0x3e8 is never used as the pin.
static _Atomic uint64_t g_inspect_actor;   // the pinned look target; 0 = none yet
static _Atomic uint64_t g_inspect_vt;      // its vtable at pin time (anti page-reuse)

static int hero_module(uintptr_t *base, uint64_t *size) {
    for (int i = 0; i < g_nmod; i++) {
        module_t *m = &g_mod[i];
        if (!strcmp(m->name, "main") && !strcmp(m->build_id, DD_HERO_MAIN_BUILD)) {
            if (m->size <= DD_ORC_LINE_FULL + 0x400) return 0;
            *base = (uintptr_t)m->base;
            *size = m->size;
            return 1;
        }
    }
    return 0;
}

// The acceptance the tick applies to the fallback actor too: the vtable lives
// in the main image and the object still carries its localized name. The
// vtable is returned so the pin can require it to stay identical — a freed
// and reused object would not keep it.
static int hero_actor_plausible(uintptr_t base, uint64_t size, uint64_t actor,
                                uint64_t *vt_out) {
    uint64_t vt = 0;
    if (!hero_rd(actor, &vt, 8) || vt < base || vt >= base + size) return 0;
    char nm[16];
    if (!hero_rd(actor + DD_HERO_NAME, nm, sizeof nm) || !nm[0]) return 0;
    if (vt_out) *vt_out = vt;
    return 1;
}

static void hero_pin_inspect(uintptr_t base, uint64_t size, uint64_t hero) {
    uint64_t vt = 0;
    if (!hero || !hero_actor_plausible(base, size, hero, &vt)) return;
    atomic_store_explicit(&g_inspect_vt, vt, memory_order_relaxed);
    uint64_t prev = atomic_exchange_explicit(&g_inspect_actor, hero,
                                             memory_order_acq_rel);
    if (prev != hero)
        LOG("hero panel: inspection target pinned (actor %#llx%s)",
            (unsigned long long)hero, prev ? ", player re-selected" : "");
}

// ---- Player-tap-gated selection follow ----------------------------------
// Tapping a hero's portrait makes the game expand that hero's card — the
// game's selected-hero slot (G+0x3e8) changes to them, whether or not the
// character sheet opens. The panel follows that player-driven change and
// never the automatic one at a turn boundary: the new value is pinned only
// while a short window after a touch lift is open, and only if the slot
// changed since the lift (turn switches carry no tap of their own).
static struct { uint64_t gen, down_ns; int x, y, live; } g_tap_prev;
static uint64_t g_tap_lift_ns, g_tap_baseline, g_sel_last;
static uintptr_t g_base_cache;
static uint64_t g_size_cache;
static int g_tap_armed;
#define DD_TAP_WINDOW_NS 800000000ull   // the window after a touch lift
#define DD_TAP_MAX_NS    500000000ull   // a shorter contact is a Tap

static void hero_tap_track(void) {
    dm_contact_snapshot s;
    dm_touch_contact_snapshot(&s);
    uint64_t now = dm_touch_now_ns();
    if (s.generation != g_tap_prev.gen) {   // the previous contact just ended
        if (g_tap_prev.live && g_tap_prev.down_ns &&
            now - g_tap_prev.down_ns < DD_TAP_MAX_NS) {
            g_tap_lift_ns = now;
            g_tap_baseline = g_sel_last;    // the selection as it was before the tap
            g_tap_armed = 1;
        }
        g_tap_prev.gen = s.generation;
        g_tap_prev.live = s.count > 0;
        g_tap_prev.down_ns = s.down_ns;
        g_tap_prev.x = s.x; g_tap_prev.y = s.y;
    } else if (s.count > 0) {               // the live contact's latest position
        g_tap_prev.x = s.x; g_tap_prev.y = s.y;
    }
}


void dd_hero_note_character_panel(uint64_t panel) {
    uintptr_t base; uint64_t size;
    if (!dm_hero_panel_enabled() || !panel || !hero_module(&base, &size)) return;
    uint64_t vt = 0;
    if (!hero_rd(panel, &vt, 8) || vt != base + DD_PANEL_VT) return;
    uint64_t hero = 0;
    if (!hero_rd(panel + DD_PANEL_HERO, &hero, 8)) return;
    hero_pin_inspect(base, size, hero);
}

void dd_hero_note_skill_wrapper(uint64_t callable) {
    uintptr_t base; uint64_t size;
    if (!dm_hero_panel_enabled() || !callable || !hero_module(&base, &size)) return;
    uint64_t vt = 0;
    if (!hero_rd(callable, &vt, 8) || vt != base + DD_WRAPPER_VT) return;
    uint64_t action = 0;
    if (!hero_rd(callable + 0x40, &action, 8) || !action) return;
    if (!hero_rd(action, &vt, 8) ||
        (vt != base + DD_SKILL_VT && vt != base + DD_CAMP_VT)) return;
    uint64_t panel = 0;
    if (!hero_rd(action + 8, &panel, 8) || !panel) return;
    if (!hero_rd(panel, &vt, 8) || vt != base + DD_PANEL_VT) return;
    uint64_t hero = 0;
    if (!hero_rd(panel + DD_PANEL_HERO, &hero, 8)) return;
    hero_pin_inspect(base, size, hero);
}

// Strips the game's colour protocol (<c> + 6-byte colour code + </c>; the
// game's own renderer interprets it, our UI draws plain text).
static void hero_strip(char *dst, size_t cap, const char *line) {
    size_t k = 0;
    for (size_t t = 0; line[t] && t < 0x100; ) {
        if (line[t] == '<' && t + 9 <= 0x100 && line[t + 1] == 'c' && line[t + 2] == '>') {
            t += 9;
            continue;
        }
        if (line[t] == '<' && t + 4 <= 0x100 && !memcmp(line + t, "</c>", 4)) {
            t += 4;
            continue;
        }
        if (k + 1 >= cap) break;
        dst[k++] = line[t++];
    }
    dst[k] = 0;
}

// One sample of the original chain. Everything below runs on the game thread
// with the game's own objects; no guest pointer outlives the call.
//
// Only the tray's combat group is passed (Instance+0x54 == 1; quirk effects
// live in group 5, deathsdoor-style states in others — the game's own group
// index). The tray functor's polarity split is deliberately not applied: it
// drops whole stat kinds the tray icons render without text. What remains is
// main+0xcd8540's own admission, aggregation and formatting.
//
// The chain is run twice with the game's own two line formats — w6=0
// (name + amount through main+0xdebdc0) and w6=1 (duration through
// main+0xdec330) — and the two rows of each aggregated effect are joined, so
// a timed effect reads like the game's own tooltip: "<name> (剩余N回合)".
static int g_hero_dbg;                   // one-shot diagnostics, first samples only
static int g_hero_dbg_n = -1;            // from DM_DD_HERO_DEBUG, default 2
static int hero_dbg_limit(void) {
    if (g_hero_dbg_n < 0) {
        const char *v = getenv("DM_DD_HERO_DEBUG");
        g_hero_dbg_n = v && atoi(v) > 0 ? atoi(v) : 2;
    }
    return g_hero_dbg_n;
}

// DoT rows (bleed / poison / ...) are the one case the aggregated chain
// cannot finish: their name key ("buff_stat_tooltip_hp_dot_bleed" and friends)
// is MISSING from the game's own tables — verified by calling the game's
// lookup for every stat-table entry under the debugger. The game itself never
// renders those rows as text; it shows an icon plus an apply-toast whose text
// comes from the tray format keys below, which DO exist. For such a row the
// panel formats the game's own tray template with the row's own aggregated
// numbers, e.g. "2伤害下次行动(2回合)".
static const char *hero_tray_format_key(const char *stat_name) {
    static const struct { const char *suf, *key; } map[] = {
        {"hp_dot_bleed", "tray_icon_tooltip_bleed_format"},
        {"hp_dot_poison", "tray_icon_tooltip_poison_format"},
        {"stress_dot", "tray_icon_tooltip_stress_dot_format"},
        {"hp_dot_heal", "tray_icon_tooltip_hp_heal_dot_format"},
        {"shuffle_dot", "tray_icon_tooltip_shuffle_dot_format"},
    };
    for (size_t i = 0; i < sizeof map / sizeof map[0]; i++)
        if (!strcmp(map[i].suf, stat_name)) return map[i].key;
    return NULL;
}

// Substitute the first two %-style integers of the game's own template with
// the row's aggregated amount and remaining turns.
static void hero_fmt_two(char *out, size_t cap, const char *tmpl, int amount, int turns) {
    size_t k = 0;
    int which = 0;
    for (size_t t = 0; tmpl[t] && k + 1 < cap; t++) {
        if (tmpl[t] == '%' && which < 2) {
            size_t adv = 0;
            int negative = 0;
            if (tmpl[t + 1] == 'd') adv = 1;
            else if (tmpl[t + 1] == '+' && tmpl[t + 2] == 'd') { adv = 2; negative = 1; }
            if (adv) {
                int v = which == 0 ? amount : turns;
                if (negative && v > 0) k += (size_t)snprintf(out + k, cap - k, "+%d", v);
                else k += (size_t)snprintf(out + k, cap - k, "%d", v);
                which++;
                t += adv;
                continue;
            }
        }
        out[k++] = tmpl[t];
    }
    out[k] = 0;
}

// The tray's own membership predicate (main+0xcd8fc0), replayed read-only
// with the game's own tables. This — not the group word — decides which
// effects get a tray icon, so it is what the panel shows. The tray splits
// the effects into a buff and a debuff icon by polarity; the panel unions
// both, so the polarity test collapses away.
#define DD_STAT_TABLE       0xb185e5e4ull
#define DD_GROUP_TABLE      0xb186068cull
static int hero_tray_predicate(const uint8_t *elem, uintptr_t base) {
    uint32_t stat;
    memcpy(&stat, elem + 8, sizeof stat);            // elem+0x08 = stat index
    uint8_t se[0x58];
    if (!hero_rd(base + DD_STAT_TABLE + (uint64_t)stat * 0x58, se, sizeof se))
        return 0;
    if (se[0x56] & 1) return 1;                      // stat always shown
    if (elem[0x1d2] & 1) return 1;                   // element flag
    if (stat == 0x2c) return 1;                      // stat 44: always
    if (se[0x45] & 1) return 1;
    // The remaining check routes the effect to the buff or the debuff icon by
    // sign; the panel unions both icons, so every effect that reaches here is
    // decided by the group flag alone.
    uint32_t group;
    memcpy(&group, elem + 0x5c, sizeof group);
    uint8_t gflag;
    if (!hero_rd(base + DD_GROUP_TABLE + (uint64_t)group * 0x4c + 0x48, &gflag, 1))
        return 0;
    return gflag & 1;
}

static void hero_original_lines(uintptr_t base, uint64_t actor,
                                uint64_t vbegin, uint64_t vend,
                                dd_hero_snapshot_t *s) {
    // Buff::Instance* = raw element + 8, exactly what the game collects at
    // main+0xcd4080 / 0xcd7398. The tray's polarity functor is not applied:
    // it splits effects into the 0xd/0xe icons and drops whole stat kinds.
    // The panel instead runs the game's own aggregate + per-row formatter and
    // keeps every combat effect, so a row the tray icons render without text
    // (stat id 5, "damage next action") still shows its game-written line.
    void *inst[DD_HERO_MAX_BUFFS];
    size_t n = 0;
    int dbg = g_hero_dbg < hero_dbg_limit();
    for (uint64_t e = vbegin; e + DD_HERO_ELEM_STEP <= vend && n < DD_HERO_MAX_BUFFS;
         e += DD_HERO_ELEM_STEP) {
        uint8_t raw[DD_HERO_ELEM_STEP];
        if (!hero_rd(e, raw, sizeof raw)) return;   // vector changed under us
        if (!hero_tray_predicate(raw, base)) continue;
        inst[n++] = (void *)(uintptr_t)(e + 8);
    }
    if (dbg) LOG("hero panel: collected %zu combat instances", n);
    if (!n) { g_hero_dbg++; return; }

    // w3 of the row formatter: the game passes "the Actor has a raid/combat
    // object" (main+0xcd7458). Outside combat the Actor's HP reads 0.
    uint64_t vt = 0;
    if (!hero_rd(actor, &vt, 8) || !vt) return;
    void *(*has_raid)(void *) = NULL;
    memcpy(&has_raid, (void *)(uintptr_t)(vt + 0x20), sizeof has_raid);
    if (!has_raid) return;
    uint32_t w5 = has_raid((void *)(uintptr_t)actor) != 0;
    s->has_battle = w5 != 0;

    dd_aggregate_fn aggregate = (dd_aggregate_fn)(base + DD_ORC_AGGREGATE);
    dd_line_fn line_full = (dd_line_fn)(base + DD_ORC_LINE_FULL);
    dd_free_fn free_fn = (dd_free_fn)(base + DD_ORC_FREE);
    dd_loc_fn lookup = (dd_loc_fn)(base + DD_ORC_LOOKUP);
    int lookup_ok = lookup != NULL;

    // main+0xdeba10 zeroes the vector itself and builds it (it may allocate);
    // main+0xcd8540's own tail frees the rows and the array with main+0xe69a20,
    // replicated below so nothing leaks per frame.
    struct dd_gvec { void *begin, *end, *cap; } agg;
    memset(&agg, 0, sizeof agg);
    aggregate(&agg, inst, inst + n, (void *)(uintptr_t)actor);

    size_t count = 0;
    if (agg.begin && agg.end > agg.begin)
        count = (size_t)((uint8_t *)agg.end - (uint8_t *)agg.begin) / DD_ORC_ROW_STEP;
    if (dbg) {
        LOG("hero panel: aggregated %zu rows from %zu instances", count, n);
        g_hero_dbg++;
    }
    for (size_t i = 0; i < count && s->buff_count < DD_HERO_MAX_BUFFS; i++) {
        void *row = (uint8_t *)agg.begin + i * DD_ORC_ROW_STEP;
        // The duration formatter (w6=1 in main+0xcd8540) already renders the
        // whole row: name + amount + the remaining turns, e.g.
        // "终曲：+30%伤害(7回合)". One 0x100 buffer per row.
        char line[0x100];
        memset(line, 0, sizeof line);
        line_full(line, row, (void *)(uintptr_t)actor, w5 & 1);
        if (dbg) LOG("hero panel: raw[%zu] = \"%s\"", i, line);
        // Strip the game's colour protocol (hero_strip above).
        dd_hero_buff_t *out = &s->buffs[s->buff_count];
        hero_strip(out->line, sizeof out->line, line);
        if (!out->line[0]) continue;         // the game wrote an empty line
        // DoT rows (bleed / poison / ...) arrive with an embedded nested key
        // ("[<buff_stat_tooltip_hp_dot_bleed>](2回合)"): their name key is
        // missing from the game's own tables, so neither the game's tooltip
        // renderer nor this panel can resolve it. The game displays such an
        // effect as a tray icon plus an apply-toast whose text comes from the
        // tray format keys (tray_icon_tooltip_bleed_format =
        // "%d伤害下次行动(%d回合)") — format that with the row's own numbers.
        if (strchr(out->line, '<')) {
            uint32_t stat = 0;
            memcpy(&stat, row, sizeof stat);          // row+0x00 = stat index
            char stat_name[32] = "";
            if (hero_rd(base + 0xb185e5e4ull + (uint64_t)stat * 0x58, stat_name, 32)) {
                stat_name[31] = 0;
                const char *tkey = hero_tray_format_key(stat_name);
                if (tkey && lookup_ok) {
                    const char *tmpl = (const char *)lookup(tkey).ptr;
                    if (tmpl && hero_page_ok((uintptr_t)tmpl)) {
                        float amount;
                        memcpy(&amount, (uint8_t *)row + 0x48, sizeof amount);
                        int32_t turns;
                        memcpy(&turns, (uint8_t *)row + 0x4c, sizeof turns);
                        if (amount == amount && amount > -1e5f && amount < 1e5f &&
                            turns >= 0) {
                            char tmpl2[0x100];
                            size_t tn = 0;
                            while (tn + 1 < sizeof tmpl2 && tmpl[tn]) {
                                tmpl2[tn] = tmpl[tn]; tn++;
                            }
                            tmpl2[tn] = 0;
                            hero_fmt_two(out->line, sizeof out->line, tmpl2,
                                         (int)(amount + (amount >= 0 ? 0.5f : -0.5f)),
                                         turns);
                        }
                    }
                }
            }
            if (strchr(out->line, '<')) continue;   // still unrenderable: never raw markup
        }
        // Two real buffs can render to the very same line (the Finale's
        // damage-low and damage-high both read "终曲：+30%伤害(6回合)"), and
        // the tray shows them as ONE icon — keep the first copy.
        int dup = 0;
        for (int r = 0; r < s->buff_count; r++) {
            if (!strcmp(s->buffs[r].line, out->line)) { dup = 1; break; }
        }
        if (dup) continue;
        if (dbg) LOG("hero panel: row[%zu] = \"%s\"", i, out->line);
        out->negative = strchr(out->line, '-') != NULL;   // display colour only
        s->buff_count++;
    }

    // Free exactly what main+0xcd8540's tail frees: each row's two nested
    // vectors (row+0x158/0x168 and row+0x170/0x180), then the row array.
    if (agg.begin) {
        for (uint8_t *r = (uint8_t *)agg.end; r > (uint8_t *)agg.begin; ) {
            r -= DD_ORC_ROW_STEP;
            void *b1 = *(void **)(r + 0x170), *e1 = *(void **)(r + 0x180);
            if (b1) {
                *(void **)(r + 0x178) = b1;
                free_fn(b1, (uint64_t)((uint8_t *)e1 - (uint8_t *)b1));
            }
            void *b2 = *(void **)(r + 0x158), *e2 = *(void **)(r + 0x168);
            if (b2) {
                *(void **)(r + 0x160) = b2;
                free_fn(b2, (uint64_t)((uint8_t *)e2 - (uint8_t *)b2));
            }
        }
        free_fn(agg.begin,
                (uint64_t)((uint8_t *)agg.cap - (uint8_t *)agg.begin));
    }
}

// Hero name and bars, from the same Actor the buff chain runs on.
//   +0x8            the localized hero name, a C string the game keeps there
//   +0x80 / +0x1274 / +0xab8   current HP, current stress, stress cap (floats;
//                   verified against the on-screen bars of three heroes with
//                   different values)
//   property bag    "heroClass" -> length-prefixed class id. Where the bag
//                   nodes sit is session-dependent (see hero_bag_scan_tick);
//                   the budgeted, name-anchored scan keeps them found. The
//                   localized class name comes from the game's own lookup with
//                   the key shape the game itself uses at roster load. The max
//                   HP is not stored in the Actor at all (the game computes it
//                   from the class config plus modifiers), so the panel shows
//                   the current HP only.
// The value after the key: the node padding varies between instances (a plain
// u32 length on one hero, a stray byte first on another), so accept the first
// identifier-shaped run and let the caller's whitelist decide.
static void hero_bag_id(const uint8_t *buf, size_t cap, size_t key_len,
                        char *out, size_t out_cap);

// The anchor test: this hero's name string (as a property-bag VALUE — the
// Actor's own +0x8 name field does not count) sits within 0x2000 bytes before
// the node. This is what binds a bag node to its hero when the bags of
// different heroes interleave in one allocator region.
static int hero_bag_anchored(uint64_t actor, uint64_t node, const char *name,
                             size_t nlen) {
    uint64_t from = node > actor + 0x2000 ? node - 0x2000 : actor;
    uint8_t chk[0x2008];
    size_t cap = (size_t)(node - from) + 8;
    if (cap > sizeof chk) cap = sizeof chk;
    if (!hero_rd(from, chk, cap)) return 0;
    for (size_t j = 0; j + nlen <= cap; j++) {
        if (memcmp(chk + j, name, nlen) != 0) continue;
        if (from + j == actor + DD_HERO_NAME) continue;   // the Actor's own field
        return 1;
    }
    return 0;
}

// The property-bag record scan, budgeted and name-anchored. The bag nodes
// drift with the session's allocator layout — observed +0x2835..+0x2954 from
// the Actor in one session and beyond 0x40000 (a different vm region) in
// another. Guards:
//   - budget: at most 12 windows (≈28 KB) per tick, spread over frames — an
//     earlier version scanned megabytes inside the frame a sheet opened and
//     froze the game, and a second one ran the anchor test on EVERY byte
//     offset (2 mincore syscalls each, thousands per window) which stalled
//     every frame the scan was alive;
//   - anchor: a node is only accepted when THIS hero's name string (as a bag
//     value — not the Actor's own +0x8 field) sits within 0x2000 bytes before
//     it, which is what binds a node to its hero;
//   - gate: the scan runs only while the hero's stress can plausibly reach
//     the overstress threshold (≥ 60) — at low stress there is nothing to
//     find, so an unstressed party costs nothing.
// The window grows across passes (0x20000, 0x40000, 0x80000). The scan fills
// the affliction-node cache for the current hero.
static struct {
    char name[DD_HERO_STR_MAX];   // the hero the scan state belongs to
    uint64_t aff_node;
    uint64_t cursor;              // next window offset to scan (or retry stamp)
    int pass;                     // 0..2 -> window 0x20000 << pass
    int done;                     // the scan reached the window's end
} g_bag;

static void hero_bag_scan_restart(void) {
    g_bag.cursor = 0;
    g_bag.pass = 0;
    g_bag.done = 0;
}

static void hero_bag_scan_tick(uint64_t actor, const char *name, int dbg) {
    if (strcmp(name, g_bag.name) != 0) {   // a different hero: restart the state
        snprintf(g_bag.name, sizeof g_bag.name, "%s", name);
        g_bag.aff_node = 0;
        hero_bag_scan_restart();
    }
    if (g_bag.done) {
        // The node holds: nothing to look for. Otherwise re-sweep every 15 s —
        // the game can materialize the bag later (opening the hero's own sheet
        // is one such moment).
        if (g_bag.aff_node || dm_touch_now_ns() < g_bag.cursor)
            return;
        hero_bag_scan_restart();
        g_bag.cursor = dm_touch_now_ns() + 15000000000ull;
        g_bag.done = 1;
        return;
    }
    uint64_t extent = actor + (0x20000ull << g_bag.pass);
    size_t nlen = strlen(name) + 1;
    if (nlen > 16) nlen = 15;   // long names anchor by their first 15 bytes
    int budget = 12;
    while (budget-- > 0) {
        if (g_bag.cursor + 0x900 > extent) {   // this pass is over
            if (g_bag.pass < 2) { g_bag.pass++; g_bag.cursor = 0; }
            else {
                g_bag.done = 1;
                g_bag.cursor = dm_touch_now_ns() + 15000000000ull;   // re-sweep stamp
            }
            return;
        }
        uint8_t win[0x900];
        if (hero_rd(actor + g_bag.cursor, win, sizeof win)) {
            for (size_t j = 0; j + 26 <= sizeof win; j++) {
                // key bytes first, and only then the (costly) anchor test —
                // the anchor on every byte offset was a per-frame stall
                if (memcmp(win + j, DD_AFFLICTION_KEY,
                           sizeof DD_AFFLICTION_KEY) != 0)
                    continue;
                uint64_t node = actor + g_bag.cursor + j;
                if (!hero_bag_anchored(actor, node, name, nlen)) continue;
                g_bag.aff_node = node;
                if (dbg) LOG("hero panel: bag scan affliction node @ +0x%llx",
                             (unsigned long long)(node - actor));
                break;
            }
        }
        g_bag.cursor += 0x700;
        if (g_bag.aff_node) return;   // found: the sweep is done
    }
}

static void hero_identity(uintptr_t base, uint64_t actor, int dbg, dd_hero_snapshot_t *s) {
    (void)base;
    char name[DD_HERO_STR_MAX];
    if (hero_rd(actor + DD_HERO_NAME, name, sizeof name)) {
        name[sizeof name - 1] = 0;
        if (name[0]) snprintf(s->name, sizeof s->name, "%s", name);
    }

    float f;
    if (hero_rd(actor + DD_HERO_HP, &f, 4) && f == f && f >= 0 && f < 1e5f) {
        s->has_hp = 1; s->hp = (int)(f + 0.5f);
    }
    if (hero_rd(actor + DD_HERO_STRESS, &f, 4) && f == f && f >= 0 && f < 1e5f) {
        s->has_stress = 1; s->stress = (int)(f + 0.5f);
    }
    if (hero_rd(actor + DD_HERO_STRESS_MAX, &f, 4) && f == f && f > 0 && f < 1e5f) {
        s->stress_max = (int)(f + 0.5f);
    }

    // The overstress state's node lives in the hero's property map. Where
    // those nodes sit is session-dependent — see hero_bag_scan_tick. The scan
    // runs only while the stress can plausibly reach the threshold (≥ 60), so
    // an unstressed party costs nothing; the name/class rows were removed by
    // request, and with them the class scan and its per-sample lookup.
    if (s->name[0] && s->has_stress && s->stress >= 60)
        hero_bag_scan_tick(actor, s->name, dbg);
}

// ---- Special states (read from their own structures, never the Buff chain) ----

// (a) The block status: the tray's own case 0x16 (main+0xcd4cbc) replayed
// read-only, both of its branches. The game gates on Actor+0x128c: while it
// is >= 1 it formats tray_icon_tooltip_health_damage_blocks_duration_format
// with (w3 = Actor+0x11a4, w4 = the count) — pool text "剩余%d次护体隔挡";
// below that it formats tray_icon_tooltip_health_damage_blocks_format with
// (w3 = Actor+0x11a4) — pool text "%d次护体隔挡". Live evidence: after the
// Shieldbreaker's Puncture the witness read cnt(+0x128c)=0, arg(+0x11a4)=2,
// so the else branch is the common one and the count lives in +0x11a4.
static void hero_block_line(uintptr_t base, uint64_t actor, int dbg, dd_hero_snapshot_t *s) {
    uint32_t cnt = 0, arg = 0;
    if (!hero_rd(actor + DD_BLOCK_COUNT, &cnt, 4) ||
        !hero_rd(actor + DD_BLOCK_ARG, &arg, 4))
        return;
    // Rate-limited field witness: one line per change (combat start/end, a
    // block consumed or granted). This is what ties the two fields to the
    // game's own block state without a debugger attached.
    static uint32_t prev_cnt = 0xffffffffu, prev_arg;
    static uint64_t prev_actor;
    if (cnt != prev_cnt || arg != prev_arg || actor != prev_actor) {
        prev_cnt = cnt; prev_arg = arg; prev_actor = actor;
        LOG("hero panel: block fields cnt=%u arg=%u (actor %#llx)",
            cnt, arg, (unsigned long long)actor);
    }
    // The state exists while either field says so; garbage cannot pass.
    int dur = cnt >= 1 && cnt <= 999;
    if (!dur && (arg < 1 || arg > 999)) return;
    dd_loc_fn lookup = (dd_loc_fn)(base + DD_ORC_LOOKUP);
    dd_fmt_fn fmt = (dd_fmt_fn)(base + DD_FMT);
    if (!lookup || !fmt) return;
    dd_loc_ret r = dur
        ? lookup("tray_icon_tooltip_health_damage_blocks_duration_format")
        : lookup("tray_icon_tooltip_health_damage_blocks_format");
    if (!r.ptr || !hero_page_ok((uintptr_t)r.ptr)) return;
    dd_fmt_desc d = { r.ptr, (uint32_t)r.packed, (uint32_t)(r.packed >> 32) };
    char line[0x100];
    memset(line, 0, sizeof line);
    if (dur) fmt(&d, line, 0x100, arg, cnt);
    else fmt(&d, line, 0x100, arg, 0);   // the else branch passes no second integer
    if (dbg) LOG("hero panel: block raw = \"%s\"", line);
    hero_strip(s->block_line, sizeof s->block_line, line);
}

// (b) The overstress state. Afflictions (暴虐, 自私, ...) are not buffs: they
// are the hero's property-bag string "affliction_type_id" (empty while the
// hero is fine) — the same bag the class id comes from, with the same drifting
// node placement. The Chinese name is the game's own lookup of
// "str_affliction_name_<id>" / "str_virtue_name_<id>", the key shapes the game
// itself composes (both verbatim in the main image). The id is validated
// against the romfs trait library's own lists, so the lookup only ever sees
// keys the game itself displays (a miss would enter the crash-prone fallback).
// The found bag node address is cached per hero and re-verified cheaply each
// sample: a state change shows up live, and a moved node costs one rescan.
static const char *const hero_affliction_ids[] = {
    "abusive", "depressed", "fearful", "irrational", "masochistic", "paranoid",
    "selfish", 0};
static const char *const hero_virtue_ids[] = {
    "courageous", "focused", "powerful", "stalwart", "vigorous", 0};

// The value after the key: the node padding varies between instances (a plain
// u32 length on one hero, a stray byte first on another), so accept the first
// identifier-shaped run and let the caller's whitelist decide.
static void hero_bag_id(const uint8_t *buf, size_t cap, size_t key_len,
                        char *out, size_t out_cap) {
    out[0] = 0;
    for (size_t t = key_len; t + 4 <= cap; t++) {
        if (buf[t] < 'a' || buf[t] > 'z') continue;
        size_t e = t;
        while (e < cap && e - t < 24 &&
               ((buf[e] >= 'a' && buf[e] <= 'z') || buf[e] == '_'))
            e++;
        if (e - t >= 3) {
            size_t n = e - t < out_cap - 1 ? e - t : out_cap - 1;
            memcpy(out, buf + t, n);
            out[n] = 0;
            return;
        }
        t = e;
    }
}

static int hero_id_in(const char *const *list, const char *id) {
    for (int i = 0; list[i]; i++)
        if (!strcmp(list[i], id)) return 1;
    return 0;
}

static void hero_affliction_line(uintptr_t base, uint64_t actor, int dbg, dd_hero_snapshot_t *s) {
    (void)actor;
    static char cached_id[32], cached_line[DD_HERO_STR_MAX];
    const size_t key_len = sizeof DD_AFFLICTION_KEY;   // includes the NUL
    uint8_t buf[0x40];
    // The node address comes from the shared bag scan (g_bag.aff_node), bound
    // to this hero by the name anchor; it is re-verified cheaply each sample,
    // so a state change shows up live.
    uint64_t node = !strcmp(s->name, g_bag.name) ? g_bag.aff_node : 0;
    int node_ok = node &&
        hero_rd(node, buf, sizeof buf) &&
        !memcmp(buf, DD_AFFLICTION_KEY, key_len);
    if (node && !node_ok) {   // the node moved or was freed: re-scan
        g_bag.aff_node = 0;
        hero_bag_scan_restart();
    }
    if (!node_ok) {
        cached_id[0] = 0; cached_line[0] = 0;
        return;
    }
    char id[32];
    hero_bag_id(buf, sizeof buf, key_len, id, sizeof id);
    if (strcmp(id, cached_id) == 0) {   // unchanged since the last sample
        snprintf(s->affliction_line, sizeof s->affliction_line, "%s", cached_line);
        return;
    }
    snprintf(cached_id, sizeof cached_id, "%s", id);
    cached_line[0] = 0;
    if (dbg) LOG("hero panel: affliction id = \"%s\"", id);
    if (id[0]) {
        const char *shape = NULL;
        if (hero_id_in(hero_affliction_ids, id)) shape = "str_affliction_name_%s";
        else if (hero_id_in(hero_virtue_ids, id)) shape = "str_virtue_name_%s";
        if (shape) {
            dd_loc_fn lookup = (dd_loc_fn)(base + DD_ORC_LOOKUP);
            char key[64];
            snprintf(key, sizeof key, shape, id);
            if (lookup) {
                const char *r = (const char *)lookup(key).ptr;
                if (r && hero_page_ok((uintptr_t)r)) {
                    char text[DD_HERO_STR_MAX];
                    size_t k = 0;
                    while (k + 1 < sizeof text && r[k]) { text[k] = r[k]; k++; }
                    text[k] = 0;
                    if (text[0]) snprintf(cached_line, sizeof cached_line, "%s", text);
                }
            }
        }
        // An id outside the game's own lists is never shown (never an internal id).
    }
    snprintf(s->affliction_line, sizeof s->affliction_line, "%s", cached_line);
}

void dd_hero_frame_tick(void) {
    if (!dm_hero_panel_enabled()) {
        if (!g_hero_cleared_when_off) {
            g_hero_cleared_when_off = 1;
            hero_publish_invalid();
        }
        return;
    }
    g_hero_cleared_when_off = 0;

    // Per frame, before the sample gate: the tap tracker must see every
    // contact change (a fast tap can start and end between two samples), and
    // the tap window must notice the selection change promptly. Both use the
    // module base cached by the per-sample scan below; until the first scan
    // succeeds there is nothing to track against.
    if (g_base_cache) {
        uint64_t s0 = 0, a0 = 0;
        if (hero_rd(g_base_cache + DD_HERO_SINGLETON, &s0, 8) && s0)
            hero_rd(s0 + DD_HERO_SINGLETON_ACTOR, &a0, 8);
        g_sel_last = a0;
        hero_tap_track();
        if (g_tap_armed && dm_touch_now_ns() - g_tap_lift_ns > DD_TAP_WINDOW_NS)
            g_tap_armed = 0;
        if (g_tap_armed && g_sel_last && g_sel_last != g_tap_baseline) {
            g_tap_armed = 0;   // the tap moved the game's own selection: follow it
            hero_pin_inspect(g_base_cache, g_size_cache, g_sel_last);
        }
    }

    if (++g_hero_tick % DD_HERO_SAMPLE_EVERY) return;

    module_t *main_mod = NULL;
    int sdk_ok = 0;
    for (int i = 0; i < g_nmod; i++) {
        module_t *m = &g_mod[i];
        if (!strcmp(m->name, "main") && !strcmp(m->build_id, DD_HERO_MAIN_BUILD)) main_mod = m;
        if (!strcmp(m->name, "sdk") && !strcmp(m->build_id, DD_HERO_SDK_BUILD)) sdk_ok = 1;
    }
    if (!main_mod || !sdk_ok || main_mod->size <= DD_ORC_LINE_FULL + 0x400 ||
        !gate_obs_present(OBS_DD_TOUCH_FRAME)) {
        hero_note("build/gate check failed");
        hero_publish_invalid();
        return;
    }
    uintptr_t base = (uintptr_t)main_mod->base;
    g_hero_base_log = base;
    g_base_cache = base;
    g_size_cache = main_mod->size;

    // The look target: the Actor the player pinned by clicking a hero, else —
    // before the first click — the acting hero, as before. The pin deliberately
    // survives the game's own hero switching; it is dropped only when the
    // Actor itself is gone (vtable/name) or the raid object behind it ended
    // (leaving the dungeon or the combat scene).
    uint64_t actor = atomic_load_explicit(&g_inspect_actor, memory_order_acquire);
    if (actor) {
        uint64_t vt = 0;
        if (!hero_actor_plausible(base, main_mod->size, actor, &vt) ||
            vt != atomic_load_explicit(&g_inspect_vt, memory_order_relaxed)) {
            atomic_store_explicit(&g_inspect_actor, 0, memory_order_release);
            actor = 0;
            hero_note("inspection target destroyed");
        } else {   // the scene check: the raid/combat object must still exist
            void *(*has_raid)(void *) = NULL;
            memcpy(&has_raid, (void *)(uintptr_t)(vt + 0x20), sizeof has_raid);
            if (!has_raid || !has_raid((void *)(uintptr_t)actor)) {
                atomic_store_explicit(&g_inspect_actor, 0, memory_order_release);
                actor = 0;
                hero_note("inspection target left the raid");
            }
        }
    }
    if (!actor) {
        uint64_t singleton = 0;
        if (!hero_rd(base + DD_HERO_SINGLETON, &singleton, 8) || !singleton ||
            singleton < base || singleton >= base + main_mod->size) {
            hero_note("singleton unreadable");
            hero_publish_invalid();
            return;
        }
        if (!hero_rd(singleton + DD_HERO_SINGLETON_ACTOR, &actor, 8) || !actor) {
            hero_note("selected actor null");
            hero_publish_invalid();
            return;
        }
        // An Actor's vtable must live inside this same main image. Town / title
        // screens reuse the singleton slot for unrelated objects, which this
        // rejects before the original chain is invoked.
        uint64_t vt = 0;
        if (!hero_rd(actor, &vt, 8) || !vt || vt < base || vt >= base + main_mod->size) {
            hero_note("actor vtable outside main");
            hero_publish_invalid();
            return;
        }
    }
    uint64_t begin = 0, end = 0;
    if (!hero_rd(actor + DD_HERO_VEC_BEGIN, &begin, 8) ||
        !hero_rd(actor + DD_HERO_VEC_END, &end, 8) ||
        end < begin || (end - begin) % DD_HERO_ELEM_STEP != 0 ||
        end - begin > DD_HERO_ELEM_STEP * 4096) {
        hero_note("buff vector malformed");
        hero_publish_invalid();
        return;
    }

    dd_hero_snapshot_t s;
    memset(&s, 0, sizeof s);
    s.valid = 1;
    int dbg = g_hero_dbg < hero_dbg_limit();
    hero_identity(base, actor, dbg, &s);
    if (begin != end) hero_original_lines(base, actor, begin, end, &s);
    hero_block_line(base, actor, dbg, &s);
    hero_affliction_line(base, actor, dbg, &s);

    {   // Which Actor did the tooltip builder describe this frame?
        uint64_t ga = atomic_load_explicit(&g_gate_actor, memory_order_relaxed);
        static uint64_t last_gate;
        if (ga && ga != last_gate) {
            last_gate = ga;
            LOG("hero panel: gate actor=%#llx hero=%#llx", (unsigned long long)ga,
                (unsigned long long)actor);
        }
    }
    hero_note("snapshot valid");
    hero_publish(&s);
}
