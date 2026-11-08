#include "../src/settings_menu.h"
#include "../src/display_settings.h"
#include "../src/ui_layout.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

static SettingsMenu menu;
static AudioQuality quality;
static int consumed;
static unsigned input(unsigned keys,int fresh,int x,int y) {
    return settings_menu_input(&menu,&quality,keys,fresh,x,y,1,&consumed);
}
int main(void) {
    settings_menu_init(&menu);aq_init(&quality);
    assert(!menu.open && menu.timeout_seconds==60);
    assert(!input(MENU_ACTIVATE,0,0,0) && !consumed); /* Player X is untouched. */
    assert(!input(MENU_OPEN,0,0,0) && consumed && menu.open && quality.tab==1);
    assert(!input(MENU_ACTIVATE,0,0,0) && consumed && menu.page==SETTINGS_AUDIO);
    UiRect choice=ui_quality_choice(5);
    assert(input(0,1,choice.x,choice.y)==SETTINGS_QUALITY && quality.modes[1]==128);
    assert(input(0,1,choice.x+choice.w-1,choice.y+choice.h-1)==SETTINGS_QUALITY);
    assert(!input(0,0,choice.x+10,choice.y+10)); /* Held touch does not cycle. */
    assert(!input(MENU_L,0,0,0) && quality.tab==0);
    assert(input(MENU_RIGHT,0,0,0)==SETTINGS_QUALITY && quality.modes[0]==256);
    assert(!input(MENU_BACK,0,0,0) && menu.open && menu.page==SETTINGS_ROOT);
    assert(!input(MENU_DOWN,0,0,0) && menu.selected==1);
    assert(input(MENU_ACTIVATE,0,0,0)==SETTINGS_DISPLAY && menu.timeout_seconds==120);
    assert(input(MENU_LEFT,0,0,0)==SETTINGS_DISPLAY && menu.timeout_seconds==60);
    assert(!input(MENU_DOWN,0,0,0) && menu.selected==2);
    assert(input(MENU_ACTIVATE,0,0,0)==SETTINGS_ROUTE);
    assert(!input(MENU_DOWN,0,0,0) && menu.selected==3);
    assert(input(MENU_ACTIVATE,0,0,0)==SETTINGS_DETAILS && !menu.open);
    for(unsigned i=0;i<3;++i) {
        input(MENU_OPEN,0,0,0);int y=i==0?UI_NAV_PLAYER.y:i==1?UI_NAV_QUEUE.y:UI_NAV_FAVORITES.y;
        assert(input(0,1,13,y+1)==(SETTINGS_NAV_PLAYER<<i) && !menu.open && consumed);
    }
    input(MENU_OPEN,0,0,0);assert(!input(0,1,UI_SETTINGS_DONE.x+1,UI_SETTINGS_DONE.y+1) && !menu.open && consumed);
    assert(!input(0,1,UI_GEAR.x,UI_GEAR.y) && menu.open && consumed);
    assert(!input(0,1,UI_GEAR.x+UI_GEAR.w-1,UI_GEAR.y+UI_GEAR.h-1) && !menu.open && consumed);
    assert(!input(0,1,UI_GEAR.x-1,UI_GEAR.y) && !menu.open && !consumed);
    unsigned seconds=60;
    assert(display_timeout_cycle(300,1)==0 && display_timeout_cycle(0,1)==30);
    uint8_t valid[]={'V','D','S','1',44,1,0,0};
    assert(display_settings_parse(&seconds,valid,sizeof(valid)) && seconds==300);
    valid[4]=31;valid[5]=0;
    assert(!display_settings_parse(&seconds,valid,sizeof(valid)) && seconds==300);
    assert(!display_settings_parse(&seconds,valid,7) && seconds==300);
    char path[]="/tmp/vita-display-XXXXXX";int fd=mkstemp(path);assert(fd>=0);close(fd);
    assert(display_settings_save(120,path) && display_settings_load(&seconds,path) && seconds==120);
    assert(display_settings_save(0,path) && display_settings_load(&seconds,path) && !seconds);
    assert(!display_settings_save(31,path) && display_settings_load(&seconds,path) && !seconds);
    unlink(path);seconds=60;assert(!display_settings_load(&seconds,path) && seconds==60);
    puts("Settings: isolated menu input, route/quality actions, complete touch targets and persisted validated timeouts passed.");
    return 0;
}
