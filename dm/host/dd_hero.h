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

#endif
