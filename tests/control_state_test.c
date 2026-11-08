#include "../src/control.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static SpotifyView view;
static uint8_t data[CTL_MAX_PAYLOAD];
int main(void) {
    ctl_write32(data,1); ctl_write32(data+4,1); ctl_write32(data+8,1);
    ctl_write32(data+12,1); ctl_write32(data+16,1); ctl_write32(data+20,65);
    ctl_write32(data+24,1); ctl_write32(data+28,2); ctl_write32(data+32,45000);
    ctl_write32(data+36,210000); ctl_write32(data+40,123);
    strcpy((char *)data+44,"Test title");
    assert(ctl_apply(&view,(const uint8_t *)"STAT",data,CTL_STATE_BYTES));
    assert(view.online && view.status==1 && view.volume==65 && view.art_id==123);
    assert(!strcmp(view.title,"Test title") && view.position_ms==45000);
    ctl_write32(data+20,101);
    assert(!ctl_apply(&view,(const uint8_t *)"STAT",data,CTL_STATE_BYTES));
    assert(view.volume==65); /* Invalid frames must not partially change state. */
    assert(!ctl_apply(&view,(const uint8_t *)"STAT",data,CTL_STATE_BYTES-1));
    assert(!ctl_frame_valid((const uint8_t *)"ARTW",CTL_MAX_PAYLOAD+1));
    memset(data,0,sizeof(data)); ctl_write32(data,33);
    assert(!ctl_apply(&view,(const uint8_t *)"QUEU",data,4));
    ctl_write32(data,1); memset(data+4,'x',CTL_ITEM_BYTES);
    assert(ctl_apply(&view,(const uint8_t *)"QUEU",data,4+CTL_ITEM_BYTES));
    assert(view.queue_count==1 && view.queue[0].title[127]==0 && view.queue[0].uri[127]==0);
    assert(!ctl_apply(&view,(const uint8_t *)"FAVS",data,4));
    memset(data,0,sizeof(data)); ctl_write32(data,122);
    assert(ctl_apply(&view,(const uint8_t *)"ARTW",data,CTL_ART_BYTES+4));
    assert(!view.has_art); /* An older track's artwork must not replace this cover. */
    ctl_write32(data,123); data[4]=0; data[5]=0xf8;
    assert(ctl_apply(&view,(const uint8_t *)"ARTW",data,CTL_ART_BYTES+4));
    assert(view.has_art && view.art[0]==0xf800);
    memset(data,0,sizeof(data));ctl_write32(data,123);ctl_write32(data+4,0);
    memset(data+8,0x12,2048);
    assert(ctl_apply(&view,(const uint8_t *)"ARTC",data,2056));
    assert(!view.has_art && view.art_received==2048);
    ctl_write32(data+4,2050);
    assert(!ctl_apply(&view,(const uint8_t *)"ARTC",data,10));
    for (unsigned offset=2048;offset<CTL_ART_BYTES;offset+=2048) {
        unsigned bytes=CTL_ART_BYTES-offset;if (bytes>2048)bytes=2048;
        ctl_write32(data+4,offset);
        assert(ctl_apply(&view,(const uint8_t *)"ARTC",data,8+bytes));
    }
    assert(view.has_art && view.art_received==CTL_ART_BYTES && view.art[0]==0x1212);
    ctl_write32(data+4,0xffffffffu);
    assert(!ctl_apply(&view,(const uint8_t *)"ARTC",data,10));
    assert(!ctl_frame_valid((const uint8_t *)"ARTC",11));
    assert(!ctl_apply(&view,(const uint8_t *)"BOOM",data,8));
    uint8_t flush[8];ctl_write32(flush,12345);ctl_write32(flush+4,1);
    assert(ctl_apply(&view,(const uint8_t *)"AFLU",flush,8));
    assert(view.audio_flush_id==12345 && view.audio_flush_hold==1);
    ctl_write32(flush+4,0);assert(ctl_apply(&view,(const uint8_t *)"AFLU",flush,8));assert(!view.audio_flush_hold);
    ctl_write32(flush+4,2);assert(!ctl_apply(&view,(const uint8_t *)"AFLU",flush,8));assert(!view.audio_flush_hold);
    ctl_write32(flush,0);ctl_write32(flush+4,0);assert(!ctl_apply(&view,(const uint8_t *)"AFLU",flush,8));
    assert(!ctl_frame_valid((const uint8_t *)"AFLU",7) && !ctl_frame_valid((const uint8_t *)"AFLU",9));
    memset(data,0,sizeof(data));
    ctl_write32(data+4,1);ctl_write32(data+8,35);ctl_write32(data+12,80);ctl_write32(data+16,80);ctl_write32(data+24,5);
    for(unsigned i=0;i<5;++i) { ctl_write32(data+156+i*388,36+i);strcpy((char *)data+160+i*388,"Found song"); }
    assert(ctl_apply(&view,(const uint8_t *)"QPAG",data,2096));
    assert(view.queue_paged && view.queue_offset==35 && view.queue_available==80 && view.queue_count==5);
    assert(view.queue[4].position==40);
    view.queue_request_id=9;view.queue_loading=1;view.queue_wanted_offset=75;view.queue_select_last=1;
    assert(ctl_apply(&view,(const uint8_t *)"QPAG",data,2096) && view.queue_loading && view.queue_offset==35);
    ctl_write32(data,9);ctl_write32(data+8,0);
    assert(ctl_apply(&view,(const uint8_t *)"QPAG",data,2096) && view.queue_loading);
    ctl_write32(data+8,75);
    for(unsigned i=0;i<5;++i)ctl_write32(data+156+i*388,76+i);
    assert(ctl_apply(&view,(const uint8_t *)"QPAG",data,2096));
    assert(!view.queue_loading && view.queue_offset==75 && view.selected==4 && view.queue[4].position==80);
    ctl_write32(data+156,81);assert(!ctl_apply(&view,(const uint8_t *)"QPAG",data,2096));
    assert(view.queue[0].position==76);ctl_write32(data+156,76);
    ctl_write32(data+24,6);assert(!ctl_apply(&view,(const uint8_t *)"QPAG",data,2096));ctl_write32(data+24,5);
    data[155]=1;assert(!ctl_apply(&view,(const uint8_t *)"QPAG",data,2096));data[155]=0;
    ctl_write32(data+20,4);assert(!ctl_apply(&view,(const uint8_t *)"QPAG",data,2096));
    assert(!ctl_frame_valid((const uint8_t *)"QPAG",2097));
    ctl_write32(data,3);ctl_write32(data+4,79);assert(ctl_apply(&view,(const uint8_t *)"QJMP",data,8));
    assert(view.jump_done==3 && view.jump_total==79);
    ctl_write32(data+4,257);assert(!ctl_apply(&view,(const uint8_t *)"QJMP",data,8) && view.jump_total==79);
    ctl_write32(data,0);ctl_write32(data+4,0);assert(ctl_apply(&view,(const uint8_t *)"QJMP",data,8) && !view.jump_total);
    puts("Control state: field validation, list bounds, stale artwork and audio markers passed.");
    return 0;
}
