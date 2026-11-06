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

typedef struct {
    char line[DD_HERO_LINE_MAX];  // one original tooltip line, already localized
    int negative;                 // the game printed a '-'
} dd_hero_buff_t;

typedef struct {
    uint64_t generation;          // bumps on hero switch, buff change or scene loss
    uint64_t sample;              // collector sample counter
    int valid;                    // 1 only when a live dungeon Actor was verified
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
    // Enemy side (right of the picture). Reserved: the selected-enemy pointer is
    // not located yet, so enemy_valid stays 0 and the UI hides that panel.
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
// Inspection target capture (the player's own click path, read-only): the
// game's CharacterDisplay sheet — opened by tapping a hero portrait — holds
// the hero it is showing at +0x120. The touch policy's gates hand us the panel
// (on close) and the skill-grid wrapper (while it draws); both pin that hero
// as the panel's look target until the target dies or the raid ends. No input
// is injected and nothing in the game is written.
void dd_hero_note_character_panel(uint64_t panel);
void dd_hero_note_skill_wrapper(uint64_t callable);

#endif
