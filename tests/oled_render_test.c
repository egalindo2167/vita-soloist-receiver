#include "../src/ui.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void) {
    const unsigned count=UI_WIDTH*UI_HEIGHT;
    uint32_t *pixels=malloc((count+2)*sizeof(*pixels));assert(pixels);
    pixels[0]=pixels[count+1]=0x12345678;
    ReceiverUiState state={0};SpotifyView *view=calloc(1,sizeof(*view));assert(view);
    state.network_ready=1;state.link.desired=1;
    ui_render_player(pixels+1,&state,"10.1.43.227",view);
    unsigned black=0;
    for (unsigned i=1;i<=count;++i)if(pixels[i]==0xff000000)++black;
    assert(black>count*85/100);
    assert(pixels[0]==0x12345678 && pixels[count+1]==0x12345678);
    pixels[1]=0xffccbbaa;ui_apply_screen(pixels+1,SCREEN_DIM);
    assert(pixels[1]==0xff332e2a);
    ui_apply_screen(pixels+1,SCREEN_BLACK);
    for(unsigned i=1;i<=count;++i)assert(pixels[i]==0xff000000);
    assert(pixels[0]==0x12345678 && pixels[count+1]==0x12345678);
    state.link.remote_mode=1;
    for (unsigned mode=0;mode<3;++mode) {
        state.link.remote_available=mode>0;state.link.editing=mode==2;
        memset(state.link.remote.audio_host,'a',253);state.link.remote.audio_host[253]=0;
        memset(state.link.remote.control_host,'b',253);state.link.remote.control_host[253]=0;
        state.link.remote.audio_port=state.link.remote.control_port=65535;
        ui_render_player(pixels+1,&state,"10.1.43.227",view);
        assert(pixels[0]==0x12345678 && pixels[count+1]==0x12345678);
    }
    state.quality_open=1;state.quality_modes[0]=320;state.quality_modes[1]=128;state.opus_bitrate=128000;
    for(unsigned tab=0;tab<2;++tab) {
        state.quality_tab=tab;ui_render_player(pixels+1,&state,"ip",view);
        assert(pixels[0]==0x12345678 && pixels[count+1]==0x12345678);
        ui_apply_screen(pixels+1,SCREEN_BLACK);
        for(unsigned i=1;i<=count;++i)assert(pixels[i]==0xff000000);
    }
    state.quality_open=0;state.link.editing=0;view->online=1;
    for(unsigned code=1;code<=8;++code) {
        state.capture_error=code;ui_render_player(pixels+1,&state,"ip",view);
        assert(pixels[0]==0x12345678 && pixels[count+1]==0x12345678);
        black=0;for(unsigned i=1;i<=count;++i)if(pixels[i]==0xff000000)++black;
        assert(black>count*90/100);
    }
    state.capture_error=0;state.screen_timeout=60;
    for(unsigned page=0;page<3;++page) {
        view->browser=page>0;view->tab=page==2;view->queue_count=view->favorite_count=32;view->selected=31;
        memset(view->title,'W',sizeof(view->title)-1);memset(view->artist,'W',sizeof(view->artist)-1);
        for(unsigned i=0;i<32;++i) {
            memset(view->queue[i].title,'W',127);memset(view->favorites[i].title,'W',127);
        }
        ui_render_player(pixels+1,&state,"ip",view);
        assert(pixels[0]==0x12345678 && pixels[count+1]==0x12345678);
        assert(pixels[1]==0xff000000); /* Exact black, including outside text/art bounds. */
    }
    for(unsigned selected=0;selected<4;++selected) {
        state.settings_open=1;state.settings_selected=selected;
        ui_render_player(pixels+1,&state,"ip",view);
        assert(pixels[0]==0x12345678 && pixels[count+1]==0x12345678);
        ui_apply_screen(pixels+1,SCREEN_BLACK);
        for(unsigned i=1;i<=count;++i)assert(pixels[i]==0xff000000);
    }
    state.settings_open=0;view->browser=0;view->has_art=1;
    strcpy(view->title,"Canción · Étoile — long title with ellipsis…");
    ui_render_player(pixels+1,&state,"ip",view);
    assert(pixels[0]==0x12345678 && pixels[count+1]==0x12345678);
    view->browser=1;view->tab=0;view->queue_paged=1;view->queue_total=view->queue_available=10000;
    view->queue_offset=9995;view->queue_count=5;
    for(unsigned i=0;i<5;++i)view->queue[i].position=9996+i;
    for(unsigned mode=0;mode<4;++mode) {
        view->keyboard.open=mode==1;view->queue_confirm=mode==2;view->jump_total=mode==3?256:0;view->jump_done=128;
        memset(view->keyboard.text,'W',127);view->keyboard.text[127]=0;
        memset(view->queue_query,'W',127);view->queue_query[127]=0;
        memset(view->confirm_title,'W',127);view->confirm_title[127]=0;view->confirm_distance=256;
        ui_render_player(pixels+1,&state,"ip",view);
        assert(pixels[0]==0x12345678 && pixels[count+1]==0x12345678);
        ui_apply_screen(pixels+1,SCREEN_BLACK);
        for(unsigned i=1;i<=count;++i)assert(pixels[i]==0xff000000);
    }
    free(view);free(pixels);
    puts("OLED renderer: true-black background, whole-frame dimming, fully blank idle frame and bounds passed.");
    return 0;
}
