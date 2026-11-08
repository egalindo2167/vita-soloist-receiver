#include "pc_link.h"
#include "secure_net.h"
#include "audio_quality.h"
#include "display_settings.h"
#ifdef PC_LINK_STATE_TEST
#include "pc_link_test_platform.h"
#else
#include <psp2/ctrl.h>
#include <psp2/kernel/threadmgr.h>
#include <psp2/kernel/processmgr.h>
#include <psp2/net/net.h>
#endif
#include <stdio.h>
#include <string.h>

#define PC_AUDIO 48152
#define PC_CONTROL 48153
#define PC_DISCOVERY 48154
#define REMOTE_CONFIG "ux0:data/vita-audio-receiver/remote-host.txt"
#define MODE_CONFIG "ux0:data/vita-audio-receiver/connection-mode.txt"
#define CONFIG "ux0:data/vita-audio-receiver/host.txt"
static PcLinkView shared;
static SceUID mutex=-1,worker=-1;
static int alive,ready,wanted,editing;
static int audio_fd=-1,control_fd=-1,audio_busy,control_busy,save_pending,save_mode,switch_pending;
static unsigned audio_port=PC_AUDIO,control_port=PC_CONTROL,serial;
static AudioQuality saved_quality;
static int save_quality_pending;
static unsigned saved_display;
static int save_display_pending;
static int audio_hold;

/* Call only while holding the state mutex. A route change first drains old
 * sockets, so retry input cannot accidentally revive the previous route. */
static void update_wanted(void) {
    __atomic_store_n(&wanted,shared.desired && !shared.editing && !switch_pending,__ATOMIC_RELEASE);
}
static void finish_switch(void) {
    if(switch_pending && !audio_busy && !control_busy) { switch_pending=0;update_wanted(); }
}
static int nonblock(int fd) {
    int on=1;return sceNetSetsockopt(fd,SCE_NET_SOL_SOCKET,SCE_NET_SO_NBIO,&on,sizeof(on));
}
static int again(void) { int e=*sceNetErrnoLoc();return e==SCE_NET_EAGAIN || e==SCE_NET_EINTR; }
static int parse_ip(const char *text,unsigned value[4]) {
    char extra;
    return sscanf(text,"%u.%u.%u.%u%c",&value[0],&value[1],&value[2],&value[3],&extra)==4 &&
        value[0]<=255 && value[1]<=255 && value[2]<=255 && value[3]<=255 &&
        strcmp(text,"0.0.0.0") && strcmp(text,"255.255.255.255");
}
static void save_address(const char *ip) {
    if (ip[0]) {
        FILE *f=fopen(CONFIG,"w");
        if (f) { fprintf(f,"%s\n",ip);fclose(f); }
    } else remove(CONFIG);
}
static void load_remote(void) {
    shared.remote_available=0;
    FILE *f=fopen(REMOTE_CONFIG,"rb");
    if(f) {
        char buffer[REMOTE_PROFILE_MAX+1];size_t n=fread(buffer,1,sizeof(buffer),f);
        if(!ferror(f))shared.remote_available=(unsigned)remote_profile_parse(buffer,n,&shared.remote);
        fclose(f);
    }
}
static void save_connection_mode(int remote) {
    FILE *f=fopen(MODE_CONFIG,"w");if(f) { fputs(remote?"remote\n":"local\n",f);fclose(f); }
}
static int keep_connecting(void) { return __atomic_load_n(&alive,__ATOMIC_ACQUIRE) && __atomic_load_n(&wanted,__ATOMIC_ACQUIRE); }
static int resolve_host(const char *host,char ip[32]) {
    SceNetInAddr address;
    if(sceNetInetPton(SCE_NET_AF_INET,host,&address)!=1) {
        int resolver=sceNetResolverCreate("remote-dns",NULL,0);if(resolver<0)return -1;
        /* Worker only: DNS never blocks the rendering or audio threads. */
        int rc=sceNetResolverStartNtoa(resolver,host,&address,1000000,1,0);
        sceNetResolverDestroy(resolver);if(rc<0)return -1;
    }
    return sceNetInetNtop(SCE_NET_AF_INET,&address,ip,32)?0:-1;
}
static int connect_pc(const char *ip,unsigned port,int audio,const char *hostname) {
    if(!keep_connecting())return -1;
    int fd=sceNetSocket(audio?"pc-audio":"pc-controls",SCE_NET_AF_INET,SCE_NET_SOCK_STREAM,0);
    if (fd<0) return -1;
    if (nonblock(fd)<0) { sceNetSocketClose(fd);return -1; }
    SceNetSockaddrIn address={0};address.sin_len=sizeof(address);address.sin_family=SCE_NET_AF_INET;
    address.sin_port=sceNetHtons((unsigned short)port);
    if (sceNetInetPton(SCE_NET_AF_INET,ip,&address.sin_addr)!=1) { sceNetSocketClose(fd);return -1; }
    int result=sceNetConnect(fd,(SceNetSockaddr *)&address,sizeof(address));
    if (result<0) {
        int e=*sceNetErrnoLoc();
        if (e!=SCE_NET_EINPROGRESS && e!=SCE_NET_EALREADY && e!=SCE_NET_EAGAIN) {
            sceNetSocketClose(fd);return -1;
        }
        int poll=sceNetEpollCreate("pc-connect",0);
        if (poll<0) { sceNetSocketClose(fd);return -1; }
        SceNetEpollEvent event={0};event.events=SCE_NET_EPOLLOUT|SCE_NET_EPOLLERR|SCE_NET_EPOLLHUP;event.data.fd=fd;
        int connected=0;
        if (sceNetEpollControl(poll,SCE_NET_EPOLL_CTL_ADD,fd,&event)>=0) {
            uint64_t deadline=sceKernelGetProcessTimeWide()+5000000ULL;
            while (__atomic_load_n(&alive,__ATOMIC_ACQUIRE) && __atomic_load_n(&wanted,__ATOMIC_ACQUIRE) &&
                   sceKernelGetProcessTimeWide()<deadline) {
                if (sceNetEpollWait(poll,&event,1,0)>0) {
                    int error=-1;unsigned size=sizeof(error);
                    if (sceNetGetsockopt(fd,SCE_NET_SOL_SOCKET,SCE_NET_SO_ERROR,&error,&size)>=0 && !error) connected=1;
                    break;
                }
                sceKernelDelayThread(10000);
            }
        }
        sceNetEpollDestroy(poll);
        if (!connected) { sceNetSocketClose(fd);return -1; }
    }
    if (secure_net_handshake_host(fd,audio?0:1,hostname,keep_connecting)<0) { sceNetSocketClose(fd);return -1; }
    return fd;
}
static int open_discovery(void) {
    int fd=sceNetSocket("pc-discovery",SCE_NET_AF_INET,SCE_NET_SOCK_DGRAM,0);
    if (fd<0)return -1;
    int on=1;sceNetSetsockopt(fd,SCE_NET_SOL_SOCKET,SCE_NET_SO_BROADCAST,&on,sizeof(on));
    SceNetSockaddrIn address={0};address.sin_len=sizeof(address);address.sin_family=SCE_NET_AF_INET;
    address.sin_addr.s_addr=sceNetHtonl(SCE_NET_INADDR_ANY);
    if (nonblock(fd)<0 || sceNetBind(fd,(SceNetSockaddr *)&address,sizeof(address))<0) {
        sceNetSocketClose(fd);return -1;
    }
    return fd;
}
static int run_link(SceSize argc,void *argv) {
    (void)argc;(void)argv;
    int udp=-1;unsigned previous_serial=0;
    uint64_t last_discovery=0,next_audio=0,next_control=0;
    while (__atomic_load_n(&alive,__ATOMIC_ACQUIRE)) {
        uint64_t now=sceKernelGetProcessTimeWide();
        char ip[32],save_ip[32];unsigned ap,cp,request;int manual,remote,connect,need_audio,need_control,persist,persist_mode;
        RemoteProfile profile;AudioQuality quality_to_save;int persist_quality,persist_display;unsigned display_to_save;
        sceKernelLockMutex(mutex,1,NULL);
        snprintf(ip,sizeof(ip),"%s",shared.ip);ap=audio_port;cp=control_port;request=serial;
        manual=shared.manual;remote=shared.remote_mode;profile=shared.remote;
        finish_switch();
        connect=shared.paired && shared.desired && !shared.editing && !switch_pending && (!remote || shared.remote_available);
        need_audio=connect && !audio_hold && !audio_busy && audio_fd<0;
        need_control=connect && !control_busy && control_fd<0;
        persist_mode=save_mode;save_mode=0;
        persist=save_pending;save_pending=0;snprintf(save_ip,sizeof(save_ip),"%s",shared.manual?shared.ip:"");
        persist_quality=save_quality_pending;save_quality_pending=0;quality_to_save=saved_quality;
        persist_display=save_display_pending;save_display_pending=0;display_to_save=saved_display;
        if (!connect || audio_hold) {
            if (audio_fd>=0) { secure_net_close(audio_fd);audio_fd=-1;audio_busy=0; }
        }
        if (!connect) {
            if (control_fd>=0) { secure_net_close(control_fd);control_fd=-1;control_busy=0; }
        }
        sceKernelUnlockMutex(mutex,1);
        if (persist)save_address(save_ip);
        if (persist_mode)save_connection_mode(remote);
        if (persist_quality)aq_save(&quality_to_save,"ux0:data/vita-audio-receiver/quality.bin");
        if (persist_display)display_settings_save(display_to_save,"ux0:data/vita-audio-receiver/display.bin");
        if (request!=previous_serial) { previous_serial=request;next_audio=next_control=0;last_discovery=0; }
        if (remote && udp>=0) { sceNetSocketClose(udp);udp=-1; }
        if (shared.paired && !remote && udp<0)udp=open_discovery();
        if (shared.paired && !manual && udp>=0 && now-last_discovery>=2000000ULL) {
            SceNetSockaddrIn broadcast={0};broadcast.sin_len=sizeof(broadcast);broadcast.sin_family=SCE_NET_AF_INET;
            broadcast.sin_port=sceNetHtons(PC_DISCOVERY);broadcast.sin_addr.s_addr=sceNetHtonl(SCE_NET_INADDR_BROADCAST);
            uint8_t query[SECURE_DISCOVERY_QUERY];
            if (secure_net_query(query)==0)
                sceNetSendto(udp,query,sizeof(query),0,(SceNetSockaddr *)&broadcast,sizeof(broadcast));
            last_discovery=now;
        }
        if (udp>=0) {
            uint8_t response[SECURE_DISCOVERY_REPLY+1];SceNetSockaddrIn from={0};unsigned size=sizeof(from);
            int n=sceNetRecvfrom(udp,response,sizeof(response),0,(SceNetSockaddr *)&from,&size);
            if (n>0) {
                unsigned found_ap=0,found_cp=0;char name[32]={0},found_ip[32]={0};
                if (secure_net_reply(response,(size_t)n,&found_ap,&found_cp,name)==1 &&
                    sceNetInetNtop(SCE_NET_AF_INET,&from.sin_addr,found_ip,sizeof(found_ip))) {
                    sceKernelLockMutex(mutex,1,NULL);
                    if (!shared.remote_mode && !shared.manual && !audio_busy && !control_busy) {
                        snprintf(shared.ip,sizeof(shared.ip),"%s",found_ip);snprintf(shared.name,sizeof(shared.name),"%s",name);
                        snprintf(shared.message,sizeof(shared.message),"Windows host found. Connecting...");
                        audio_port=found_ap;control_port=found_cp;
                        snprintf(ip,sizeof(ip),"%s",found_ip);ap=found_ap;cp=found_cp;
                    }
                    sceKernelUnlockMutex(mutex,1);
                }
            } else if (n<0 && !again()) { sceNetSocketClose(udp);udp=-1; }
        }
        if (connect && (remote || ip[0])) {
            for (int channel=0;channel<2;++channel) {
                int needed=channel?need_control:need_audio;
                uint64_t *next=channel?&next_control:&next_audio;
                if (!needed || now<*next)continue;
                *next=now+2000000ULL;
                char target[32];int resolved=0;
                if(remote)resolved=resolve_host(channel?profile.control_host:profile.audio_host,target);
                else snprintf(target,sizeof(target),"%s",ip);
                unsigned target_port=remote?(channel?profile.control_port:profile.audio_port):(channel?cp:ap);
                /* Keep the original DNS name after resolving: Funnel routes the
                 * encrypted ClientHello by SNI, not by the relay's public IP. */
                const char *hostname=remote?(channel?profile.control_host:profile.audio_host):NULL;
                SceNetInAddr numeric;
                if(hostname && sceNetInetPton(SCE_NET_AF_INET,hostname,&numeric)==1)hostname=NULL;
                int fd=resolved<0?-1:connect_pc(target,target_port,!channel,hostname);
                sceKernelLockMutex(mutex,1,NULL);
                if (fd>=0 && shared.desired && !shared.editing && serial==request && (channel || !audio_hold)) {
                    if (channel) { control_fd=fd;control_busy=1; }
                    else { audio_fd=fd;audio_busy=1; }
                    snprintf(shared.message,sizeof(shared.message),"Encrypted connection to paired Windows host.");
                } else {
                    if (fd>=0)secure_net_close(fd);
                    if (shared.desired && serial==request)snprintf(shared.message,sizeof(shared.message),"%s",resolved<0?"DNS failed. Check Wi-Fi and remote profile.":remote?"Tunnel unavailable. Check PC tunnel and profile.":"Waiting for paired PC. Check Host Status or pairing.");
                }
                sceKernelUnlockMutex(mutex,1);
            }
        }
        sceKernelDelayThread(20000);
    }
    if (udp>=0)sceNetSocketClose(udp);
    if (audio_fd>=0) { secure_net_close(audio_fd);audio_fd=-1; }
    if (control_fd>=0) { secure_net_close(control_fd);control_fd=-1; }
    return 0;
}
int pc_link_start(void) {
    memset(&shared,0,sizeof(shared));shared.desired=1;serial=1;audio_hold=0;

    secure_net_start("ux0:data/vita-audio-receiver/vita-pairing.bin");
    shared.paired=(unsigned)secure_net_paired();
    snprintf(shared.message,sizeof(shared.message),"%s",shared.paired?"Searching for your paired Windows host...":"Run Pair Vita.cmd on your PC, then copy its file by USB.");
    FILE *f=fopen(CONFIG,"r");
    if (f) {
        char line[32]={0};if (fgets(line,sizeof(line),f)) {
            line[strcspn(line,"\r\n")]=0;
            if (parse_ip(line,shared.octets)) {
                snprintf(shared.ip,sizeof(shared.ip),"%s",line);shared.manual=1;
                snprintf(shared.name,sizeof(shared.name),"Saved PC address");
            }
        }
        fclose(f);
    }
    load_remote();
    f=fopen(MODE_CONFIG,"r");
    if(f) { char mode[16]={0};if(fgets(mode,sizeof(mode),f) && !strcmp(mode,"remote\n"))shared.remote_mode=1;fclose(f); }
    mutex=sceKernelCreateMutex("pc-link-state",0,0,NULL);if (mutex<0) { secure_net_stop();return mutex; }
    worker=sceKernelCreateThread("pc-link",run_link,112,0x20000,0,0,NULL);
    if (worker<0) { int rc=worker;sceKernelDeleteMutex(mutex);mutex=-1;secure_net_stop();return rc; }
    __atomic_store_n(&wanted,1,__ATOMIC_RELEASE);__atomic_store_n(&alive,1,__ATOMIC_RELEASE);
    int rc=sceKernelStartThread(worker,0,NULL);
    if (rc<0) { sceKernelDeleteThread(worker);sceKernelDeleteMutex(mutex);worker=mutex=-1;secure_net_stop();return rc; }
    __atomic_store_n(&ready,1,__ATOMIC_RELEASE);return 0;
}
void pc_link_snapshot(PcLinkView *view) {
    if (!__atomic_load_n(&ready,__ATOMIC_ACQUIRE))return;
    if (sceKernelTryLockMutex(mutex,1)<0)return;
    *view=shared;sceKernelUnlockMutex(mutex,1);
}
void pc_link_request(int connect) {
    if (!__atomic_load_n(&ready,__ATOMIC_ACQUIRE))return;
    sceKernelLockMutex(mutex,1,NULL);shared.desired=!!connect;++serial;
    snprintf(shared.message,sizeof(shared.message),"%s",connect?"Connecting to Windows host...":"Disconnected. Press X to reconnect.");
    update_wanted();sceKernelUnlockMutex(mutex,1);
}
int pc_link_wanted(void) { return __atomic_load_n(&wanted,__ATOMIC_ACQUIRE); }
static int take(int control) {
    if (!__atomic_load_n(&ready,__ATOMIC_ACQUIRE))return -1;
    sceKernelLockMutex(mutex,1,NULL);int *slot=control?&control_fd:&audio_fd;
    int fd=shared.desired && !shared.editing && !switch_pending && (control || !audio_hold) && __atomic_load_n(&wanted,__ATOMIC_ACQUIRE)?*slot:-1;if (fd>=0)*slot=-1;
    sceKernelUnlockMutex(mutex,1);return fd;
}
int pc_link_take_audio(void) { return take(0); }
int pc_link_take_control(void) { return take(1); }
int pc_link_editing(void) { return __atomic_load_n(&editing,__ATOMIC_ACQUIRE); }
int pc_link_remote_mode(void) {
    if(!__atomic_load_n(&ready,__ATOMIC_ACQUIRE))return 0;
    sceKernelLockMutex(mutex,1,NULL);int mode=(int)shared.remote_mode;sceKernelUnlockMutex(mutex,1);return mode;
}
int pc_link_save_quality(unsigned local,unsigned remote) {
    if(!__atomic_load_n(&ready,__ATOMIC_ACQUIRE) || !aq_valid(local) || !aq_valid(remote))return 0;
    sceKernelLockMutex(mutex,1,NULL);saved_quality.modes[0]=local;saved_quality.modes[1]=remote;
    save_quality_pending=1;sceKernelUnlockMutex(mutex,1);return 1;
}
int pc_link_save_display(unsigned timeout_seconds) {
    if(!__atomic_load_n(&ready,__ATOMIC_ACQUIRE) || !display_timeout_valid(timeout_seconds))return 0;
    sceKernelLockMutex(mutex,1,NULL);saved_display=timeout_seconds;save_display_pending=1;
    sceKernelUnlockMutex(mutex,1);return 1;
}
static void closed(int control) {
    if (!__atomic_load_n(&ready,__ATOMIC_ACQUIRE))return;
    sceKernelLockMutex(mutex,1,NULL);
    if (control)control_busy=0;else audio_busy=0;
    sceKernelUnlockMutex(mutex,1);
}
void pc_link_audio_closed(void) { closed(0); }
void pc_link_audio_hold(int hold) {
    if(!__atomic_load_n(&ready,__ATOMIC_ACQUIRE))return;
    sceKernelLockMutex(mutex,1,NULL);
    if(audio_hold!=!!hold) {
        audio_hold=!!hold;++serial;
        /* A pending socket may predate the marker. Never adopt it on release. */
        if(audio_hold && audio_fd>=0) { secure_net_close(audio_fd);audio_fd=-1;audio_busy=0; }
    }
    sceKernelUnlockMutex(mutex,1);
}
void pc_link_control_closed(void) { closed(1); }
unsigned pc_link_buttons(unsigned pressed,int audio_connected) {
    if (!__atomic_load_n(&ready,__ATOMIC_ACQUIRE))return 0;
    unsigned used=0;
    if (!shared.paired)return pressed&(SCE_CTRL_CROSS|SCE_CTRL_SELECT);
    sceKernelLockMutex(mutex,1,NULL);
    if (shared.editing && shared.remote_mode) {
        used=pressed&(SCE_CTRL_CROSS|SCE_CTRL_CIRCLE|SCE_CTRL_TRIANGLE|SCE_CTRL_SELECT);
        if(pressed&(SCE_CTRL_CIRCLE|SCE_CTRL_SELECT)) { shared.editing=0;++serial; }
        if(pressed&SCE_CTRL_CROSS) { shared.editing=0;shared.desired=1;++serial; }
        if(pressed&SCE_CTRL_TRIANGLE) { shared.remote_mode=0;save_mode=1;switch_pending=1;shared.editing=0;shared.desired=1;++serial; }
    } else if (shared.editing) {
        used=pressed&(SCE_CTRL_LEFT|SCE_CTRL_RIGHT|SCE_CTRL_UP|SCE_CTRL_DOWN|SCE_CTRL_LTRIGGER|
            SCE_CTRL_RTRIGGER|SCE_CTRL_CROSS|SCE_CTRL_CIRCLE|SCE_CTRL_TRIANGLE|SCE_CTRL_SELECT|SCE_CTRL_SQUARE);
        if (pressed&SCE_CTRL_LEFT)shared.selected=(shared.selected+3)%4;
        if (pressed&SCE_CTRL_RIGHT)shared.selected=(shared.selected+1)%4;
        int delta=(pressed&SCE_CTRL_UP)?1:(pressed&SCE_CTRL_DOWN)?-1:(pressed&SCE_CTRL_RTRIGGER)?10:(pressed&SCE_CTRL_LTRIGGER)?-10:0;
        shared.octets[shared.selected]=(shared.octets[shared.selected]+delta+256)%256;
        if (pressed&SCE_CTRL_CIRCLE) {
            shared.editing=0;++serial;
        }
        if (pressed&SCE_CTRL_TRIANGLE) {
            shared.manual=0;shared.ip[0]=0;shared.name[0]=0;shared.editing=0;shared.desired=1;save_pending=1;++serial;
            snprintf(shared.message,sizeof(shared.message),"Searching for a Windows host...");
        }
        if (pressed&SCE_CTRL_CROSS) {
            char address[32];snprintf(address,sizeof(address),"%u.%u.%u.%u",shared.octets[0],shared.octets[1],shared.octets[2],shared.octets[3]);
            unsigned check[4];
            if (parse_ip(address,check)) {
                snprintf(shared.ip,sizeof(shared.ip),"%s",address);shared.manual=1;shared.editing=0;shared.desired=1;
                snprintf(shared.name,sizeof(shared.name),"Saved PC address");audio_port=PC_AUDIO;control_port=PC_CONTROL;
                save_pending=1;++serial;
            }
        }
    } else if (!audio_connected) {
        if(pressed&SCE_CTRL_TRIANGLE) {
            shared.remote_mode^=1;save_mode=1;switch_pending=1;shared.desired=1;++serial;used|=SCE_CTRL_TRIANGLE;
            load_remote();
            snprintf(shared.message,sizeof(shared.message),"%s",shared.remote_mode?"Connecting through saved remote tunnel...":"Searching for your local Windows host...");
        }
        if (pressed&SCE_CTRL_SELECT) {
            shared.editing=1;used|=SCE_CTRL_SELECT;++serial;
            if (!parse_ip(shared.ip,shared.octets)) { shared.octets[0]=192;shared.octets[1]=168;shared.octets[2]=1;shared.octets[3]=10; }
        }
        if (pressed&SCE_CTRL_CROSS) {
            shared.desired=1;++serial;used|=SCE_CTRL_CROSS;
        }
    }
    update_wanted();
    __atomic_store_n(&editing,(int)shared.editing,__ATOMIC_RELEASE);
    sceKernelUnlockMutex(mutex,1);return used;
}
void pc_link_stop(void) {
    if (!__atomic_load_n(&ready,__ATOMIC_ACQUIRE))return;
    __atomic_store_n(&alive,0,__ATOMIC_RELEASE);__atomic_store_n(&wanted,0,__ATOMIC_RELEASE);
    sceKernelWaitThreadEnd(worker,NULL,NULL);sceKernelDeleteThread(worker);
    /* Keep an address saved even if START follows the save button immediately. */
    if (save_pending) { save_address(shared.manual?shared.ip:"");save_pending=0; }
    if (save_mode) { save_connection_mode(shared.remote_mode);save_mode=0; }
    if (save_quality_pending) { aq_save(&saved_quality,"ux0:data/vita-audio-receiver/quality.bin");save_quality_pending=0; }
    if (save_display_pending) { display_settings_save(saved_display,"ux0:data/vita-audio-receiver/display.bin");save_display_pending=0; }
    __atomic_store_n(&ready,0,__ATOMIC_RELEASE);sceKernelDeleteMutex(mutex);worker=mutex=-1;
    secure_net_stop();
}
