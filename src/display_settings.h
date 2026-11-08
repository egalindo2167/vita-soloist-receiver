#ifndef RECEIVER_DISPLAY_SETTINGS_H
#define RECEIVER_DISPLAY_SETTINGS_H
#include <stddef.h>
static inline int display_timeout_valid(unsigned seconds) {
    return seconds==0 || seconds==30 || seconds==60 || seconds==120 || seconds==300;
}
unsigned display_timeout_cycle(unsigned seconds,int direction);
int display_settings_parse(unsigned *seconds,const void *data,size_t size);
int display_settings_load(unsigned *seconds,const char *path);
int display_settings_save(unsigned seconds,const char *path);
#endif
