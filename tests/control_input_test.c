#define CONTROL_INPUT_TEST
#include "../src/control.c"
#include <assert.h>
#include <stdio.h>
int main(void) {
    state_mutex=1;shared.browser=1;shared.tab=0;shared.queue_count=3;shared.selected=2;
    strcpy(shared.queue[2].uri,"q:0123456789abcdef0123456789abcdef");
    uint8_t out[CTL_COMMAND_BYTES+8];
    assert(make_command((Input){1,SCE_CTRL_CROSS,0,0},out)==CTL_COMMAND_BYTES+8);
    assert(!memcmp(out,"CMND",4) && ctl_read32(out+8)==CTL_PLAY_QUEUE && !shared.browser);
    assert(!strcmp((const char *)out+16,shared.queue[2].uri));
    shared.browser=1;shared.tab=1;shared.favorite_count=1;shared.selected=0;
    strcpy(shared.favorites[0].uri,"spotify:track:0123456789abcdef012345");
    assert(make_command((Input){1,SCE_CTRL_CROSS,0,0},out)>0);
    assert(ctl_read32(out+8)==CTL_PLAY_URI && !shared.browser);
    shared.browser=1;shared.tab=0;shared.selected=0;
    assert(make_command((Input){2,UI_LIST_X,UI_LIST_Y+2*UI_LIST_ROW_H+55,1},out)>0);
    assert(ctl_read32(out+8)==CTL_PLAY_QUEUE && shared.selected==2);
    for(unsigned tab=0;tab<2;++tab) {
        shared.browser=1;shared.tab=tab;
        assert(make_command((Input){1,SCE_CTRL_LTRIGGER,0,0},out)>0 && ctl_read32(out+8)==CTL_PREV);
        assert(shared.browser && shared.tab==tab);
        assert(make_command((Input){1,SCE_CTRL_RTRIGGER,0,0},out)>0 && ctl_read32(out+8)==CTL_NEXT);
        assert(shared.browser && shared.tab==tab);
        assert(make_command((Input){1,SCE_CTRL_SQUARE,0,0},out)>0 && ctl_read32(out+8)==CTL_SHUFFLE);
        assert(!make_command((Input){1,SCE_CTRL_LEFT,0,0},out) && shared.tab!=tab);
    }
    UiRect targets[]={UI_PREVIOUS,UI_PLAY,UI_NEXT,UI_SHUFFLE,UI_REPEAT};
    unsigned ops[]={CTL_PREV,CTL_TOGGLE,CTL_NEXT,CTL_SHUFFLE,CTL_REPEAT};
    for(unsigned page=0;page<3;++page)for(unsigned i=0;i<5;++i)for(unsigned corner=0;corner<4;++corner) {
        shared.browser=page>0;shared.tab=page==2;
        int x=targets[i].x+(corner&1?targets[i].w-1:0),y=targets[i].y+(corner&2?targets[i].h-1:0);
        assert(make_command((Input){2,x,y,1},out)>0 && ctl_read32(out+8)==ops[i]);
        assert(shared.browser==(page>0) && shared.tab==(page==2));
        assert(!make_command((Input){2,x,y,0},out));
    }
    shared.browser=0;
    assert(make_command((Input){1,SCE_CTRL_TRIANGLE,0,0},out)>0 && shared.browser && shared.tab==0);
    assert(make_command((Input){1,SCE_CTRL_TRIANGLE,0,0},out)>0 && shared.browser && shared.tab==1);
    assert(!make_command((Input){1,SCE_CTRL_TRIANGLE,0,0},out) && !shared.browser);
    assert(make_command((Input){3,1,0,0},out)>0 && shared.browser && !shared.tab);
    shared.queue_count=12;shared.selected=0;
    assert(!make_command((Input){2,UI_PAGE_DOWN.x,UI_PAGE_DOWN.y,1},out) && shared.selected==5);
    assert(!make_command((Input){2,UI_PAGE_DOWN.x,UI_PAGE_DOWN.y,1},out) && shared.selected==10);
    assert(!make_command((Input){2,UI_PAGE_UP.x,UI_PAGE_UP.y,1},out) && shared.selected==5);
    assert(!make_command((Input){2,UI_LIST_X-1,UI_LIST_Y+10,1},out));
    shared.duration_ms=200000;
    assert(make_command((Input){2,UI_SEEK.x,UI_SEEK.y,1},out)>0 && ctl_read32(out+8)==CTL_SEEK && !ctl_read32(out+12));
    assert(make_command((Input){2,UI_SEEK.x+UI_SEEK.w-1,UI_SEEK.y+UI_SEEK.h-1,1},out)>0 && ctl_read32(out+12)==200000);
    assert(make_command((Input){2,UI_VOLUME.x,UI_VOLUME.y,0},out)>0 && ctl_read32(out+8)==CTL_VOLUME && !ctl_read32(out+12));
    assert(make_command((Input){2,UI_VOLUME.x+UI_VOLUME.w-1,UI_VOLUME.y+UI_VOLUME.h-1,0},out)>0 && ctl_read32(out+12)==100);
    shared.volume=57;
    assert(make_command((Input){2,UI_VOLUME_MUTE.x,UI_VOLUME_MUTE.y,1},out)>0 && !ctl_read32(out+12));
    shared.volume=0;
    assert(make_command((Input){2,UI_VOLUME_MUTE.x,UI_VOLUME_MUTE.y,1},out)>0 && ctl_read32(out+12)==57);
    assert(!make_command((Input){1,SCE_CTRL_SELECT,0,0},out));
    shared.browser=1;shared.tab=0;shared.queue_paged=1;shared.queue_count=5;shared.queue_total=80;
    shared.queue_available=80;shared.queue_offset=0;shared.selected=4;shared.queue_loading=0;
    assert(make_command((Input){1,SCE_CTRL_DOWN,0,0},out)>0 && ctl_read32(out+8)==CTL_QUEUE_PAGE && ctl_read32(out+12)==5);
    assert(shared.queue_loading && shared.queue_wanted_offset==5);
    assert(!make_command((Input){1,SCE_CTRL_CROSS,0,0},out)); /* Do not play old page while waiting. */
    shared.queue_loading=0;
    assert(!make_command((Input){1,SCE_CTRL_SQUARE,0,0},out) && shared.keyboard.open);
    strcpy(shared.keyboard.text,"song");
    assert(make_command((Input){1,SCE_CTRL_RTRIGGER,0,0},out)>0 && ctl_read32(out+8)==CTL_QUEUE_SEARCH);
    assert(!strcmp((const char *)out+16,"song") && shared.queue_request_id==1 && shared.queue_loading);
    shared.queue_loading=0;shared.selected=0;shared.queue[0].position=79;strcpy(shared.queue[0].uri,"q:test-token");
    assert(!make_command((Input){1,SCE_CTRL_CROSS,0,0},out) && shared.queue_confirm);
    assert(!make_command((Input){1,SCE_CTRL_CIRCLE,0,0},out) && !shared.queue_confirm && shared.browser);
    assert(!make_command((Input){1,SCE_CTRL_CROSS,0,0},out) && shared.queue_confirm);
    assert(make_command((Input){1,SCE_CTRL_CROSS,0,0},out)>0 && ctl_read32(out+8)==CTL_PLAY_QUEUE && !shared.browser);
    assert(!strcmp((const char *)out+16,"q:test-token"));
    shared.jump_total=79;
    assert(make_command((Input){1,SCE_CTRL_CIRCLE,0,0},out)>0 && ctl_read32(out+8)==CTL_QUEUE_CANCEL);
    puts("Control input: queue-preserving selection, global shoulder/transport actions, page navigation and expanded touch-edge/drag behavior passed.");
    return 0;
}
