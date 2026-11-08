#include "audio_quality.h"
#include "protocol.h"
#include <stdio.h>
#include <string.h>
static const unsigned modes[]={0,320,256,192,160,128,96};
static void put32(uint8_t *p,unsigned n) { for(unsigned i=0;i<4;++i)p[i]=(uint8_t)(n>>(i*8)); }
int aq_valid(unsigned mode) {
    for(unsigned i=0;i<7;++i)if(mode==modes[i])return 1;
    return 0;
}
void aq_init(AudioQuality *q) { memset(q,0,sizeof(*q));q->modes[0]=q->modes[1]=320; }
int aq_parse(AudioQuality *q,const void *data,size_t size) {
    const uint8_t *p=data;
    if(size!=12 || memcmp(p,"VAQ1",4))return 0;
    unsigned local=vpcm_le32(p+4),remote=vpcm_le32(p+8);
    if(!aq_valid(local) || !aq_valid(remote))return 0;
    q->modes[0]=local;q->modes[1]=remote;return 1;
}
int aq_load(AudioQuality *q,const char *path) {
    FILE *f=fopen(path,"rb");if(!f)return 0;
    uint8_t p[13];size_t n=fread(p,1,sizeof(p),f);int bad=ferror(f);fclose(f);
    return !bad && aq_parse(q,p,n);
}
int aq_save(const AudioQuality *q,const char *path) {
    if(!aq_valid(q->modes[0]) || !aq_valid(q->modes[1]))return 0;
    uint8_t p[12];memcpy(p,"VAQ1",4);put32(p+4,q->modes[0]);put32(p+8,q->modes[1]);
    FILE *f=fopen(path,"wb");if(!f)return 0;
    int ok=fwrite(p,1,sizeof(p),f)==sizeof(p);if(fclose(f))ok=0;return ok;
}
unsigned aq_cycle(unsigned mode,int delta) {
    unsigned i;for(i=0;i<7 && modes[i]!=mode;++i) { }
    if(i==7)i=1;
    return modes[(i+(delta<0?6:1))%7];
}
void aq_report(uint8_t out[32],unsigned mode,unsigned underruns,unsigned buffer_ms,
               unsigned seconds,int playing,int remote,unsigned actual_kbps) {
    memcpy(out,"VAQ1",4);put32(out+4,mode);put32(out+8,underruns);put32(out+12,buffer_ms);
    put32(out+16,seconds);put32(out+20,!!playing);put32(out+24,!!remote);put32(out+28,actual_kbps);
}
void aq_report_v2(uint8_t out[36],unsigned mode,unsigned underruns,unsigned buffer_ms,
                  unsigned seconds,int playing,int remote,unsigned actual_kbps,uint32_t received_frames) {
    aq_report(out,mode,underruns,buffer_ms,seconds,playing,remote,actual_kbps);
    memcpy(out,"VAQ2",4);put32(out+32,received_frames);
}
