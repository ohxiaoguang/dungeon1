"""Execute collector rules with synthetic tables and gate frames; no game inputs."""
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SOURCE = (ROOT / 'dm/host/hle_dd_hero.c').read_text()


def function(name):
    start = SOURCE.index('static ', SOURCE.index(name) - 32)
    brace = SOURCE.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (SOURCE[end] == '{') - (SOURCE[end] == '}')
        end += 1
    return SOURCE[start:end]


class HeroPanelBehavior(unittest.TestCase):
    def test_collector_rules(self):
        predicate = function('int hero_tray_predicate')
        floats = function('float hero_gate_f32')
        harness = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <math.h>
#define DD_UI_W 1280.0f
#define DD_UI_H 720.0f
#define DD_HERO_GROUP 0x5c
#define DD_STAT_TABLE 0x1000
#define DD_GROUP_TABLE 0x2000
#define DD_HERO_STR_MAX 64
#define DD_AFFLICTION_KEY "affliction_type_id"
#define LOG(...) ((void)0)
static uint8_t stats[0x58], flag;
static int hero_rd(uint64_t a, void *p, size_t n) {
    if (n == sizeof stats) memcpy(p, stats, n); else *(uint8_t *)p = flag;
    return 1;
}
'''
        harness += predicate + '\n' + floats + '\n' + function('int hero_project_box')
        harness += r'''
int main(void) {
    uint8_t elem[0x1d8] = {0}; uint32_t group = 1, stat = 2;
    memcpy(elem+8, &stat, 4); memcpy(elem+0x5c, &group, 4); flag=1;
    assert(hero_tray_predicate(elem, 0));
    stats[0x56]=1; assert(!hero_tray_predicate(elem, 0)); stats[0x56]=0;
    stats[0x45]=1; assert(!hero_tray_predicate(elem, 0));
    stat=4; memcpy(elem+8,&stat,4); assert(hero_tray_predicate(elem,0));
    stat=2; memcpy(elem+8,&stat,4); stats[0x45]=0;
    stat=44; memcpy(elem+8,&stat,4); assert(!hero_tray_predicate(elem, 0));
    stat=2; memcpy(elem+8,&stat,4);
    elem[0x1d2]=1; flag=0; assert(!hero_tray_predicate(elem, 0));
    flag=0; group=18; memcpy(elem+0x5c,&group,4);
    assert(hero_tray_predicate(elem,0));
    group=19; memcpy(elem+0x5c,&group,4); assert(hero_tray_predicate(elem,0));
    stats[0x45]=1; assert(!hero_tray_predicate(elem,0)); stats[0x45]=0;
    flag=1; group=5; memcpy(elem+0x5c,&group,4); assert(!hero_tray_predicate(elem, 0));
    uint64_t frame[100]={0}; float values[]={18, 31, 12, 24};
    for (int i=0;i<4;i++) memcpy((uint8_t *)frame+256+16*i,&values[i],4);
    for (int i=0;i<4;i++) assert(hero_gate_f32(frame,i)==values[i]);
    float projection[16]={2.0f/1920,0,0,0,0,-2.0f/720,0,0,0,0,1,0,-1,1,0,1};
    float position[3]={960,700,0}, local[4]={-100,100,-300,0}, box[4];
    float viewport[4]={0,0,2.0f/3,2.0f/3}, extent[2]={1920,720};
    assert(hero_project_box(local,position,1,projection,viewport,extent,box));
    assert(fabsf((box[0]+box[2])*.5f-.5f)<1e-6f);
    assert(fabsf(box[1]-400.0f/1080)<1e-6f);
    position[0]+=192;
    assert(hero_project_box(local,position,1,projection,viewport,extent,box));
    assert(fabsf((box[0]+box[2])*.5f-.6f)<1e-6f);
    local[1]=200;
    assert(hero_project_box(local,position,-1,projection,viewport,extent,box));
    assert(fabsf((box[0]+box[2])*.5f-(.6f-50.0f/1920))<1e-6f);
    projection[15]=0; assert(!hero_project_box(local,position,1,projection,viewport,extent,box));
    return 0;
}
'''
        (ROOT / 'out').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='hero-rules-', dir=ROOT / 'out') as temp:
            src = pathlib.Path(temp) / 'rules.c'
            exe = pathlib.Path(temp) / 'rules'
            src.write_text(harness)
            subprocess.run(['clang', '-std=c11', '-Wall', '-Werror', str(src), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)

    def test_enemy_buff_formatting_preserves_vitals(self):
        harness = r"""
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "dd_hero.h"
#define DD_HERO_ELEM_STEP 0x1d8
#define DD_ORC_ROW_STEP 0x1d0
#define DD_STAT_TABLE 0
#define DD_HERO_GROUP 0x5c
#define LOG(...) ((void)0)
typedef void *(*dd_aggregate_fn)(void *,void **,void **,void *);
typedef void (*dd_line_fn)(char *,void *,void *,uint32_t);
typedef void (*dd_free_fn)(void *,uint64_t);
typedef struct {void *ptr;uint64_t packed;} dd_loc_ret;
typedef dd_loc_ret (*dd_loc_fn)(const char *);
static int g_hero_dbg, aggregated;
static int hero_dbg_limit(void) { return 0; }
static int hero_rd(uint64_t a,void *p,size_t n) {memcpy(p,(void *)(uintptr_t)a,n);return 1;}
static int hero_page_ok(uint64_t a) {return 1;}
static int hero_tray_predicate(const uint8_t *p,uintptr_t base) {return 1;}
static void hero_strip(char *p,size_t n,const char *s) {snprintf(p,n,"%s",s);}
static const char *hero_tray_format_key(const char *s) {return 0;}
static void hero_fmt_two(char *p,size_t n,const char *s,int a,int b) {}
static void *agg_stub(void *out,void **begin,void **end,void *actor) {
    aggregated++; memset(out,0,3*sizeof(void *));return out;
}
static void line_stub(char *out,void *row,void *actor,uint32_t w3) {}
static void free_stub(void *p,uint64_t n) {}
static dd_loc_ret lookup_stub(const char *s) {return (dd_loc_ret){0};}
static void *no_hero_raid(void *actor) {return 0;}
#define DD_ORC_AGGREGATE ((uintptr_t)agg_stub)
#define DD_ORC_LINE_FULL ((uintptr_t)line_stub)
#define DD_ORC_FREE ((uintptr_t)free_stub)
#define DD_ORC_LOOKUP ((uintptr_t)lookup_stub)
"""
        harness += function('void hero_original_lines')
        harness += r"""
int main(void) {
    uintptr_t vt[8]={0}; vt[4]=(uintptr_t)no_hero_raid;
    uintptr_t actor[1]={(uintptr_t)vt}; uint8_t buff[DD_HERO_ELEM_STEP]={0};
    dd_hero_snapshot_t s={0};s.target_type=DD_INSPECT_ENEMY;
    s.has_battle=1;s.has_hp=1;s.hp=7;s.has_hp_max=1;s.hp_max=13;
    hero_original_lines(0,(uintptr_t)actor,(uintptr_t)buff,(uintptr_t)buff+sizeof buff,&s,0);
    assert(aggregated==1);assert(s.has_battle==1);
    assert(s.has_hp && s.hp==7 && s.has_hp_max && s.hp_max==13);
    return 0;
}
"""
        with tempfile.TemporaryDirectory(prefix='hero-vitals-', dir=ROOT / 'out') as temp:
            src = pathlib.Path(temp) / 'vitals.c'
            exe = pathlib.Path(temp) / 'vitals'
            src.write_text(harness)
            subprocess.run(['clang', '-std=c11', '-I', str(ROOT / 'dm/host'), str(src), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)

    def test_native_traits_and_mark_duration(self):
        harness = r'''#include <assert.h>
#include <stdint.h>
#include <string.h>
#include <stdio.h>
#define DD_HERO_ELEM_STEP 0x1d8
#define DD_HERO_GROUP 0x5c
static uint8_t records[4][0x100], buffs[3][0x1d8], alternate;
static uint64_t vectors[6];
static int hero_rd(uint64_t a,void *out,size_t n) {
 if(a==0xb1a57220) {uint64_t v=(uintptr_t)vectors;memcpy(out,&v,8);return 1;}
 if(a==0xb1a8f61b) {*(uint8_t*)out=alternate;return 1;}
 memcpy(out,(void*)(uintptr_t)a,n);return 1;
}
'''
        harness += function('int hero_trait_id') + '\n' + function('int hero_mark_turns')
        harness += r'''
int main(void) {
 const char *ids[]={"masochistic","paranoid","abusive","custom_trait"};
 for(int i=0;i<4;i++) {strcpy((char*)records[i],ids[i]);uint32_t hash=100+i;memcpy(records[i]+0x40,&hash,4);}
 vectors[0]=(uintptr_t)records;vectors[1]=(uintptr_t)(records+4);
 vectors[3]=vectors[0];vectors[4]=vectors[1];
 char id[64];
 for(int i=0;i<4;i++) {assert(hero_trait_id(0,100+i,id));assert(!strcmp(id,ids[i]));}
 assert(!hero_trait_id(0,999,id));alternate=1;
 assert(hero_trait_id(0,101,id));assert(!strcmp(id,"paranoid"));
 vectors[4]=vectors[3]+1;assert(!hero_trait_id(0,101,id));
 uint32_t stat=1, group=1, duration=1;int32_t t=2;
 memcpy(buffs[0]+8,&stat,4);memcpy(buffs[0]+0x5c,&group,4);
 memcpy(buffs[0]+0x54,&t,4);memcpy(buffs[0]+0x58,&duration,4);
 int turns;uint64_t begin=(uintptr_t)buffs,end=(uintptr_t)(buffs+3);
 assert(hero_mark_turns(begin,end,&turns));assert(turns==2);
 memcpy(buffs[1],buffs[0],0x1d8);t=4;memcpy(buffs[1]+0x54,&t,4);
 assert(hero_mark_turns(begin,end,&turns));assert(turns==4);
 duration=0;memcpy(buffs[1]+0x58,&duration,4);
 assert(hero_mark_turns(begin,end,&turns));assert(turns==-1);
 memset(buffs,0,sizeof buffs);assert(!hero_mark_turns(begin,end,&turns));
 assert(!hero_mark_turns(begin,end-1,&turns));return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='hero-states-', dir=ROOT / 'out') as temp:
            src = pathlib.Path(temp) / 'states.c'
            exe = pathlib.Path(temp) / 'states'
            src.write_text(harness)
            subprocess.run(['clang', '-std=c11', str(src), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    unittest.main()
