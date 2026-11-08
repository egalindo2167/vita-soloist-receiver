#include "../src/audio_reset.h"
#include <assert.h>
#include <stdio.h>
int main(void) {
    AudioResetPolicy p={0};assert(!audio_reset_event(&p,0,0,0));assert(!audio_reset_event(&p,1,2,0));
    assert(audio_reset_event(&p,123,1,100));assert(p.held);
    assert(!audio_reset_event(&p,123,1,1000));assert(p.since==100);
    assert(!audio_reset_timeout(&p,3000000,0));assert(audio_reset_timeout(&p,3000101,0));assert(!p.held);
    /* Re-reading the same shared marker after timeout must not re-arm the hold. */
    assert(!audio_reset_event(&p,123,1,4000000));assert(!p.held);
    assert(audio_reset_event(&p,123,0,5000000));assert(!p.held);
    assert(audio_reset_event(&p,124,1,6000000));assert(!audio_reset_timeout(&p,31000000,1));
    assert(audio_reset_timeout(&p,31000001,1));assert(!p.held);
    /* Coalesced ready-only markers still discard the old stream exactly once. */
    assert(audio_reset_event(&p,125,0,32000000));assert(!audio_reset_event(&p,125,0,33000000));
    puts("Audio reset: hold/release, coalescing, duplicate markers and bounded loss recovery passed.");
    return 0;
}
