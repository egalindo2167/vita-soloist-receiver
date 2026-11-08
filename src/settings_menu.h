#ifndef RECEIVER_SETTINGS_MENU_H
#define RECEIVER_SETTINGS_MENU_H
#include "audio_quality.h"
enum { MENU_OPEN=1, MENU_BACK=2, MENU_ACTIVATE=4, MENU_UP=8, MENU_DOWN=16,
       MENU_LEFT=32, MENU_RIGHT=64, MENU_L=128, MENU_R=256 };
enum { SETTINGS_QUALITY=1, SETTINGS_DISPLAY=2, SETTINGS_ROUTE=4, SETTINGS_DETAILS=8,
       SETTINGS_NAV_PLAYER=16, SETTINGS_NAV_QUEUE=32, SETTINGS_NAV_FAVORITES=64 };
enum { SETTINGS_ROOT, SETTINGS_AUDIO };
typedef struct { unsigned open,page,selected,timeout_seconds; } SettingsMenu;
void settings_menu_init(SettingsMenu *menu);
/* Pure input policy; file writes and network changes run on the PC-link worker.
 * Every gesture in an open menu is consumed, including the gesture closing it. */
unsigned settings_menu_input(SettingsMenu *menu,AudioQuality *quality,unsigned keys,
                             int fresh,int x,int y,int remote,int *consumed);
#endif
