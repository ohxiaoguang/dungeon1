// The kernel's thread id at ThreadLocalRegion + 0x110 (thread.c guest_thread_tlr_set_id): nn::os reads it there as "the current thread id" and stores it in
// InternalCriticalSection lock words, so a region without it reads 0 -- which is also a free lock word, and SDK 22's pthread_mutex_lock then treats a mutex being
// locked for the first time as already held by the current thread and aborts (Darkest Dungeon 1.3.0's first malloc, sdk+0x138bb0 -> 0x153bf0 -> 0x153c90).
// Method: include the real thread.c, create the keys the way the loader does, initialise a thread's region and set an id; the region must start at 0 (the host
// writes it, nothing in the game's code does -- the region is read-only at EL0), and the write must land at +0x110 only, leaving +0x1f8 (the current thread
// object) alone.
#include <stdint.h>
#include <stdio.h>
#include <pthread.h>
#include <string.h>
#include "../thread.c"

pthread_key_t g_key18, g_keytls, g_keytlr, g_keygate;
void dm_gate(void) {}

static int fails, checks;
#define EXPECT(name, want, got) do { long long w_ = (long long)(want), g_ = (long long)(got); checks++; \
    printf("%-52s expected %-10lld → got %-10lld %s\n", name, w_, g_, w_ == g_ ? "✓" : "✗"); if (w_ != g_) fails++; } while (0)

int main(void) {
    if (pthread_key_create(&g_key18, NULL) || pthread_key_create(&g_keytls, NULL) || pthread_key_create(&g_keytlr, NULL) || pthread_key_create(&g_keygate, NULL)) {
        printf("key creation failed\n"); return 2;
    }
    guest_thread_init();
    uint8_t *tlr = pthread_getspecific(g_keytlr);
    if (!tlr) { printf("no thread-local region\n"); return 2; }
    EXPECT("a fresh region has no thread id at +0x110", 0, *(uint32_t *)(tlr + 0x110));
    guest_thread_tlr_set_id(0x51);
    EXPECT("the id svcGetThreadId answers lands at +0x110", 0x51, *(uint32_t *)(tlr + 0x110));
    guest_thread_tlr_set_id(0x1234);
    EXPECT("a later id replaces it", 0x1234, *(uint32_t *)(tlr + 0x110));
    EXPECT("the current thread object at +0x1f8 is untouched", 1, *(void **)(tlr + 0x1f8) == tlr + 0x200);
    EXPECT("the bytes after the id are untouched", 0, *(uint32_t *)(tlr + 0x114));
    printf("t_tlr_id: %d checks, %d failed\n", checks, fails); return fails != 0;
}
