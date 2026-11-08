#include "ui.h"
#include "ui_draw.h"
#include "version.h"
#include "protocol.h"
#include "settings_menu.h"
#include <stdio.h>
#include <string.h>

#define RGB UI_RGB
#define BG RGB(0,0,0)
#define INK RGB(225,231,227)
#define SOFT RGB(146,158,151)
#define FAINT RGB(77,91,82)
#define LINE RGB(24,34,28)
#define SELECTED RGB(10,22,15)
#define GREEN RGB(30,210,112)
#define AMBER RGB(218,175,92)
#define RED RGB(223,116,124)

static void box(uint32_t *p,UiRect r,uint32_t c) { ud_rect(p,r,c); }
static void label(uint32_t *p,int x,int y,unsigned font,uint32_t c,const char *s,int w) {
    ud_text(p,x,y,font,c,s,w);
}
static void right_text(uint32_t *p,int right,int y,unsigned font,uint32_t c,const char *s,int w) {
    int width=ud_width(font,s);if(width>w)width=w;label(p,right-width,y,font,c,s,width);
}
static void outline(uint32_t *p,UiRect r,uint32_t c) {
    box(p,(UiRect){r.x,r.y,r.w,1},c);box(p,(UiRect){r.x,r.y+r.h-1,r.w,1},c);
    box(p,(UiRect){r.x,r.y,1,r.h},c);box(p,(UiRect){r.x+r.w-1,r.y,1,r.h},c);
}
static void clock_text(char *out,size_t n,unsigned ms) { snprintf(out,n,"%u:%02u",ms/60000,(ms/1000)%60); }
static void timeout_text(char *out,size_t n,unsigned seconds) {
    if(!seconds)snprintf(out,n,"Never (dims)");
    else if(seconds<60)snprintf(out,n,"%u seconds",seconds);
    else snprintf(out,n,"%u minute%s",seconds/60,seconds==60?"":"s");
}
void ui_apply_screen(uint32_t *p,int mode) {
    if(mode==SCREEN_BLACK)box(p,(UiRect){0,0,UI_WIDTH,UI_HEIGHT},BG);
    else if(mode==SCREEN_DIM)for(unsigned i=0;i<UI_WIDTH*UI_HEIGHT;++i)p[i]=0xff000000u|((p[i]&0xfcfcfcu)>>2);
}
static void navigation(uint32_t *p,UiRect r,int icon,const char *name,int active) {
    if(active)ud_round(p,r,10,SELECTED);
    ud_icon(p,icon,r.x+20,r.y+r.h/2,23,active?GREEN:SOFT);
    label(p,r.x+42,r.y+17,UF_BODY,active?INK:SOFT,name,r.w-44);
}
static void sidebar(uint32_t *p,const ReceiverUiState *s,int page,const SpotifyView *spotify) {
    box(p,(UiRect){168,20,1,504},LINE);
    box(p,(UiRect){24,31,3,15},GREEN);box(p,(UiRect){31,25,3,27},GREEN);box(p,(UiRect){38,29,3,19},GREEN);
    label(p,54,25,UF_BODY,INK,"Vita Audio",108);label(p,55,51,UF_SMALL,FAINT,"RECEIVER",100);
    navigation(p,UI_NAV_PLAYER,ICON_PLAYER,"Now playing",page==0);
    navigation(p,UI_NAV_QUEUE,ICON_QUEUE,"Queue",page==1);
    navigation(p,UI_NAV_FAVORITES,ICON_HEART,"Favorites",page==2);
    if(page>0 && spotify) {
        unsigned count=spotify->tab?spotify->favorite_count:spotify->queue_count;
        unsigned first=spotify->selected/UI_LIST_ROWS*UI_LIST_ROWS;
        if(!spotify->tab && spotify->queue_paged) { count=spotify->queue_total;first=spotify->queue_offset; }
        unsigned end=first+UI_LIST_ROWS;if(end>count)end=count;
        char number[40];snprintf(number,sizeof(number),"%u–%u of %u",count?first+1:0,end,count);
        label(p,24,327,UF_SMALL,SOFT,number,126);
        ud_icon(p,ICON_UP,52,386,26,first?INK:FAINT);ud_icon(p,ICON_DOWN,120,386,26,end<count?INK:FAINT);
    } else {
        char codec[32];
        if(s->opus_bitrate)snprintf(codec,sizeof(codec),"%s %u kbps",s->quality_modes[!!s->link.remote_mode]?"Opus":"Auto ·",s->opus_bitrate/1000);
        else snprintf(codec,sizeof(codec),"%s",s->connected?"PCM audio":"Ready to connect");
        label(p,24,343,UF_SMALL,SOFT,codec,128);
        label(p,24,369,UF_SMALL,FAINT,s->link.remote_mode?"Remote · TLS 1.3":"Local · TLS 1.3",128);
    }
    ud_icon(p,ICON_MOON,37,462,23,SOFT);label(p,60,453,UF_SMALL,SOFT,"Screen off",94);
    char version[28];snprintf(version,sizeof(version),"Version %s",RECEIVER_VERSION);label(p,24,508,UF_SMALL,FAINT,version,130);
}
static void shell(uint32_t *p,const ReceiverUiState *s,int page,const SpotifyView *spotify,const char *title,const char *hint,int gear) {
    box(p,(UiRect){0,0,UI_WIDTH,UI_HEIGHT},BG);sidebar(p,s,page,spotify);
    label(p,196,25,UF_TITLE,INK,title,510);label(p,198,72,UF_SMALL,SOFT,hint,726);
    ud_circle(p,740,43,3,s->connected?GREEN:FAINT);label(p,753,32,UF_SMALL,SOFT,s->link.remote_mode?"REMOTE":"LOCAL",106);
    if(gear)ud_round(p,UI_GEAR,30,SELECTED);
    ud_icon(p,ICON_GEAR,914,44,28,gear?GREEN:SOFT);
}
static void artwork(uint32_t *p,const SpotifyView *s) {
    const int left=204,top=110;
    if(s->has_art) {
        for(unsigned y=0;y<CTL_ART_EDGE;++y)for(unsigned x=0;x<CTL_ART_EDGE;++x) {
            int dx=x<9?9-(int)x:x>=CTL_ART_EDGE-9?(int)x-(CTL_ART_EDGE-10):0;
            int dy=y<9?9-(int)y:y>=CTL_ART_EDGE-9?(int)y-(CTL_ART_EDGE-10):0;
            if(dx && dy && dx*dx+dy*dy>81)continue;
            uint16_t a=s->art[y*CTL_ART_EDGE+x];unsigned r=(a>>11)&31,g=(a>>5)&63,b=a&31;
            p[(top+y)*UI_WIDTH+left+x]=RGB((r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2));
        }
    } else {
        outline(p,(UiRect){left,top,224,224},LINE);ud_icon(p,ICON_MUSIC,left+112,top+102,62,GREEN);
        label(p,left+59,top+172,UF_SMALL,SOFT,"Spotify Connect",125);
    }
}
static void transport(uint32_t *p,const SpotifyView *s) {
    char time[20];box(p,(UiRect){UI_PROGRESS_X,412,UI_PROGRESS_W,4},LINE);
    unsigned progress=s->duration_ms?(unsigned)((uint64_t)s->position_ms*UI_PROGRESS_W/s->duration_ms):0;
    if(progress>UI_PROGRESS_W)progress=UI_PROGRESS_W;
    if(progress)box(p,(UiRect){UI_PROGRESS_X,412,(int)progress,4},GREEN);
    ud_circle(p,UI_PROGRESS_X+(float)progress,414,4.5f,INK);
    clock_text(time,sizeof(time),s->position_ms);label(p,204,427,UF_SMALL,SOFT,time,100);
    clock_text(time,sizeof(time),s->duration_ms);right_text(p,908,427,UF_SMALL,SOFT,time,100);
    label(p,196,466,UF_BODY,INK,s->title[0]?s->title:"Spotify",117);label(p,196,494,UF_SMALL,SOFT,s->artist,117);
    ud_icon(p,ICON_SHUFFLE,356,489,27,s->shuffle?GREEN:SOFT);if(s->shuffle)ud_circle(p,356,516,2,GREEN);
    ud_icon(p,ICON_PREVIOUS,432,489,29,INK);
    ud_circle(p,516,489,31,GREEN);ud_icon(p,s->status==1?ICON_PAUSE:ICON_PLAY,516,489,29,BG);
    ud_icon(p,ICON_NEXT,600,489,29,INK);ud_icon(p,ICON_REPEAT,676,489,28,s->repeat?GREEN:SOFT);
    if(s->repeat)ud_circle(p,676,516,2,GREEN);
    if(s->repeat==2)label(p,672,479,UF_SMALL,GREEN,"1",16);
    ud_icon(p,ICON_SPEAKER,744,489,23,SOFT);box(p,(UiRect){UI_VOLUME_X,487,UI_VOLUME_W,4},LINE);
    if(!s->volume)ud_line(p,735,498,753,480,2.2f,SOFT);
    unsigned level=s->volume>100?100:s->volume;int w=(int)level*UI_VOLUME_W/100;
    if(w)box(p,(UiRect){UI_VOLUME_X,487,w,4},INK);
    ud_circle(p,UI_VOLUME_X+(float)w,489,4.5f,INK);
    snprintf(time,sizeof(time),"%u%%",level);right_text(p,916,508,UF_SMALL,SOFT,time,80);
}
static void browser(uint32_t *p,const ReceiverUiState *audio,const SpotifyView *s) {
    unsigned count=s->tab?s->favorite_count:s->queue_count;unsigned first=s->selected/UI_LIST_ROWS*UI_LIST_ROWS;
    const ControlItem *items=s->tab?s->favorites:s->queue;
    shell(p,audio,s->tab?2:1,s,s->tab?"Favorites":s->queue_query[0]?"Search results":"Up next",
        s->tab?"L/R skip tracks   ·   D-pad selects / switches tabs   ·   X plays   ·   Triangle cycles tabs":"",0);
    if(!s->tab) {
        ud_round(p,UI_QUEUE_SEARCH,10,SELECTED);ud_icon(p,ICON_SEARCH,220,84,22,s->queue_paged?GREEN:FAINT);
        label(p,246,73,UF_BODY,s->queue_query[0]?INK:SOFT,s->queue_query[0]?s->queue_query:"Search upcoming songs · Square",540);
        label(p,829,73,UF_BODY,SOFT,s->queue_query[0]?"Clear":"Refresh",98);
        char scope[128];
        if(!s->queue_paged)snprintf(scope,sizeof(scope),"Upgrade the PC host to enable queue search.");
        else if(s->queue_loading || (s->queue_flags&2))snprintf(scope,sizeof(scope),"Loading available upcoming songs…");
        else snprintf(scope,sizeof(scope),"%u %s / %u available upcoming · %s",s->queue_total,s->queue_total==1?"match":"matches",s->queue_available,
                      s->queue_flags&1?"PC safety limit reached":"Current queue only, not the whole playlist");
        label(p,198,389,UF_SMALL,SOFT,scope,728);
    }
    if(!count) {
        ud_icon(p,s->tab?ICON_HEART:ICON_QUEUE,554,189,45,FAINT);
        label(p,252,246,UF_TITLE,INK,s->tab?"Your favorites live here":s->queue_query[0]?"No matching upcoming songs":"Nothing up next",650);
        ud_wrap(p,254,295,UF_BODY,SOFT,s->tab?"Add a song, album or playlist using favorites.py on your PC.":s->queue_query[0]?
            "Try fewer words, a title or an artist. Songs outside Soloist's available queue cannot be searched.":
            "Start an album or playlist in Spotify. Upcoming songs will appear here.",640,2,26);
    }
    for(unsigned row=0;row<UI_LIST_ROWS && first+row<count;++row) {
        unsigned i=first+row;int y=UI_LIST_Y+(int)row*UI_LIST_ROW_H;
        if(i==s->selected)ud_round(p,(UiRect){UI_LIST_X,y+1,UI_LIST_W,54},9,SELECTED);
        char rank[16];snprintf(rank,sizeof(rank),"%02u",items[i].position?items[i].position:i+1);
        if(s->tab)ud_icon(p,strstr(items[i].uri,":playlist:")?ICON_QUEUE:ICON_MUSIC,216,y+28,21,i==s->selected?GREEN:FAINT);
        else label(p,208,y+17,UF_BODY,i==s->selected?GREEN:FAINT,rank,66);
        int tx=s->tab?254:282;
        label(p,tx,y+5,UF_LABEL,INK,items[i].title[0]?items[i].title:"Spotify item",878-tx);
        label(p,tx+1,y+32,UF_SMALL,SOFT,items[i].artist[0]?items[i].artist:s->tab?"Saved shortcut":"Spotify",877-tx);
        ud_icon(p,i==s->selected?ICON_PLAY:ICON_CHEVRON,904,y+28,i==s->selected?15:18,i==s->selected?GREEN:FAINT);
    }
    unsigned total=!s->tab && s->queue_paged?s->queue_total:count;
    unsigned offset=!s->tab && s->queue_paged?s->queue_offset:first;
    if(total>UI_LIST_ROWS) {
        int h=280*UI_LIST_ROWS/(int)total;if(h<24)h=24;
        int y=UI_LIST_Y+(280-h)*(int)offset/(int)(total-UI_LIST_ROWS);if(y>UI_LIST_Y+280-h)y=UI_LIST_Y+280-h;
        ud_round(p,(UiRect){938,y,3,h},1,FAINT);
    }
    transport(p,s);
}
static void search_keyboard_frame(uint32_t *p,const ReceiverUiState *audio,const SpotifyView *s) {
    shell(p,audio,1,s,"Search upcoming songs","R search   ·   L delete   ·   Square space   ·   Triangle clear   ·   O cancel",0);
    ud_round(p,(UiRect){196,112,732,60},10,SELECTED);
    const char *visible=s->keyboard.text;
    while(*visible && ud_width(UF_LABEL,visible)>654) {
        ++visible;while(((unsigned char)*visible&0xc0)==0x80)++visible;
    }
    label(p,216,130,UF_LABEL,INK,*visible?visible:"Type a title or artist…",680);
    char scope[112];snprintf(scope,sizeof(scope),"%u available upcoming songs · accents/case ignored · current queue only",s->queue_available);
    label(p,198,177,UF_SMALL,SOFT,scope,726);
    for(unsigned row=0;row<5;++row)for(unsigned col=0;col<search_keyboard_columns(row);++col) {
        UiRect r=search_keyboard_bounds(row,col);int selected=s->keyboard.row==row && s->keyboard.column==col;
        int submit=row==4 && col==3;
        if(selected || submit)ud_round(p,r,9,submit?GREEN:SELECTED);
        else box(p,(UiRect){r.x+9,r.y+r.h-1,r.w-18,1},LINE);
        char c[]={search_keyboard_character(row,col),0};const char *key=row<4?c:search_keyboard_label(row,col);
        int w=ud_width(UF_LABEL,key);
        label(p,r.x+(r.w-w)/2,r.y+(r.h-23)/2,UF_LABEL,submit?BG:selected?GREEN:INK,key,r.w-12);
    }
    label(p,198,506,UF_SMALL,SOFT,"D-pad selects a key; X enters it. Searching does not interrupt playback.",726);
}
static void queue_action_frame(uint32_t *p,const ReceiverUiState *audio,const SpotifyView *s) {
    int active=s->jump_total!=0;
    shell(p,audio,1,s,active?"Moving through queue":"Play this upcoming song?","The remaining playlist is preserved. Soloist advances one confirmed skip at a time.",0);
    char line[144];
    if(active) {
        snprintf(line,sizeof(line),"%u of %u skips confirmed",s->jump_done,s->jump_total);
        label(p,204,160,UF_TITLE,INK,line,714);
        box(p,(UiRect){204,238,704,5},LINE);
        unsigned w=s->jump_total?(unsigned)((uint64_t)s->jump_done*704/s->jump_total):0;
        box(p,(UiRect){204,238,(int)w,5},GREEN);
        label(p,204,280,UF_BODY,SOFT,"Cancel stops further skips. Already completed skips cannot be undone.",714);
    } else {
        ud_wrap(p,204,143,UF_TITLE,INK,s->confirm_title,704,2,36);
        snprintf(line,sizeof(line),"This selection needs %u skips and may take a while.",s->confirm_distance);
        label(p,204,245,UF_BODY,SOFT,line,714);
        label(p,204,284,UF_SMALL,SOFT,"You can cancel while advancing. Very distant jumps may time out.",714);
        ud_round(p,UI_CONFIRM_GO,28,GREEN);label(p,670,365,UF_LABEL,BG,"X · Continue",240);
    }
    ud_round(p,UI_CONFIRM_CANCEL,28,SELECTED);label(p,295,365,UF_LABEL,GREEN,active?"O / X · Cancel":"O · Back",240);
}
static void disconnect_frame(uint32_t *p,const ReceiverUiState *audio,const SpotifyView *s) {
    shell(p,audio,0,s,"Disconnect from your PC?","Audio will stop on this Vita. Your PC host will stay ready to reconnect.",0);
    label(p,204,185,UF_TITLE,INK,"Keep listening?",700);
    label(p,204,242,UF_BODY,SOFT,"Press Circle to return, or X to disconnect.",700);
    ud_round(p,UI_CONFIRM_CANCEL,28,SELECTED);label(p,295,365,UF_LABEL,GREEN,"O · Back",240);
    ud_round(p,UI_CONFIRM_GO,28,GREEN);label(p,650,365,UF_LABEL,BG,"X · Disconnect",270);
}
static void quality_frame(uint32_t *p,const ReceiverUiState *s) {
    shell(p,s,-1,NULL,"Settings / Audio","Separate preferences for Local and Remote. Changes apply during playback.",1);
    UiRect tabs[]={UI_QUALITY_LOCAL,UI_QUALITY_REMOTE};
    for(unsigned i=0;i<2;++i) {
        if(s->quality_tab==i)ud_round(p,tabs[i],10,SELECTED);
        label(p,tabs[i].x+24,tabs[i].y+20,UF_LABEL,s->quality_tab==i?GREEN:SOFT,i?"Remote":"Local Wi-Fi",272);
    }
    static const unsigned rates[]={0,320,256,192,160,128,96};
    for(unsigned i=0;i<7;++i) {
        UiRect r=ui_quality_choice(i);int selected=s->quality_modes[!!s->quality_tab]==rates[i];
        if(selected)ud_round(p,r,10,SELECTED);else box(p,(UiRect){r.x+12,r.y+r.h-1,r.w-24,1},LINE);
        char text[32];if(rates[i])snprintf(text,sizeof(text),"%u kbps",rates[i]);else snprintf(text,sizeof(text),"Auto");
        label(p,r.x+18,r.y+21,UF_LABEL,selected?GREEN:INK,text,125);
        if(selected)ud_icon(p,ICON_CHECK,r.x+r.w-20,r.y+32,18,GREEN);
    }
    ud_icon(p,ICON_BACK,218,380,21,SOFT);label(p,240,369,UF_BODY,SOFT,"Settings",133);
    label(p,198,430,UF_BODY,INK,"Auto adjusts between 96 and 320 kbps.",720);
    label(p,198,461,UF_SMALL,SOFT,"Choose Auto for changing connections, or keep a fixed rate.",720);
    label(p,198,506,UF_SMALL,SOFT,"L/R connection tab   ·   Left/Right quality   ·   O back",720);
}
static void settings_frame(uint32_t *p,const ReceiverUiState *s) {
    if(s->quality_open || s->settings_page==SETTINGS_AUDIO) { quality_frame(p,s);return; }
    shell(p,s,-1,NULL,"Settings","Up/Down select   ·   Left/Right or X changes   ·   O or SELECT closes",1);
    static const char *titles[]={"Audio quality","Screen timeout","Connection route","PC connection"};
    char detail[4][104],value[4][40],local[24],remote[24];
    if(s->quality_modes[0])snprintf(local,sizeof(local),"%u kbps",s->quality_modes[0]);else snprintf(local,sizeof(local),"Auto");
    if(s->quality_modes[1])snprintf(remote,sizeof(remote),"%u kbps",s->quality_modes[1]);else snprintf(remote,sizeof(remote),"Auto");
    snprintf(detail[0],sizeof(detail[0]),"Local %s  /  Remote %s",local,remote);snprintf(value[0],sizeof(value[0]),"Choose");
    snprintf(detail[1],sizeof(detail[1]),"Audio keeps playing while the screen is off.");timeout_text(value[1],sizeof(value[1]),s->screen_timeout);
    snprintf(detail[2],sizeof(detail[2]),"Changing the route reconnects this Vita.");snprintf(value[2],sizeof(value[2]),"%s",s->link.remote_mode?"Remote":"Local Wi-Fi");
    snprintf(detail[3],sizeof(detail[3]),"Connection setup pauses audio until you finish.");
    snprintf(value[3],sizeof(value[3]),"%s",s->link.remote_mode?"Details":"Address");
    for(unsigned i=0;i<4;++i) {
        int y=UI_SETTINGS_ROW_Y+(int)i*UI_SETTINGS_ROW_H;
        if(i==s->settings_selected)ud_round(p,(UiRect){196,y,732,64},10,SELECTED);
        label(p,216,y+9,UF_LABEL,INK,titles[i],400);label(p,216,y+37,UF_SMALL,SOFT,detail[i],470);
        right_text(p,876,y+23,UF_BODY,i==s->settings_selected?GREEN:SOFT,value[i],196);ud_icon(p,ICON_CHEVRON,906,y+33,20,FAINT);
    }
    label(p,200,410,UF_SMALL,SOFT,s->screen_timeout?"OLED protection: dims first, then turns off. First tap or button only wakes.":
        "Automatic screen off disabled. Dimming stays on; use Screen off for OLED protection.",724);
    char stats[128];snprintf(stats,sizeof(stats),"%u kbps  ·  %u ms buffered  ·  %u rebuffers",s->opus_bitrate/1000,s->buffer_ms,s->underruns);
    label(p,200,452,UF_SMALL,FAINT,stats,716);
    label(p,200,503,UF_SMALL,SOFT,"Settings save on this Vita.",520);
    ud_round(p,UI_SETTINGS_DONE,28,SELECTED);label(p,815,486,UF_LABEL,GREEN,"Done",95);
}
static void connection_frame(uint32_t *p,const ReceiverUiState *s,const char *ip) {
    const PcLinkView *link=&s->link;char value[144];
    shell(p,s,-1,NULL,link->editing?"PC connection":"Connect to your PC",
          link->editing?"O back   ·   START exits":"SELECT settings   ·   X retry   ·   Triangle Local/Remote   ·   Square speaker test",0);
    if(s->network_ready && !link->paired) {
        label(p,204,140,UF_SMALL,AMBER,"ONE-TIME PAIRING",710);label(p,204,184,UF_TITLE,INK,"Pair this Vita with Windows",710);
        label(p,204,242,UF_BODY,SOFT,"1. Run Pair Vita.cmd on your PC.",710);label(p,204,280,UF_BODY,SOFT,"2. Copy vita-pairing.bin with VitaShell USB to:",710);
        label(p,204,317,UF_LABEL,GREEN,"ux0:data/vita-audio-receiver/",710);label(p,204,361,UF_BODY,SOFT,"3. Close and reopen this app.",710);
    } else if(link->remote_mode && !link->remote_available) {
        label(p,204,140,UF_SMALL,AMBER,"REMOTE PROFILE NEEDED",710);label(p,204,184,UF_TITLE,INK,"Set up your PC tunnel",710);
        label(p,204,242,UF_BODY,SOFT,"Run Setup Funnel.cmd on your PC.",710);label(p,204,280,UF_BODY,SOFT,"Copy remote-host.txt with VitaShell USB to:",710);
        label(p,204,317,UF_LABEL,GREEN,"ux0:data/vita-audio-receiver/",710);label(p,204,361,UF_BODY,SOFT,"Reopen the app after copying the file.",710);
    } else if(link->editing && link->remote_mode) {
        label(p,204,132,UF_SMALL,GREEN,"AUDIO ENDPOINT",710);ud_wrap(p,204,166,UF_BODY,INK,link->remote.audio_host,710,2,23);
        snprintf(value,sizeof(value),"Port %u",link->remote.audio_port);label(p,204,221,UF_SMALL,SOFT,value,710);
        label(p,204,271,UF_SMALL,GREEN,"CONTROL ENDPOINT",710);ud_wrap(p,204,305,UF_BODY,INK,link->remote.control_host,710,2,23);
        snprintf(value,sizeof(value),"Port %u",link->remote.control_port);label(p,204,360,UF_SMALL,SOFT,value,710);
        label(p,204,437,UF_BODY,SOFT,"X connect   ·   O back   ·   Triangle use Local",710);
    } else if(link->editing) {
        label(p,204,130,UF_BODY,SOFT,"Enter the PC IPv4 address shown by Host Status.",710);
        for(unsigned i=0;i<4;++i) {
            int x=196+(int)i*184;UiRect r={x,194,164,84};
            if(i==link->selected)ud_round(p,r,10,SELECTED);else outline(p,r,LINE);
            snprintf(value,sizeof(value),"%03u",link->octets[i]);label(p,x+43,215,UF_HERO,i==link->selected?GREEN:INK,value,100);
            if(i<3)label(p,x+171,226,UF_LABEL,FAINT,".",12);
        }
        label(p,204,318,UF_BODY,SOFT,"Left/Right field   ·   Up/Down 1   ·   L/R 10",710);label(p,204,375,UF_BODY,INK,"X save and connect   ·   O cancel",710);
        label(p,204,425,UF_BODY,GREEN,"Triangle returns to automatic discovery",710);
    } else {
        const char *heading=!s->network_ready?"Starting Wi-Fi…":!link->desired?"Ready when you are":link->remote_mode?"Connecting through your tunnel":
            link->ip[0]?"Connecting to Windows":"Looking for your Windows host";
        label(p,204,137,UF_SMALL,GREEN,link->remote_mode?"REMOTE · PAIRED TLS 1.3":"LOCAL · PAIRED TLS 1.3",710);
        ud_wrap(p,204,180,UF_TITLE,INK,heading,710,2,36);
        ud_wrap(p,204,265,UF_BODY,SOFT,link->message[0]?link->message:"Start Vita Audio Host on Windows. Connection is automatic.",710,2,27);
        box(p,(UiRect){204,345,704,1},LINE);label(p,204,372,UF_SMALL,FAINT,link->remote_mode?"SAVED AUDIO TUNNEL":"PC HOST",710);
        label(p,204,403,UF_LABEL,INK,link->remote_mode?link->remote.audio_host:link->ip[0]?link->ip:"Automatic discovery",710);
        snprintf(value,sizeof(value),"Vita %s  ·  Keep the PC awake and signed in.",ip);label(p,204,461,UF_SMALL,SOFT,value,710);
    }
    label(p,204,506,UF_SMALL,FAINT,"Screen off keeps audio running. Settings are available from the gear.",710);
}
static void capture_frame(uint32_t *p,const ReceiverUiState *s) {
    shell(p,s,-1,NULL,s->capture_error==8?"Soloist update needed":"Audio setup needed","The receiver will retry automatically when the PC is ready.",0);
    label(p,204,139,UF_SMALL,AMBER,s->capture_error==8?"SOLOIST BUILD EXPIRED":"CHECK THE PC HOST",710);
    ud_wrap(p,204,186,UF_TITLE,INK,vaer_message(s->capture_error),704,2,36);
    label(p,204,295,UF_BODY,SOFT,s->capture_error==8?"Install a new official Soloist build.":"Run Setup Audio.cmd on the PC.",710);
    label(p,204,337,UF_BODY,SOFT,s->capture_error==8?"Then run Upgrade Host.cmd.":"Keep Soloist routed to your saved virtual cable.",710);
    label(p,204,405,UF_BODY,GREEN,"Audio resumes after the PC setup is corrected.",710);
    label(p,204,504,UF_SMALL,FAINT,"SELECT settings   ·   Square speaker test   ·   START exit",710);
}
void ui_render_frame(uint32_t *p,const ReceiverUiState *s,const char *ip) {
    if(s->settings_open || s->quality_open) { settings_frame(p,s);return; }
    if(s->capture_error && !s->link.editing && !s->testing) { capture_frame(p,s);return; }
    if(s->link.editing || (!s->connected && !s->error && !s->testing)) { connection_frame(p,s,ip);return; }
    shell(p,s,-1,NULL,s->testing?"Speaker test":s->error?"Connection needs attention":"Receiving audio",
        "SELECT settings   ·   X mute   ·   O disconnect   ·   Square speaker test   ·   START exit",0);
    label(p,204,146,UF_SMALL,s->error?RED:GREEN,s->muted?"MUTED":s->testing?"LOCAL TONE":s->playing?"STREAMING":"BUFFERING",710);
    ud_wrap(p,204,196,UF_TITLE,INK,s->status,710,3,38);
    char value[128];snprintf(value,sizeof(value),"Vita %s  ·  %u ms buffered  ·  %u rebuffers",ip,s->buffer_ms,s->underruns);
    label(p,204,384,UF_BODY,SOFT,value,710);label(p,204,464,UF_SMALL,FAINT,"Keep this app running. Screen off continues playback.",710);
}
void ui_render_player(uint32_t *p,const ReceiverUiState *audio,const char *ip,const SpotifyView *s) {
    if(audio->settings_open || audio->quality_open) { settings_frame(p,audio);return; }
    if(audio->link.editing) { connection_frame(p,audio,ip);return; }
    if(audio->capture_error && !audio->testing) { capture_frame(p,audio);return; }
    if(!s->online) { ui_render_frame(p,audio,ip);return; }
    if(s->disconnect_confirm) { disconnect_frame(p,audio,s);return; }
    if(s->keyboard.open) { search_keyboard_frame(p,audio,s);return; }
    if(s->jump_total || s->queue_confirm) { queue_action_frame(p,audio,s);return; }
    if(s->browser) { browser(p,audio,s);return; }
    shell(p,audio,0,s,"Now playing","X play/pause   ·   L/R skip   ·   Triangle tabs   ·   SELECT settings",0);artwork(p,s);
    const char *state=!s->api_online?"RECONNECTING TO SOLOIST":!s->logged_in?"PAIR FROM SPOTIFY":!s->active?"DEVICE INACTIVE":
        s->status==1?"PLAYING FROM SPOTIFY":s->status==2?"PAUSED":s->status==3?"BUFFERING":"SPOTIFY CONNECT";
    label(p,456,110,UF_SMALL,s->status==1?GREEN:SOFT,state,458);
    ud_wrap(p,454,149,UF_HERO,INK,s->title[0]?s->title:!s->logged_in?"Select this device in Spotify":"Choose something to play",458,2,39);
    label(p,456,246,UF_LABEL,SOFT,s->artist,458);label(p,456,283,UF_BODY,FAINT,s->album,458);
    if(s->message[0])label(p,456,329,UF_SMALL,SOFT,s->message,458);
    transport(p,s);
}
