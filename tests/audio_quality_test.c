#include "../src/audio_quality.h"
#include "../src/protocol.h"
#include "../src/audio_policy.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
int main(void) {
    AudioQuality q;aq_init(&q);assert(q.modes[0]==320 && q.modes[1]==320 && !q.open);
    for(unsigned mode=0;mode<=400;++mode) {
        int valid=mode==0 || mode==96 || mode==128 || mode==160 || mode==192 || mode==256 || mode==320;
        assert(aq_valid(mode)==valid);
    }
    unsigned mode=320;for(unsigned i=0;i<7;++i)mode=aq_cycle(mode,1);assert(mode==320);
    assert(aq_cycle(320,-1)==0 && aq_cycle(0,-1)==96);
    uint8_t feedback[32];aq_report(feedback,128,3,469,90,1,1,320);
    assert(!memcmp(feedback,"VAQ1",4) && vpcm_le32(feedback+4)==128 && vpcm_le32(feedback+8)==3);
    assert(vpcm_le32(feedback+12)==469 && vpcm_le32(feedback+16)==90 && vpcm_le32(feedback+20)==1);
    assert(vpcm_le32(feedback+24)==1 && vpcm_le32(feedback+28)==320);
    uint8_t v2[36];aq_report_v2(v2,320,9,2048,123,1,1,320,0xfffffff0u);
    assert(!memcmp(v2,"VAQ2",4) && vpcm_le32(v2+12)==2048 && vpcm_le32(v2+32)==0xfffffff0u);
    assert(AUDIO_CAPACITY_MS==2048 && audio_start_bytes(1)==196608 && audio_start_bytes(0)==49152);
    assert(audio_start_bytes(1)<AUDIO_CAPACITY_BYTES);
    char path[]="/tmp/vita-quality-test-XXXXXX";int fd=mkstemp(path);assert(fd>=0);close(fd);
    q.modes[1]=128;assert(aq_save(&q,path));aq_init(&q);assert(aq_load(&q,path));assert(q.modes[1]==128);
    const uint8_t good[12]={'V','A','Q','1',0x40,1,0,0,0x80,0,0,0};
    for(unsigned i=0;i<12;++i)assert(!aq_parse(&q,good,i));
    assert(!aq_parse(&q,good,13));uint8_t bad[12];memcpy(bad,good,12);bad[0]='x';assert(!aq_parse(&q,bad,12));
    memcpy(bad,good,12);bad[8]=127;assert(!aq_parse(&q,bad,12));assert(q.modes[1]==128);
    unlink(path);puts("Audio quality: preferences, validation, persistence, cycling and exact feedback wire format passed.");
    return 0;
}
