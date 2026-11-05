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

// Hero identity and bars, on the same Actor (verified by differential
// observation on two heroes with different values, 2026-11-05):
#define DD_HERO_NAME        0x8ull      // localized hero name, C string
#define DD_HERO_HP          0x80ull     // float current HP
#define DD_HERO_STRESS      0x1274ull   // float current stress
#define DD_HERO_STRESS_MAX  0xab8ull    // float stress cap (200)
#define DD_HERO_GROUP       0x5cull     // element word: 1 = combat effect, 5 = quirk
#define DD_HERO_CLASS_KEY   "heroClass" // property-bag key -> length-prefixed class id

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

typedef void *(*dd_loc_fn)(const char *key);
typedef void (*dd_aggregate_fn)(void *out_vec, void **inst_begin, void **inst_end,
                                void *actor);
typedef void (*dd_line_fn)(char *out_0x100, void *row, void *actor, uint32_t w3);
typedef void (*dd_free_fn)(void *p, uint64_t bytes);

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
        // Strip the game's colour protocol (<c> + 6-byte colour code + </c>;
        // the game's own renderer interprets it, our UI draws plain text).
        dd_hero_buff_t *out = &s->buffs[s->buff_count];
        size_t k = 0;
        for (size_t t = 0; t < 0x100 && line[t]; ) {
            if (line[t] == '<' && t + 9 <= 0x100 && line[t + 1] == 'c' && line[t + 2] == '>') {
                t += 9;
                continue;
            }
            if (line[t] == '<' && t + 4 <= 0x100 && !memcmp(line + t, "</c>", 4)) {
                t += 4;
                continue;
            }
            if (k + 1 >= sizeof out->line) break;
            out->line[k++] = line[t++];
        }
        out->line[k] = 0;
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
                    const char *tmpl = (const char *)lookup(tkey);
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
                            k = strlen(out->line);
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
//   property bag    "heroClass" -> length-prefixed class id. The bag position
//                   drifts between instances, so the (name -> class) pair is
//                   cached per hero. The localized class name comes from the
//                   game's own lookup with the key shape the game itself uses
//                   at roster load. The max HP is not stored in the Actor at
//                   all (the game computes it from the class config plus
//                   modifiers), so the panel shows the current HP only.
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

    // The class id lives in the hero's property map (the hero's save record),
    // whose nodes the allocator scatters AFTER this Actor at drifting offsets
    // (+0x2d96 .. +0x75f2 observed). The scan is bounded by the next LIVE
    // Actor (same vtable AND a name) so it never crosses into another hero,
    // skips unmapped pages instead of stopping, and runs once per hero — the
    // (name -> class) pair is cached, so known heroes cost nothing.
    char class_id[DD_HERO_STR_MAX] = "";
    static char cached_name[DD_HERO_STR_MAX], cached_class[DD_HERO_STR_MAX];
    if (cached_class[0] && !strcmp(s->name, cached_name))
        snprintf(class_id, sizeof class_id, "%s", cached_class);
    if (!class_id[0] && s->name[0]) {
        uint64_t extent = actor + 0x6000;   // conservative fallback
        uint64_t vt = 0;
        if (hero_rd(actor, &vt, 8) && vt) {
            for (uint64_t a = actor + 0x1000; a < actor + 0x40000; a += 0x400) {
                uint64_t v = 0;
                if (!hero_rd(a, &v, 8)) continue;   // unmapped page: skip it
                if (v != vt) continue;
                char nm[16];                     // a LIVE actor carries its name
                if (!hero_rd(a + DD_HERO_NAME, nm, sizeof nm) || !nm[0]) continue;
                extent = a;
                break;
            }
        }
        for (uint64_t a = actor; a + 0x900 <= extent && !class_id[0]; a += 0x700) {
            uint8_t buf[0x900];
            if (!hero_rd(a, buf, sizeof buf)) continue;   // skip unmapped windows
            for (size_t j = 0; j + 26 <= sizeof buf; j++) {
                if (memcmp(buf + j, DD_HERO_CLASS_KEY, 10) != 0) continue;  // "heroClass\0"
                // The value follows the key, but the node padding before it
                // varies (a plain u32 length on one hero, a stray byte first
                // on another). Skip the padding and accept the first
                // identifier run that is a class id the game itself ships
                // (romfs heroes/ directories).
                static const char *const classes[] = {
                    "abomination", "antiquarian", "arbalest", "bounty_hunter",
                    "crusader", "grave_robber", "hellion", "highwayman",
                    "houndmaster", "jester", "leper", "man_at_arms", "occultist",
                    "plague_doctor", "vestal", "shieldbreaker", "flagellant",
                    "musketeer", 0};
                for (size_t t = j + 10; t + 4 <= j + 26 && t < sizeof buf; t++) {
                    if (buf[t] < 'a' || buf[t] > 'z') continue;
                    size_t e = t;
                    while (e < sizeof buf && e - t < 24 &&
                           ((buf[e] >= 'a' && buf[e] <= 'z') || buf[e] == '_'))
                        e++;
                    if (e - t < 3) { t = e; continue; }
                    char cand[28];
                    memcpy(cand, buf + t, e - t);
                    cand[e - t] = 0;
                    for (int ci = 0; classes[ci]; ci++) {
                        if (!strcmp(cand, classes[ci])) {
                            snprintf(class_id, sizeof class_id, "%s", cand);
                            break;
                        }
                    }
                    if (class_id[0]) break;
                    t = e;
                }
                break;
            }
        }
        if (class_id[0]) {
            snprintf(cached_name, sizeof cached_name, "%s", s->name);
            snprintf(cached_class, sizeof cached_class, "%s", class_id);
        }
    }
    if (dbg) LOG("hero panel: hero=\"%s\" class_id=\"%s\" hp=%d stress=%d/%d",
                 s->name, class_id, s->hp, s->stress, s->stress_max);
    if (!class_id[0]) return;
    snprintf(s->class_id, sizeof s->class_id, "%s", class_id);

    // The localized class name comes from the game's own lookup with the
    // game's own key shape "hero_class_name_<id>". The game itself looks this
    // key up for every class while loading the roster (captured live), so the
    // call always hits an existing entry — the earlier crash came from feeding
    // the lookup garbage ids extracted from the wrong buffer, which took the
    // missing-key path that is not safe to enter from outside the game.
    dd_loc_fn lookup = (dd_loc_fn)(base + DD_ORC_LOOKUP);
    if (!lookup) return;
    char key[DD_HERO_STR_MAX];
    snprintf(key, sizeof key, "hero_class_name_%s", class_id);
    const char *r = (const char *)lookup(key);
    if (r && hero_page_ok((uintptr_t)r)) {
        char text[DD_HERO_STR_MAX];
        size_t k = 0;
        while (k + 1 < sizeof text && r[k]) { text[k] = r[k]; k++; }
        text[k] = 0;
        if (dbg) LOG("hero panel: class key \"%s\" -> \"%s\"", key, text);
        if (text[0]) snprintf(s->class_name, sizeof s->class_name, "%s", text);
    }
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

    uint64_t singleton = 0;
    if (!hero_rd(base + DD_HERO_SINGLETON, &singleton, 8) || !singleton ||
        singleton < base || singleton >= base + main_mod->size) {
        hero_note("singleton unreadable");
        hero_publish_invalid();
        return;
    }
    uint64_t actor = 0;
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
