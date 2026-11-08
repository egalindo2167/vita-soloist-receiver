#ifndef RECEIVER_AUDIO_QUALITY_H
#define RECEIVER_AUDIO_QUALITY_H
#include <stddef.h>
#include <stdint.h>
typedef struct { unsigned modes[2],tab;int open; } AudioQuality;
int aq_valid(unsigned mode);
void aq_init(AudioQuality *quality);
int aq_parse(AudioQuality *quality,const void *data,size_t size);
int aq_load(AudioQuality *quality,const char *path);
int aq_save(const AudioQuality *quality,const char *path);
unsigned aq_cycle(unsigned mode,int delta);
void aq_report(uint8_t out[32],unsigned mode,unsigned underruns,unsigned buffer_ms,
               unsigned seconds,int playing,int remote,unsigned actual_kbps);
void aq_report_v2(uint8_t out[36],unsigned mode,unsigned underruns,unsigned buffer_ms,
                  unsigned seconds,int playing,int remote,unsigned actual_kbps,uint32_t received_frames);
#endif
