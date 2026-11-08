#include "screen_policy.h"
#include "display_settings.h"
#include <string.h>

void screen_policy_init(ScreenPolicy *state,uint64_t now) {
    memset(state,0,sizeof(*state));state->last_activity=now;state->timeout_seconds=60;
}
void screen_policy_set_timeout(ScreenPolicy *state,unsigned seconds) {
    if(display_timeout_valid(seconds))state->timeout_seconds=seconds;
}
int screen_policy_step(ScreenPolicy *state,uint64_t now,unsigned buttons,
                       unsigned *pressed,int touching,int fresh_touch,int x,int y) {
    state->blocked_buttons&=buttons;
    if (!touching)state->blocked_touch=0;
    *pressed&=~state->blocked_buttons;
    int activity=(*pressed!=0 || (touching && !state->blocked_touch));
    if (state->mode==SCREEN_BLACK) {
        if (activity) {
            state->mode=SCREEN_ACTIVE;state->last_activity=now;
            state->blocked_buttons=buttons;state->blocked_touch=touching;
        }
        *pressed=0;return 1;
    }
    if (activity || (buttons & ~state->blocked_buttons)) {
        state->last_activity=now;state->mode=SCREEN_ACTIVE;
    } else {
        uint64_t idle=now>=state->last_activity?now-state->last_activity:0;
        uint64_t off=(uint64_t)state->timeout_seconds*1000000ULL;
        uint64_t dim=off && off/2<SCREEN_DIM_US?off/2:SCREEN_DIM_US;
        state->mode=off && idle>=off?SCREEN_BLACK:idle>=dim?SCREEN_DIM:SCREEN_ACTIVE;
    }
    if (fresh_touch && !state->blocked_touch &&
        x>=SCREEN_BUTTON_X && x<SCREEN_BUTTON_X+SCREEN_BUTTON_W &&
        y>=SCREEN_BUTTON_Y && y<SCREEN_BUTTON_Y+SCREEN_BUTTON_H) {
        state->mode=SCREEN_BLACK;state->blocked_touch=1;
        state->blocked_buttons=buttons;*pressed=0;return 1;
    }
    if (state->blocked_touch || state->blocked_buttons || state->mode==SCREEN_BLACK) {
        *pressed=0;return 1;
    }
    return 0;
}
