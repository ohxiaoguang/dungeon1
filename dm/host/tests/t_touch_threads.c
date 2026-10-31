// Concurrent touch publication and consumption: the front end publishes the
// finger set (dm_touch_set_from / dm_touch_cancel_from / dm_touch_policy_activate)
// while the game thread samples the contact snapshot and the gesture history.
// Everything hle_touch.c shares is meant to be taken under its one lock, so the
// ThreadSanitizer build (make tsan) must report no data race; the plain build
// checks that the values read back stay inside their documented ranges.
#include <pthread.h>
#include <stdatomic.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include "front.h"

static atomic_int g_stop;
static int fails, cases;

static uint64_t now_ns(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return (uint64_t)t.tv_sec * 1000000000ull + (uint64_t)t.tv_nsec; }
static void check(const char *what, int ok) { cases++; if (!ok) { fails++; printf("FAIL %s\n", what); } else printf("ok   %s\n", what); }

static void *publisher(void *arg) {
    (void)arg;
    for (int i = 0; i < 200000; i++) {
        dm_touch t = {0, (float)(i % 1000) / 1000.0f, 0.25f};
        dm_touch_set_from(&t, 1, (i & 1) ? DM_CONTACT_IOS : DM_CONTACT_MAC_LEFT);
        if ((i & 127) == 0) dm_touch_set_from(NULL, 0, DM_CONTACT_IOS);
    }
    return NULL;
}
static void *canceller(void *arg) {
    (void)arg;
    for (int i = 0; i < 2000; i++) {
        dm_touch_cancel_from(DM_CONTACT_IOS);
        dm_touch_policy_activate(i & 1);
    }
    return NULL;
}
static void *reader(void *arg) {
    (void)arg;
    static int8_t g[16][0x60];
    int bad_phase = 0, bad_count = 0, bad_samp = 0, bad_gen = 0;
    uint64_t last_gen = 0;
    while (!atomic_load(&g_stop)) {
        int n = gesture_fill(g, 16, now_ns());
        if (n < 0 || n > 16) bad_samp++;
        dm_contact_snapshot s;
        dm_touch_contact_snapshot(&s);
        if (s.phase < DM_CONTACT_DOWN || s.phase > DM_CONTACT_RELEASED) bad_phase++;
        if (s.count < 0 || s.count > 16) bad_count++;
        if (s.generation < last_gen) bad_gen++;   // generations only advance
        last_gen = s.generation;
    }
    check("reader: every sampled phase is a documented one", bad_phase == 0);
    check("reader: every sampled count is 0..16", bad_count == 0);
    check("reader: gesture count is 0..16", bad_samp == 0);
    check("reader: generation never goes backwards", bad_gen == 0);
    return NULL;
}

int main(void) {
    pthread_t p, r, c;
    atomic_store(&g_stop, 0);
    dm_touch_policy_activate(1);
    pthread_create(&r, NULL, reader, NULL);
    pthread_create(&c, NULL, canceller, NULL);
    pthread_create(&p, NULL, publisher, NULL);
    pthread_join(p, NULL);
    pthread_join(c, NULL);
    atomic_store(&g_stop, 1);
    pthread_join(r, NULL);
    check("publisher and reader completed", 1);
    printf("== %d checks, %d failed ==\n", cases, fails);
    return fails != 0;
}
