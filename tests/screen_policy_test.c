#include "../src/screen_policy.h"
#include <assert.h>
#include <stdio.h>

int main(void) {
    ScreenPolicy s;unsigned press=0;
    screen_policy_init(&s,100);
    assert(!screen_policy_step(&s,100+SCREEN_DIM_US-1,0,&press,0,0,0,0));
    assert(s.mode==SCREEN_ACTIVE);
    screen_policy_step(&s,100+SCREEN_DIM_US,0,&press,0,0,0,0);
    assert(s.mode==SCREEN_DIM);
    screen_policy_step(&s,100+SCREEN_BLACK_US,0,&press,0,0,0,0);
    assert(s.mode==SCREEN_BLACK);
    /* A wake button is consumed, including START/X, and cannot be held through
       into a transport action. A later independent press works as normal. */
    press=8;assert(screen_policy_step(&s,70000000,8,&press,0,0,0,0));
    assert(s.mode==SCREEN_ACTIVE && !press);
    press=16;assert(screen_policy_step(&s,70000001,8|16,&press,0,0,0,0));assert(!press);
    press=0;screen_policy_step(&s,70000002,0,&press,0,0,0,0);
    press=8;assert(!screen_policy_step(&s,70000003,8,&press,0,0,0,0));assert(press==8);
    /* A playing track, queue update or advancing clock is no input and must
       never keep the panel lit. Only real interaction resets the idle timer. */
    press=0;screen_policy_step(&s,70000004,0,&press,0,0,0,0);
    screen_policy_step(&s,130000003,0,&press,0,0,0,0);assert(s.mode==SCREEN_BLACK);
    /* Touch wakes without seeking; dragging the wake touch remains suppressed. */
    assert(screen_policy_step(&s,130000004,0,&press,1,1,500,300));
    assert(s.mode==SCREEN_ACTIVE);
    assert(screen_policy_step(&s,130000005,0,&press,1,0,600,300));
    screen_policy_step(&s,130000006,0,&press,0,0,0,0);
    assert(!screen_policy_step(&s,130000007,0,&press,1,1,600,300));
    /* The manual button works on all pages and its held touch cannot wake it. */
    screen_policy_step(&s,130000008,0,&press,0,0,0,0);
    assert(screen_policy_step(&s,130000009,0,&press,1,1,SCREEN_BUTTON_X+1,SCREEN_BUTTON_Y+1));
    assert(s.mode==SCREEN_BLACK);
    assert(screen_policy_step(&s,130000010,0,&press,1,0,500,300));assert(s.mode==SCREEN_BLACK);
    screen_policy_step(&s,130000011,0,&press,0,0,0,0);
    screen_policy_step(&s,130000012,0,&press,1,1,500,300);assert(s.mode==SCREEN_ACTIVE);
    /* An input in the dimmed state can perform its normal transport action. */
    screen_policy_step(&s,130000013,0,&press,0,0,0,0);
    screen_policy_step(&s,160000012,0,&press,0,0,0,0);assert(s.mode==SCREEN_DIM);
    press=16;assert(!screen_policy_step(&s,160000013,16,&press,0,0,0,0));
    assert(s.mode==SCREEN_ACTIVE && press==16);
    puts("Screen policy: idle timing, manual off, wake-only gestures and held-input suppression passed.");
    screen_policy_init(&s,0);screen_policy_set_timeout(&s,30);press=0;
    screen_policy_step(&s,14999999,0,&press,0,0,0,0);assert(s.mode==SCREEN_ACTIVE);
    screen_policy_step(&s,15000000,0,&press,0,0,0,0);assert(s.mode==SCREEN_DIM);
    screen_policy_step(&s,30000000,0,&press,0,0,0,0);assert(s.mode==SCREEN_BLACK);
    screen_policy_init(&s,0);screen_policy_set_timeout(&s,120);
    screen_policy_step(&s,60000000,0,&press,0,0,0,0);assert(s.mode==SCREEN_DIM);
    screen_policy_step(&s,120000000,0,&press,0,0,0,0);assert(s.mode==SCREEN_BLACK);
    screen_policy_init(&s,0);screen_policy_set_timeout(&s,0);
    screen_policy_step(&s,600000000,0,&press,0,0,0,0);assert(s.mode==SCREEN_DIM);
    screen_policy_set_timeout(&s,31);assert(!s.timeout_seconds);
    assert(screen_policy_step(&s,600000001,0,&press,1,1,SCREEN_BUTTON_X+SCREEN_BUTTON_W-1,SCREEN_BUTTON_Y+SCREEN_BUTTON_H-1));
    assert(s.mode==SCREEN_BLACK);
    return 0;
}
