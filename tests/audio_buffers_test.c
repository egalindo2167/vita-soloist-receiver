#include <assert.h>
#include <string.h>
#include "../src/audio_buffers.h"
static VpcmAudioBuffers pool;
static uint8_t first[VPCM_BLOCK_BYTES], second[VPCM_BLOCK_BYTES];
static uint8_t in_flight[VPCM_BLOCK_BYTES];
/* The device retains the most recent pointer after accepting it. The next
 * output call consumes that retained pointer before accepting its replacement. */
static const void *pending;
static void fake_output(const void *next) {
    if (pending) assert(memcmp(pending,in_flight,VPCM_BLOCK_BYTES)==0);
    memcpy(in_flight,next,VPCM_BLOCK_BYTES);
    pending=next;
}
int main(void) {
    memset(first,0x11,sizeof(first));memset(second,0x44,sizeof(second));
    int16_t *a=vpcm_prepare_audio(&pool,first,sizeof(first),0);fake_output(a);
    int16_t *b=vpcm_prepare_audio(&pool,second,sizeof(second),0);
    assert(a!=b);fake_output(b);
    /* Third block may overwrite A, but must preserve B until submission. */
    int16_t *c=vpcm_prepare_audio(&pool,first,16,0);
    assert(c==a);fake_output(c);
    assert(!memcmp(c,first,16));
    for(size_t i=16;i<VPCM_BLOCK_BYTES;i++)assert(((uint8_t*)c)[i]==0);
    int16_t *d=vpcm_prepare_audio(&pool,second,sizeof(second),1);fake_output(d);
    for(size_t i=0;i<VPCM_BLOCK_BYTES;i++)assert(((uint8_t*)d)[i]==0);
    unsigned before=pool.next;
    assert(vpcm_prepare_audio(&pool,first,3,0)==NULL);
    assert(vpcm_prepare_audio(&pool,first,VPCM_BLOCK_BYTES+4,0)==NULL);
    assert(pool.next==before);
    return 0;
}
