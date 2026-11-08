#ifndef RECEIVER_AUDIO_RESET_H
#define RECEIVER_AUDIO_RESET_H
#include <stdint.h>
typedef struct { uint32_t id;unsigned phase;int held;uint64_t since; } AudioResetPolicy;
static inline int audio_reset_event(AudioResetPolicy *p,uint32_t id,unsigned hold,uint64_t now) {
    if(!id || hold>1 || (p->id==id && p->phase==hold))return 0;
    p->id=id;p->phase=hold;p->held=!!hold;p->since=now;return 1;
}
static inline int audio_reset_timeout(AudioResetPolicy *p,uint64_t now,int controls_online) {
    uint64_t elapsed=now>=p->since?now-p->since:0;
    if(p->held && (elapsed>25000000ULL || (!controls_online && elapsed>3000000ULL))) {
        p->held=0;return 1;
    }
    return 0;
}
#endif
