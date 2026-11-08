#include "display_settings.h"
#include <stdint.h>
#include <stdio.h>
#include <string.h>

unsigned display_timeout_cycle(unsigned seconds,int direction) {
    static const unsigned choices[]={30,60,120,300,0};
    unsigned i;for(i=0;i<5 && choices[i]!=seconds;++i) { }
    if(i==5)i=1;
    return choices[(i+(direction<0?4:1))%5];
}
int display_settings_parse(unsigned *seconds,const void *data,size_t size) {
    const uint8_t *p=data;
    if(size!=8 || memcmp(p,"VDS1",4))return 0;
    unsigned value=(unsigned)p[4]|((unsigned)p[5]<<8)|((unsigned)p[6]<<16)|((unsigned)p[7]<<24);
    if(!display_timeout_valid(value))return 0;
    *seconds=value;return 1;
}
int display_settings_load(unsigned *seconds,const char *path) {
    FILE *f=fopen(path,"rb");if(!f)return 0;
    uint8_t data[9];size_t n=fread(data,1,sizeof(data),f);int bad=ferror(f);fclose(f);
    return !bad && display_settings_parse(seconds,data,n);
}
int display_settings_save(unsigned seconds,const char *path) {
    if(!display_timeout_valid(seconds))return 0;
    uint8_t data[8]={'V','D','S','1',0,0,0,0};
    for(unsigned i=0;i<4;++i)data[i+4]=(uint8_t)(seconds>>(8*i));
    /* Like quality.bin, this tiny non-secret preference is written on the
     * worker. A truncated file is rejected at boot, retaining the safe 60 s
     * default. Do not rely on destination-replacing rename semantics in Vita IO. */
    FILE *f=fopen(path,"wb");if(!f)return 0;
    int ok=fwrite(data,1,sizeof(data),f)==sizeof(data);
    if(fclose(f))ok=0;
    return ok;
}
