// Hero status panel: the read-only snapshot the UI consumes.
//
// The game-thread collector (hle_dd_hero.c) fills this in on the game thread
// and hands out copies under a mutex. The Buff rows are VERBATIM lines
// produced by the game's own tooltip code (aggregate -> localize -> format);
// the identity fields (name, class, HP, stress) come from the same Actor.
#ifndef DD_HERO_H
#define DD_HERO_H

#include <stdint.h>

#define DD_HERO_STR_MAX   64
#define DD_HERO_LINE_MAX  256           // the game's own line buffer is 0x100
#define DD_HERO_MAX_BUFFS 32

// What the panel is looking at. Phase 1 only ever produces DD_INSPECT_HERO, but
// the snapshot, the collector's target slot and both front ends are written
// against this type so an enemy target can be added without a second panel.
typedef enum {
    DD_INSPECT_NONE = 0,
    DD_INSPECT_HERO = 1,
    DD_INSPECT_ENEMY = 2
} DdInspectTargetType;

typedef struct {
    char line[DD_HERO_LINE_MAX];  // one original tooltip line, already localized
    int negative;                 // the game printed a '-'
} dd_hero_buff_t;

typedef struct {
    uint64_t generation;          // bumps on hero switch, buff change or scene loss
    uint64_t sample;              // collector sample counter
    int valid;                    // 1 only when a live dungeon Actor was verified
    // ---- The inspected object (the last one the player tapped) ----
    // The panel is anchored to the GAME's own per-unit screen position, read
    // from the sprite animator draw (see hle_dd_hero.c). All coordinates are
    // normalized over the game's picture (0..1, origin top left), so a front end
    // only maps them through its own picture rectangle - no platform constants.
    int target_type;              // DdInspectTargetType
    uint64_t target_actor;        // identity only; the UI never dereferences it
    int anchor_valid;             // the target was drawn this sample (its position is real)
    float anchor_x, anchor_y;     // the panel's anchor point: the top centre of the unit
    float body_x0, body_y0, body_x1, body_y1;   // the unit's click box, same space
    char name[DD_HERO_STR_MAX];   // localized hero name (the game stores it in the Actor)
    char class_name[DD_HERO_STR_MAX]; // localized class name (empty: see hle_dd_hero.c)
    char class_id[DD_HERO_STR_MAX];   // the Actor's raw class id, e.g. "jester"
    int has_battle;               // the game says a raid/combat object exists
    int has_hp, hp;               // current HP
    int has_stress, stress, stress_max;
    // Special states, each read from its own game structure (never through the
    // Buff filters). Empty string = the state is not present.
    char affliction_line[DD_HERO_STR_MAX]; // the overstress state's own name, e.g. "暴虐"
    char block_line[DD_HERO_LINE_MAX];     // the game's own block tooltip, e.g. "剩余1次护体隔挡"
    int buff_count;
    dd_hero_buff_t buffs[DD_HERO_MAX_BUFFS];
    // Enemy side (right of the picture). Reserved for phase 2: the same
    // snapshot, panel and anchor are reused, but until an enemy target can be
    // captured the UI never shows this side.
    int enemy_valid;
    int enemy_buff_count;
    dd_hero_buff_t enemy_buffs[DD_HERO_MAX_BUFFS];
} dd_hero_snapshot_t;

// Thread-safe by-value copy. Safe to call from the UI/main thread at any time.
void dm_hero_snapshot_take(dd_hero_snapshot_t *out);
// 1 when DM_DD_HERO_PANEL is enabled; cached at first use.
int dm_hero_panel_enabled(void);
// Called once per game frame from the existing OBS_DD_TOUCH_FRAME gate.
void dd_hero_frame_tick(void);
// The inspected object is chosen by tapping the unit on screen (the host's own
// contact stream, hit-tested against the game's per-unit screen positions), and
// never by the automatic turn switch. Two read-only observers pin the hero the
// game's own CharacterDisplay sheet shows (opened by double-tapping a model):
// the sheet holds it at +0x120, and the touch policy's gates hand us the panel
// (on close) and the skill-grid wrapper (while it draws). No input is injected
// and nothing in the game is written.
void dd_hero_note_character_panel(uint64_t panel);
void dd_hero_note_skill_wrapper(uint64_t callable);

#endif
