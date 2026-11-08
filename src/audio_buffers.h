#ifndef VPCM_AUDIO_BUFFERS_H
#define VPCM_AUDIO_BUFFERS_H
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include "protocol.h"
/* Output accepts the current pointer while the prior queued buffer finishes.
 * Never overwrite that in-flight buffer. Alternation keeps each block intact
 * until the following output call has returned. Drain before destroying pool. */
typedef struct {
    int16_t samples[2][VPCM_FRAMES * 2] __attribute__((aligned(64)));
    unsigned next;
} VpcmAudioBuffers;
static inline int16_t *vpcm_next_audio_buffer(VpcmAudioBuffers *pool) {
    int16_t *p = pool->samples[pool->next];
    pool->next ^= 1;
    return p;
}
static inline int16_t *vpcm_prepare_audio(VpcmAudioBuffers *pool,
        const uint8_t *data, size_t count, int muted) {
    if (count > VPCM_BLOCK_BYTES || count % 4) return NULL;
    int16_t *p = vpcm_next_audio_buffer(pool);
    memset(p, 0, VPCM_BLOCK_BYTES);
    if (!muted && count) memcpy(p, data, count);
    return p;
}
#endif
