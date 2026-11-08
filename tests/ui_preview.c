#include "../src/ui.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char **argv) {
    static SpotifyView spotify;
    ReceiverUiState state = {0};
    state.screen_timeout=60;
    state.quality_modes[0]=state.quality_modes[1]=320;
    if(argc>1 && !strncmp(argv[1],"quality",7)) {
        state.quality_open=1;state.quality_tab=strstr(argv[1],"remote")!=NULL;
        state.quality_modes[1]=strstr(argv[1],"auto")?0:128;
        state.opus_bitrate=state.quality_tab?128000:320000;state.buffer_ms=state.quality_tab?1024:256;
        state.connected=state.playing=1;
        state.link.remote_mode=state.quality_tab;
    }
    if(argc>1 && !strncmp(argv[1],"settings",8)) {
        state.settings_open=1;state.settings_selected=1;
        state.screen_timeout=!strcmp(argv[1],"settings-never")?0:120;
        state.quality_modes[1]=0;state.opus_bitrate=320000;state.buffer_ms=1024;
        state.connected=1;state.link.remote_mode=1;
    }
    state.network_ready=1;
    if(argc>1 && !strcmp(argv[1],"capture-error"))state.capture_error=4;
    if(argc>1 && !strcmp(argv[1],"expired"))state.capture_error=8;
    state.link.desired=state.link.paired=1;
    if (argc>1 && !strcmp(argv[1],"pairing"))state.link.paired=0;
    snprintf(state.link.message,sizeof(state.link.message),"Start Vita Audio Host on Windows. This Vita connects automatically.");
    snprintf(state.status, sizeof(state.status),
             "Start the PC sender, then select the Soloist device in Spotify.");
    if (argc>1 && !strcmp(argv[1],"streaming")) {
        state.connected=state.playing=1;
        state.buffer_ms=128; state.played_seconds=147;
        snprintf(state.status, sizeof(state.status),
                 "PC audio connected. Choose music in Spotify on your phone or PC.");
    } else if (argc>1 && !strcmp(argv[1],"muted")) {
        state.connected=state.playing=state.muted=1;
        state.buffer_ms=200; state.played_seconds=99;
        snprintf(state.status, sizeof(state.status), "Audio is muted. Press X to unmute.");
    } else if (argc>1 && !strcmp(argv[1],"error")) {
        state.error=1;
        snprintf(state.status, sizeof(state.status),
                 "Could not initialize receiver. Restart Vita and check Wi-Fi. Press START to exit.");
    } else if (argc>1 && !strcmp(argv[1],"buffering")) {
        state.connected=1; state.buffer_ms=45;
        snprintf(state.status, sizeof(state.status), "Buffering after network interruption");
    } else if (argc>1 && !strcmp(argv[1],"test")) {
        state.testing=1;
        snprintf(state.status, sizeof(state.status), "Playing a short local tone. No computer connection is needed.");
    }
    if (argc>1 && (!strcmp(argv[1],"host") || !strcmp(argv[1],"address"))) {
        snprintf(state.link.ip,sizeof(state.link.ip),"10.1.43.20");
        snprintf(state.link.name,sizeof(state.link.name),"Windows-PC");
        snprintf(state.link.message,sizeof(state.link.message),"Windows host found. Connecting...");
        if (!strcmp(argv[1],"address")) {
            state.link.editing=1;state.link.selected=2;
            state.link.octets[0]=10;state.link.octets[1]=1;state.link.octets[2]=43;state.link.octets[3]=20;
        }
    }
    if (argc>1 && (!strcmp(argv[1],"remote") || !strcmp(argv[1],"remote-details") || !strcmp(argv[1],"remote-missing"))) {
        state.link.remote_mode=1;state.link.remote_available=strcmp(argv[1],"remote-missing")!=0;
        state.link.editing=!strcmp(argv[1],"remote-details");
        snprintf(state.link.remote.audio_host,sizeof(state.link.remote.audio_host),"desktop.example-tailnet.ts.net");
        snprintf(state.link.remote.control_host,sizeof(state.link.remote.control_host),"desktop.example-tailnet.ts.net");
        state.link.remote.audio_port=443;state.link.remote.control_port=8443;
        snprintf(state.link.message,sizeof(state.link.message),"Connecting through saved remote tunnel...");
    }
    uint32_t *pixels=calloc(UI_WIDTH*UI_HEIGHT,sizeof(*pixels));
    if (!pixels) return 1;
    int searching=argc>1 && !strncmp(argv[1],"search",6);
    if (argc>1 && (searching || !strcmp(argv[1],"player") || !strcmp(argv[1],"dim") || !strcmp(argv[1],"black") || !strcmp(argv[1],"browser") || !strcmp(argv[1],"paused") || !strcmp(argv[1],"favorites"))) {
        spotify.online=spotify.api_online=spotify.logged_in=spotify.active=1;
        spotify.status=!strcmp(argv[1],"paused")?2:1; spotify.volume=65; spotify.shuffle=1;
        spotify.duration_ms=210000; spotify.position_ms=45000;
        snprintf(spotify.title,sizeof(spotify.title),"Midnight Current");
        snprintf(spotify.artist,sizeof(spotify.artist),"Mira Wells");
        snprintf(spotify.album,sizeof(spotify.album),"Night Signals");
        spotify.browser=searching || !strcmp(argv[1],"browser") || !strcmp(argv[1],"favorites");
        spotify.tab=!strcmp(argv[1],"favorites");
        spotify.queue_count=8; spotify.selected=1;
        for (int i=0;i<8;++i) {
            static const char *songs[]={"Midnight Current","Somewhere Quiet","Afterimage","Slow Motion","All the Way Home","Ocean Drive","Late Checkout","Soft Focus"};
            snprintf(spotify.queue[i].title,128,"%s",songs[i]);
            snprintf(spotify.queue[i].artist,128,"Mira Wells · Night Signals");
            spotify.queue[i].position=(unsigned)i+1;
        }
        spotify.queue_paged=1;spotify.queue_available=spotify.queue_total=80;spotify.queue_count=5;
        if(searching) {
            strcpy(spotify.queue_query,"quiet");spotify.queue_total=spotify.queue_count=1;spotify.selected=0;
            strcpy(spotify.queue[0].title,"Somewhere Quiet");spotify.queue[0].position=38;
            if(!strcmp(argv[1],"search-keyboard"))search_keyboard_open(&spotify.keyboard,"mira");
            if(!strcmp(argv[1],"search-empty")) { strcpy(spotify.queue_query,"unheard");spotify.queue_total=spotify.queue_count=0; }
            if(!strcmp(argv[1],"search-far")) {
                spotify.queue_confirm=1;spotify.confirm_distance=38;strcpy(spotify.confirm_title,"Somewhere Quiet");
            }
            if(!strcmp(argv[1],"search-progress")) { spotify.jump_total=79;spotify.jump_done=38; }
            if(!strcmp(argv[1],"search-large")) {
                spotify.queue_available=5000;spotify.queue_total=240;spotify.queue_count=5;spotify.queue_offset=95;
                strcpy(spotify.queue_query,"signals");
                for(unsigned i=0;i<5;++i)spotify.queue[i].position=2001+i*4;
            }
        }
        if (spotify.tab) {
            spotify.selected=0;spotify.favorite_count=3;
            snprintf(spotify.favorites[0].title,128,"Evening rotation");
            snprintf(spotify.favorites[0].artist,128,"Playlist");
            snprintf(spotify.favorites[0].uri,128,"spotify:playlist:0123456789abcdefghijkl");
            snprintf(spotify.favorites[1].title,128,"Night Signals");
            snprintf(spotify.favorites[1].artist,128,"Album · Mira Wells");
            snprintf(spotify.favorites[2].title,128,"Midnight Current");
            snprintf(spotify.favorites[2].artist,128,"Song · Mira Wells");
        }
        /* Original procedural cover fixture, not Spotify artwork. */
        spotify.has_art=1;
        for(unsigned y=0;y<CTL_ART_EDGE;++y)for(unsigned x=0;x<CTL_ART_EDGE;++x) {
            unsigned r=8+y/9,g=24+x/5,b=31+y/4;
            int dx=(int)x-104,dy=(int)y-110,d=dx*dx+dy*dy;
            if(d<8100 && d>7056) { r=35;g=184;b=139; }
            if((int)y>(int)x/2+50 && (int)y<(int)x/2+85) { r=28;g=132+y/4;b=142+x/7; }
            if(d<180) { r=208;g=229;b=211; }
            spotify.art[y*CTL_ART_EDGE+x]=(uint16_t)(((r>>3)<<11)|((g>>2)<<5)|(b>>3));
        }
        state.connected=state.playing=1; state.buffer_ms=256;state.opus_bitrate=320000;
        ui_render_player(pixels,&state,"10.1.43.227",&spotify);
    } else ui_render_frame(pixels,&state,state.error?"Unavailable":"10.1.43.227");
    if (argc>1 && !strcmp(argv[1],"dim"))ui_apply_screen(pixels,SCREEN_DIM);
    if (argc>1 && !strcmp(argv[1],"black"))ui_apply_screen(pixels,SCREEN_BLACK);
    printf("P6\n%d %d\n255\n",UI_WIDTH,UI_HEIGHT);
    for (unsigned i=0;i<UI_WIDTH*UI_HEIGHT;++i) {
        unsigned char rgb[]={pixels[i]&255,(pixels[i]>>8)&255,(pixels[i]>>16)&255};
        fwrite(rgb,1,3,stdout);
    }
    free(pixels);
    return 0;
}
