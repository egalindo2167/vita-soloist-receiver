#include "settings_menu.h"
#include "display_settings.h"
#include "ui_layout.h"
#include <string.h>

void settings_menu_init(SettingsMenu *m) { memset(m,0,sizeof(*m));m->timeout_seconds=60; }
unsigned settings_menu_input(SettingsMenu *m,AudioQuality *q,unsigned keys,
                             int fresh,int x,int y,int remote,int *consumed) {
    *consumed=0;
    int gear=fresh && ui_hit(UI_GEAR,x,y);
    if(!m->open) {
        if((keys&MENU_OPEN) || gear) {
            m->open=1;m->page=SETTINGS_ROOT;m->selected=0;q->tab=!!remote;*consumed=1;
        }
        return 0;
    }
    *consumed=1;
    if((keys&MENU_OPEN) || gear) { m->open=0;return 0; }
    if(keys&MENU_BACK) {
        if(m->page==SETTINGS_AUDIO)m->page=SETTINGS_ROOT;else m->open=0;
        return 0;
    }
    int nav=fresh?ui_nav_at(x,y):-1;
    if(nav>=0) { m->open=0;return SETTINGS_NAV_PLAYER<<nav; }
    if(m->page==SETTINGS_AUDIO) {
        if(keys&(MENU_UP|MENU_DOWN|MENU_L|MENU_R))q->tab^=1;
        if(keys&(MENU_LEFT|MENU_RIGHT|MENU_ACTIVATE)) {
            q->modes[q->tab]=aq_cycle(q->modes[q->tab],keys&MENU_LEFT?-1:1);
            return SETTINGS_QUALITY;
        }
        if(fresh) {
            if(ui_hit(UI_QUALITY_LOCAL,x,y))q->tab=0;
            else if(ui_hit(UI_QUALITY_REMOTE,x,y))q->tab=1;
            static const unsigned choices[]={0,320,256,192,160,128,96};
            for(unsigned i=0;i<7;++i)if(ui_hit(ui_quality_choice(i),x,y)) {
                q->modes[q->tab]=choices[i];return SETTINGS_QUALITY;
            }
            if(ui_hit((UiRect){196,352,184,56},x,y))m->page=SETTINGS_ROOT;
        }
        return 0;
    }
    if(fresh && ui_hit(UI_SETTINGS_DONE,x,y)) { m->open=0;return 0; }
    if(keys&MENU_UP)m->selected=(m->selected+3)%4;
    else if(keys&MENU_DOWN)m->selected=(m->selected+1)%4;
    int activate=!!(keys&(MENU_ACTIVATE|MENU_LEFT|MENU_RIGHT));
    if(fresh && x>=196 && x<928 && y>=UI_SETTINGS_ROW_Y && y<UI_SETTINGS_ROW_Y+4*UI_SETTINGS_ROW_H) {
        m->selected=(unsigned)(y-UI_SETTINGS_ROW_Y)/UI_SETTINGS_ROW_H;activate=1;
    }
    if(!activate)return 0;
    switch(m->selected) {
        case 0:m->page=SETTINGS_AUDIO;return 0;
        case 1:m->timeout_seconds=display_timeout_cycle(m->timeout_seconds,keys&MENU_LEFT?-1:1);return SETTINGS_DISPLAY;
        case 2:return SETTINGS_ROUTE;
        default:m->open=0;return SETTINGS_DETAILS;
    }
}
