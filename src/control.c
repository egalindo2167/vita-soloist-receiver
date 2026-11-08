#include "control.h"
#include "pc_link.h"
#include "secure_net.h"
#include "ui_layout.h"
#ifdef CONTROL_INPUT_TEST
#include "pc_link_test_platform.h"
#else
#include <psp2/ctrl.h>
#include <psp2/kernel/threadmgr.h>
#include <psp2/kernel/processmgr.h>
#include <psp2/net/net.h>
#endif
#include <string.h>
#include <stdio.h>

static SpotifyView shared;
static SceUID state_mutex=-1, input_mutex=-1, worker=-1;
static int running, ready, online, disconnect_requested;
static uint8_t rx[CTL_MAX_PAYLOAD], header[8];
typedef struct { unsigned kind; int a,b,fresh; } Input;
static Input inputs[32];
static unsigned input_head, input_count;
static unsigned audio_buffer_ms,audio_underruns,audio_seconds,audio_playing,audio_kbps,audio_remote;
static unsigned previous_volume=65;
void control_audio_stats(unsigned buffer_ms,unsigned underruns,unsigned seconds,int playing,unsigned kbps,int remote) {
    __atomic_store_n(&audio_buffer_ms,buffer_ms,__ATOMIC_RELAXED);
    __atomic_store_n(&audio_underruns,underruns,__ATOMIC_RELAXED);
    __atomic_store_n(&audio_seconds,seconds,__ATOMIC_RELAXED);
    __atomic_store_n(&audio_playing,!!playing,__ATOMIC_RELAXED);
    __atomic_store_n(&audio_kbps,kbps,__ATOMIC_RELAXED);
    __atomic_store_n(&audio_remote,!!remote,__ATOMIC_RELAXED);
}

static void push_input(Input in) {
    /* This small mutex never protects metadata, artwork, rendering or I/O. */
    sceKernelLockMutex(input_mutex,1,NULL);
    if (input_count==32) { input_head=(input_head+1)%32; --input_count; }
    inputs[(input_head+input_count)%32]=in; ++input_count;
    sceKernelUnlockMutex(input_mutex,1);
}
unsigned control_buttons(unsigned pressed) {
    if (!__atomic_load_n(&online,__ATOMIC_ACQUIRE)) return 0;
    unsigned mask=SCE_CTRL_CROSS|SCE_CTRL_CIRCLE|SCE_CTRL_TRIANGLE|SCE_CTRL_SQUARE|
        SCE_CTRL_SELECT|SCE_CTRL_LTRIGGER|SCE_CTRL_RTRIGGER|SCE_CTRL_LEFT|SCE_CTRL_RIGHT|
        SCE_CTRL_UP|SCE_CTRL_DOWN;
    unsigned used=pressed&mask;
    if (used) push_input((Input){1,(int)used,0,0});
    return used;
}
void control_touch(int x, int y, int fresh) {
    if (__atomic_load_n(&online,__ATOMIC_ACQUIRE)) push_input((Input){2,x,y,fresh});
}
void control_navigate(unsigned page) {
    if(page<=2 && __atomic_load_n(&online,__ATOMIC_ACQUIRE))push_input((Input){3,(int)page,0,0});
}
int control_take_disconnect(void) {
    return __atomic_exchange_n(&disconnect_requested,0,__ATOMIC_ACQ_REL);
}
int control_online(void) { return __atomic_load_n(&online,__ATOMIC_ACQUIRE); }
int control_audio_flush(uint32_t *id,unsigned *hold) {
    if(!__atomic_load_n(&ready,__ATOMIC_ACQUIRE) || sceKernelTryLockMutex(state_mutex,1)<0)return 0;
    *id=shared.audio_flush_id;*hold=shared.audio_flush_hold;
    sceKernelUnlockMutex(state_mutex,1);return *id!=0;
}
int control_snapshot(SpotifyView *v) {
    if (!__atomic_load_n(&ready,__ATOMIC_ACQUIRE)) return 0;
    if (sceKernelTryLockMutex(state_mutex,1)<0) return 0;
    int changed=v->generation!=shared.generation;
    if (changed) *v=shared;
    sceKernelUnlockMutex(state_mutex,1); return changed;
}
static int get_input(Input *in) {
    sceKernelLockMutex(input_mutex,1,NULL);
    int found=input_count!=0;
    if (found) { *in=inputs[input_head]; input_head=(input_head+1)%32; --input_count; }
    sceKernelUnlockMutex(input_mutex,1); return found;
}
static unsigned selected_uri(char *uri) {
    unsigned count=shared.tab ? shared.favorite_count : shared.queue_count;
    ControlItem *items=shared.tab ? shared.favorites : shared.queue;
    if (shared.selected>=count) return 0;
    if(!shared.tab && shared.queue_loading)return 0;
    if(!shared.tab && items[shared.selected].position>8) {
        shared.queue_confirm=1;shared.confirm_distance=items[shared.selected].position;
        memcpy(shared.confirm_title,items[shared.selected].title,128);
        memcpy(shared.confirm_token,items[shared.selected].uri,128);return 0;
    }
    memcpy(uri,items[shared.selected].uri,128); return shared.tab?CTL_PLAY_URI:CTL_PLAY_QUEUE;
}
static unsigned search_request(const char *query,int *value,char *text) {
    shared.queue_request_id=shared.queue_request_id%0x7fffffffu+1;
    memmove(shared.queue_query,query,128);memcpy(text,query,128);
    shared.queue_loading=1;shared.queue_wanted_offset=0;shared.queue_select_last=0;
    shared.selected=0;*value=(int)shared.queue_request_id;return CTL_QUEUE_SEARCH;
}
static unsigned page_request(unsigned offset,int last,int *value,char *text) {
    if(shared.queue_loading || offset>=shared.queue_total)return 0;
    shared.queue_loading=1;shared.queue_wanted_offset=offset;shared.queue_select_last=!!last;
    *value=(int)offset;snprintf(text,128,"%u",shared.queue_request_id);return CTL_QUEUE_PAGE;
}
static void open_search(void) {
    if(shared.queue_paged)search_keyboard_open(&shared.keyboard,shared.queue_query);
}
static int make_command(Input in, uint8_t *out) {
    unsigned op=0; int value=0; char uri[128]={0};
    sceKernelLockMutex(state_mutex,1,NULL);
    if(shared.volume && shared.volume<=100)previous_volume=shared.volume;
    if(in.kind==3)shared.keyboard.open=shared.queue_confirm=shared.disconnect_confirm=0;
    if(shared.keyboard.open) {
        unsigned keys=0;
        if(in.kind==1) {
            unsigned b=(unsigned)in.a;
            if(b&SCE_CTRL_UP)keys|=KEY_UP;
            if(b&SCE_CTRL_DOWN)keys|=KEY_DOWN;
            if(b&SCE_CTRL_LEFT)keys|=KEY_LEFT;
            if(b&SCE_CTRL_RIGHT)keys|=KEY_RIGHT;
            if(b&SCE_CTRL_CROSS)keys|=KEY_ENTER;
            if(b&SCE_CTRL_CIRCLE)keys|=KEY_CANCEL;
            if(b&SCE_CTRL_LTRIGGER)keys|=KEY_DELETE;
            if(b&SCE_CTRL_RTRIGGER)keys|=KEY_SEARCH;
            if(b&SCE_CTRL_SQUARE)keys|=KEY_SPACE;
            if(b&SCE_CTRL_TRIANGLE)keys|=KEY_CLEAR;
        }
        unsigned action=search_keyboard_input(&shared.keyboard,keys,in.kind==2 && in.fresh,in.a,in.b);
        if(action==KEYBOARD_SUBMIT)op=search_request(shared.keyboard.text,&value,uri);
    } else if(shared.disconnect_confirm) {
        if((in.kind==1 && ((unsigned)in.a&SCE_CTRL_CROSS)) ||
           (in.kind==2 && in.fresh && ui_hit(UI_CONFIRM_GO,in.a,in.b))) {
            shared.disconnect_confirm=0;__atomic_store_n(&disconnect_requested,1,__ATOMIC_RELEASE);
        } else if((in.kind==1 && ((unsigned)in.a&(SCE_CTRL_CIRCLE|SCE_CTRL_TRIANGLE))) ||
           (in.kind==2 && in.fresh && ui_hit(UI_CONFIRM_CANCEL,in.a,in.b)))shared.disconnect_confirm=0;
    } else if(shared.jump_total) {
        if((in.kind==1 && ((unsigned)in.a&(SCE_CTRL_CIRCLE|SCE_CTRL_CROSS))) ||
           (in.kind==2 && in.fresh && ui_hit(UI_CONFIRM_CANCEL,in.a,in.b)))op=CTL_QUEUE_CANCEL;
    } else if(shared.queue_confirm) {
        if((in.kind==1 && ((unsigned)in.a&SCE_CTRL_CROSS)) ||
           (in.kind==2 && in.fresh && ui_hit(UI_CONFIRM_GO,in.a,in.b))) {
            op=CTL_PLAY_QUEUE;memcpy(uri,shared.confirm_token,128);shared.queue_confirm=0;
        } else if((in.kind==1 && ((unsigned)in.a&(SCE_CTRL_CIRCLE|SCE_CTRL_TRIANGLE))) ||
           (in.kind==2 && in.fresh && ui_hit(UI_CONFIRM_CANCEL,in.a,in.b)))shared.queue_confirm=0;
    } else if (in.kind==1) {
        unsigned b=(unsigned)in.a;
        /* Transport keys keep their meaning on every music page. */
        if(b&SCE_CTRL_LTRIGGER)op=CTL_PREV;
        else if(b&SCE_CTRL_RTRIGGER)op=CTL_NEXT;
        else if(b&SCE_CTRL_SQUARE) {
            if(shared.browser && !shared.tab && shared.queue_paged)open_search();else op=CTL_SHUFFLE;
        }
        else if(b&SCE_CTRL_TRIANGLE) {
            if(!shared.browser) { shared.browser=1;shared.tab=0; }
            else if(!shared.tab)shared.tab=1;
            else shared.browser=0;
            shared.selected=0;if(shared.browser)op=CTL_REFRESH;
        } else if (shared.browser) {
            if (b&SCE_CTRL_CIRCLE) shared.browser=0;
            if (b&(SCE_CTRL_LEFT|SCE_CTRL_RIGHT)) {
                shared.tab^=1; shared.selected=0;
            }
            unsigned count=shared.tab ? shared.favorite_count : shared.queue_count;
            if(count && (shared.tab || !shared.queue_loading)) {
                if(!shared.tab && shared.queue_paged) {
                    if(b&SCE_CTRL_UP) {
                        if(shared.selected)--shared.selected;
                        else if(shared.queue_offset>=5)op=page_request(shared.queue_offset-5,1,&value,uri);
                    }
                    if(b&SCE_CTRL_DOWN) {
                        if(shared.selected+1<count)++shared.selected;
                        else if(shared.queue_offset+count<shared.queue_total)op=page_request(shared.queue_offset+5,0,&value,uri);
                    }
                } else {
                    if(b&SCE_CTRL_UP)shared.selected=shared.selected?shared.selected-1:count-1;
                    if(b&SCE_CTRL_DOWN)shared.selected=(shared.selected+1)%count;
                }
            }
            if (b&SCE_CTRL_CROSS) op=selected_uri(uri);
        } else {
            if (b&SCE_CTRL_CROSS) op=CTL_TOGGLE;
            else if (b&SCE_CTRL_LEFT) { op=CTL_VOLUME_DELTA; value=-5; }
            else if (b&SCE_CTRL_RIGHT) { op=CTL_VOLUME_DELTA; value=5; }
            else if (b&SCE_CTRL_UP) { op=CTL_SEEK_DELTA; value=10000; }
            else if (b&SCE_CTRL_DOWN) { op=CTL_SEEK_DELTA; value=-10000; }
            else if (b&SCE_CTRL_CIRCLE) shared.disconnect_confirm=1;
        }
    } else if (in.kind==2) {
        int x=in.a,y=in.b;
        int nav=in.fresh?ui_nav_at(x,y):-1;
        if(nav>=0) {
            shared.browser=nav>0;shared.tab=nav==2;shared.selected=0;
            if(shared.browser)op=CTL_REFRESH;
        } else if(shared.browser && !shared.tab && in.fresh && ui_hit(UI_QUEUE_SEARCH,x,y))open_search();
        else if(shared.browser && !shared.tab && in.fresh && ui_hit(UI_QUEUE_CLEAR,x,y)) {
            if(shared.queue_query[0]) { char empty[128]={0};op=search_request(empty,&value,uri); }
            else op=CTL_REFRESH;
        } else if(shared.browser && !shared.tab && x>=196 && x<928 && y>=388 && y<408) { /* Queue scope caption, not seek. */ }
        else if(in.fresh && ui_hit(UI_VOLUME_MUTE,x,y)) {
            op=CTL_VOLUME;value=shared.volume?0:(int)previous_volume;
        } else if(ui_hit(UI_VOLUME,x,y)) {
            op=CTL_VOLUME;value=(x-UI_VOLUME_X)*100/UI_VOLUME_W;
            if(value<0)value=0;
            if(value>100)value=100;
        } else if(in.fresh && ui_hit(UI_SEEK,x,y) && shared.duration_ms) {
            int position=x-UI_PROGRESS_X;if(position<0)position=0;if(position>UI_PROGRESS_W)position=UI_PROGRESS_W;
            op=CTL_SEEK;value=(int)((uint64_t)position*shared.duration_ms/UI_PROGRESS_W);
        } else if(in.fresh && ui_hit(UI_PREVIOUS,x,y))op=CTL_PREV;
        else if(in.fresh && ui_hit(UI_PLAY,x,y))op=CTL_TOGGLE;
        else if(in.fresh && ui_hit(UI_NEXT,x,y))op=CTL_NEXT;
        else if(in.fresh && ui_hit(UI_SHUFFLE,x,y))op=CTL_SHUFFLE;
        else if(in.fresh && ui_hit(UI_REPEAT,x,y))op=CTL_REPEAT;
        else if (shared.browser && in.fresh) {
            if(ui_hit((UiRect){UI_LIST_X,UI_LIST_Y,UI_LIST_W,UI_LIST_ROWS*UI_LIST_ROW_H},x,y)) {
                unsigned first=(shared.selected/UI_LIST_ROWS)*UI_LIST_ROWS;
                unsigned index=first+(unsigned)(y-UI_LIST_Y)/UI_LIST_ROW_H;
                unsigned count=shared.tab ? shared.favorite_count : shared.queue_count;
                if (index<count) { shared.selected=index; op=selected_uri(uri); }
            } else {
                unsigned count=shared.tab?shared.favorite_count:shared.queue_count;
                unsigned first=(shared.selected/UI_LIST_ROWS)*UI_LIST_ROWS;
                if(!shared.tab && shared.queue_paged) {
                    if(ui_hit(UI_PAGE_UP,x,y) && shared.queue_offset>=5)op=page_request(shared.queue_offset-5,0,&value,uri);
                    else if(ui_hit(UI_PAGE_DOWN,x,y) && shared.queue_offset+count<shared.queue_total)op=page_request(shared.queue_offset+5,0,&value,uri);
                } else {
                    if(ui_hit(UI_PAGE_UP,x,y) && first>=UI_LIST_ROWS)shared.selected=first-UI_LIST_ROWS;
                    else if(ui_hit(UI_PAGE_DOWN,x,y) && first+UI_LIST_ROWS<count)shared.selected=first+UI_LIST_ROWS;
                }
            }
        }
    } else if(in.kind==3 && (unsigned)in.a<=2) {
        shared.browser=in.a>0;shared.tab=in.a==2;shared.selected=0;
        if(shared.browser)op=CTL_REFRESH;
    }
    if (op==CTL_PLAY_URI || op==CTL_PLAY_QUEUE) shared.browser=0;
    ++shared.generation;
    sceKernelUnlockMutex(state_mutex,1);
    if (!op) return 0;
    memcpy(out,"CMND",4); ctl_write32(out+4,CTL_COMMAND_BYTES);
    ctl_write32(out+8,op); ctl_write32(out+12,(uint32_t)value); memcpy(out+16,uri,128);
    return CTL_COMMAND_BYTES+8;
}
static void lost(void) {
    __atomic_store_n(&online,0,__ATOMIC_RELEASE);
    sceKernelLockMutex(state_mutex,1,NULL);
    shared.online=0; shared.browser=0; ++shared.generation;
    shared.keyboard.open=shared.queue_confirm=shared.jump_total=shared.disconnect_confirm=0;
    shared.queue_paged=shared.queue_request_id=shared.queue_revision=shared.queue_loading=0;
    shared.queue_offset=shared.queue_total=shared.queue_available=shared.queue_count=0;shared.queue_query[0]=0;
    sceKernelUnlockMutex(state_mutex,1);
    sceKernelLockMutex(input_mutex,1,NULL); input_head=input_count=0;
    sceKernelUnlockMutex(input_mutex,1);
}
static int run_control(SceSize n, void *p) {
    (void)n; (void)p;
    int client=-1,close_it=0;size_t hh=0,have=0,need=0,sent=0,send_size=0;
    uint64_t last_diagnostic=0;
    uint64_t last_received=0;
    uint8_t out[CTL_COMMAND_BYTES+8];
    while (__atomic_load_n(&running,__ATOMIC_ACQUIRE)) {
        if (client<0) {
            client=pc_link_take_control();
            if (client>=0) {
                hh=have=need=sent=send_size=0; close_it=0;last_diagnostic=0;
                last_received=sceKernelGetProcessTimeWide();
            }
        }
        if (client>=0) {
            if (!pc_link_wanted())close_it=1;
            uint8_t *dest=hh<8 ? header+hh : rx+have;
            size_t room=hh<8 ? 8-hh : need-have;
            if (room>16384) room=16384;
            int got=secure_net_read(client,dest,room);
            if (got>0) {
                last_received=sceKernelGetProcessTimeWide();
                if (hh<8) {
                    hh+=(size_t)got;
                    if (hh==8) {
                        need=ctl_read32(header+4);
                        if (!ctl_frame_valid(header,(uint32_t)need)) close_it=1;
                    }
                } else {
                    have+=(size_t)got;
                    if (have==need) {
                        sceKernelLockMutex(state_mutex,1,NULL);
                        int valid=ctl_apply(&shared,header,rx,need);
                        unsigned connected=shared.online;
                        sceKernelUnlockMutex(state_mutex,1);
                        if (!valid) close_it=1;
                        else __atomic_store_n(&online,(int)connected,__ATOMIC_RELEASE);
                        hh=have=need=0;
                    }
                }
            } else if (got!=SECURE_NET_RETRY) close_it=1;
            if (send_size==sent) {
                Input in;
                while (get_input(&in)) {
                    send_size=(size_t)make_command(in,out); sent=0;
                    if (send_size) break;
                }
                uint64_t now=sceKernelGetProcessTimeWide();
                if (send_size==sent && (!last_diagnostic || now-last_diagnostic>=5000000ULL)) {
                    memcpy(out,"RSTA",4);ctl_write32(out+4,28);
                    ctl_write32(out+8,__atomic_load_n(&audio_underruns,__ATOMIC_RELAXED));
                    ctl_write32(out+12,__atomic_load_n(&audio_buffer_ms,__ATOMIC_RELAXED));
                    ctl_write32(out+16,__atomic_load_n(&audio_seconds,__ATOMIC_RELAXED));
                    ctl_write32(out+20,__atomic_load_n(&audio_playing,__ATOMIC_RELAXED));
                    ctl_write32(out+24,__atomic_load_n(&audio_kbps,__ATOMIC_RELAXED));
                    ctl_write32(out+28,__atomic_load_n(&audio_remote,__ATOMIC_RELAXED));
                    ctl_write32(out+32,7); /* reset, stable tokens, paged queue search */
                    sent=0;send_size=36;last_diagnostic=now;
                }
            }
            if (sent<send_size) {
                int put=secure_net_write(client,out+sent,send_size-sent);
                if (put>0) sent+=(size_t)put;
                else if (put!=SECURE_NET_RETRY) close_it=1;
            }
            if (sceKernelGetProcessTimeWide()-last_received>8000000ULL)close_it=1;
            if (close_it) {
                secure_net_close(client);client=-1;
                pc_link_control_closed();
                lost();
            }
        } else {
            Input discard; while (get_input(&discard)) { }
        }
        sceKernelDelayThread(5000);
    }
    if (client>=0) { secure_net_close(client);pc_link_control_closed(); }
    lost(); return 0;
}
int control_start(void) {
    memset(&shared,0,sizeof(shared)); shared.generation=1;
    input_head=input_count=0;
    int rc=-1;
    state_mutex=sceKernelCreateMutex("spotify-state",0,0,NULL);
    if (state_mutex<0) return state_mutex;
    input_mutex=sceKernelCreateMutex("spotify-input",0,0,NULL);
    if (input_mutex<0) { rc=input_mutex; goto fail; }
    worker=sceKernelCreateThread("spotify-controls",run_control,112,0x10000,0,0,NULL);
    if (worker<0) { rc=worker; goto fail; }
    __atomic_store_n(&running,1,__ATOMIC_RELEASE);
    rc=sceKernelStartThread(worker,0,NULL);
    if (rc<0) { __atomic_store_n(&running,0,__ATOMIC_RELEASE); goto fail; }
    __atomic_store_n(&ready,1,__ATOMIC_RELEASE); return 0;
fail:
    if (worker>=0) { sceKernelDeleteThread(worker); worker=-1; }
    if (input_mutex>=0) { sceKernelDeleteMutex(input_mutex); input_mutex=-1; }
    sceKernelDeleteMutex(state_mutex); state_mutex=-1; return rc;
}
void control_stop(void) {
    if (!__atomic_load_n(&ready,__ATOMIC_ACQUIRE)) return;
    __atomic_store_n(&running,0,__ATOMIC_RELEASE);
    sceKernelWaitThreadEnd(worker,NULL,NULL); sceKernelDeleteThread(worker); worker=-1;
    __atomic_store_n(&ready,0,__ATOMIC_RELEASE);
    sceKernelDeleteMutex(input_mutex); sceKernelDeleteMutex(state_mutex);
    input_mutex=state_mutex=-1;
}
