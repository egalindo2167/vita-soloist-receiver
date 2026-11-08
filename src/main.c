#include <psp2/audioout.h>
#include <psp2/ctrl.h>
#include <psp2/display.h>
#include <psp2/kernel/processmgr.h>
#include <psp2/kernel/threadmgr.h>
#include <psp2/net/net.h>
#include <psp2/net/netctl.h>
#include <psp2/power.h>
#include <psp2/sysmodule.h>
#include <psp2/touch.h>
#include <stdio.h>
#include <stdarg.h>
#include <math.h>
#include <psp2/io/fcntl.h>
#include <psp2/io/stat.h>
#include <stdlib.h>
#include <string.h>
#include "debugScreen.h"
#include "protocol.h"
#include "opus_stream.h"
#include "secure_net.h"
#include "audio_buffers.h"
#include "ui.h"
#include "version.h"
#include "audio_quality.h"
#include "settings_menu.h"
#include "display_settings.h"

_Static_assert(VPCM_RATE == 48000, "The Vita MAIN audio port requires 48000 Hz");

#include "audio_policy.h"
#include "audio_reset.h"
#define CAPACITY AUDIO_CAPACITY_BYTES
#define QUALITY_PATH "ux0:data/vita-audio-receiver/quality.bin"
#define NET_HEAP_BYTES (2 * 1024 * 1024)
static uint8_t queue[CAPACITY];
static uint8_t header[VPCM_HEADER_BYTES];
static VpcmAudioBuffers audio_buffers;
static char status[128] = "Waiting for computer";
static FILE *logfile;
static int ui_started, network_ready;
static ScreenPolicy screen;
static int wireless_previous=-1;
static OpusStream opus;
static uint8_t compressed[8192];
static unsigned opus_bitrate;
static unsigned capture_error;
static AudioQuality quality;
static SettingsMenu settings;
static int route_remote(void) { return pc_link_remote_mode(); }
static void save_quality(void) {
    if(!pc_link_save_quality(quality.modes[0],quality.modes[1]))
        snprintf(status,sizeof(status),"Could not queue quality preference; it applies for this session.");
}
static int settings_input(unsigned *pressed,int fresh,int x,int y) {
    unsigned b=*pressed,keys=0;
    if(b&SCE_CTRL_SELECT)keys|=MENU_OPEN;
    if(b&SCE_CTRL_CIRCLE)keys|=MENU_BACK;
    if(b&SCE_CTRL_CROSS)keys|=MENU_ACTIVATE;
    if(b&SCE_CTRL_UP)keys|=MENU_UP;
    if(b&SCE_CTRL_DOWN)keys|=MENU_DOWN;
    if(b&SCE_CTRL_LEFT)keys|=MENU_LEFT;
    if(b&SCE_CTRL_RIGHT)keys|=MENU_RIGHT;
    if(b&SCE_CTRL_LTRIGGER)keys|=MENU_L;
    if(b&SCE_CTRL_RTRIGGER)keys|=MENU_R;
    int consumed=0;
    unsigned action=settings_menu_input(&settings,&quality,keys,fresh,x,y,route_remote(),&consumed);
    if(consumed)*pressed=0;
    if(action&SETTINGS_QUALITY)save_quality();
    if(action&SETTINGS_DISPLAY) {
        screen_policy_set_timeout(&screen,settings.timeout_seconds);
        if(!pc_link_save_display(settings.timeout_seconds))
            snprintf(status,sizeof(status),"Screen timeout applies for this session; could not save it.");
    }
    if(action&SETTINGS_ROUTE) {
        if(pc_link_editing())pc_link_buttons(SCE_CTRL_CIRCLE,0);
        pc_link_buttons(SCE_CTRL_TRIANGLE,0);
    }
    if((action&SETTINGS_DETAILS) && !pc_link_editing())pc_link_buttons(SCE_CTRL_SELECT,0);
    if(action&SETTINGS_NAV_PLAYER)control_navigate(0);
    if(action&SETTINGS_NAV_QUEUE)control_navigate(1);
    if(action&SETTINGS_NAV_FAVORITES)control_navigate(2);
    return consumed;
}

static void publish_ui(int connected, int playing, int muted, size_t used,
                       uint64_t frames, unsigned underruns, int error, int testing) {
    ReceiverUiState state = {0};
    snprintf(state.status, sizeof(state.status), "%s", status);
    state.connected=connected; state.playing=playing; state.muted=muted;
    state.buffer_ms=(unsigned)(used*1000/(VPCM_RATE*4));
    state.played_seconds=frames/VPCM_RATE; state.underruns=underruns;
    state.network_ready=network_ready; state.error=error; state.testing=testing;
    state.capture_error=capture_error;
    state.screen_mode=screen.mode;
    state.opus_bitrate=opus_bitrate;
    state.quality_modes[0]=quality.modes[0];state.quality_modes[1]=quality.modes[1];
    state.quality_tab=quality.tab;state.quality_open=settings.open && settings.page==SETTINGS_AUDIO;
    state.settings_open=settings.open;state.settings_page=settings.page;state.settings_selected=settings.selected;
    state.screen_timeout=settings.timeout_seconds;
    ui_publish(&state);
}
static void log_line(const char *fmt, ...) {
    if (!logfile) return;
    fprintf(logfile, "[%llu] ", (unsigned long long)sceKernelGetProcessTimeWide());
    va_list args; va_start(args, fmt); vfprintf(logfile, fmt, args); va_end(args);
    fputc('\n', logfile); fflush(logfile);
}
static void describe(const char *s) {
    snprintf(status, sizeof(status), "%s", s);
    log_line("%s", s);
}
static int open_audio(void) {
    int port = sceAudioOutOpenPort(SCE_AUDIO_OUT_PORT_TYPE_MAIN, VPCM_FRAMES,
                                  VPCM_RATE, SCE_AUDIO_OUT_MODE_STEREO);
    log_line("MAIN port open: rate=%d frames=%d result=0x%08X", VPCM_RATE, VPCM_FRAMES, port);
    if (port >= 0) {
        int vol[2] = {SCE_AUDIO_VOLUME_0DB, SCE_AUDIO_VOLUME_0DB};
        int rc = sceAudioOutSetVolume(port, SCE_AUDIO_VOLUME_FLAG_L_CH | SCE_AUDIO_VOLUME_FLAG_R_CH, vol);
        log_line("Set audio volume: 0x%08X", rc);
    }
    return port;
}
static void reply_to_sender(int fd, int ok, uint32_t code) {
    uint8_t reply[VPCM_REPLY_BYTES]; vpcm_reply(reply, ok, code);
    size_t sent = 0;
    uint64_t start = sceKernelGetProcessTimeWide();
    while (sent < sizeof(reply) && sceKernelGetProcessTimeWide()-start < 250000) {
        int n = secure_net_write(fd, reply+sent, sizeof(reply)-sent);
        if (n > 0) sent += n;
        else if (n == SECURE_NET_RETRY) sceKernelDelayThread(1000);
        else break;
    }
    log_line("Startup reply: %s code=0x%08X bytes=%u", ok ? "ready" : "error", code, (unsigned)sent);
}
static void local_tone(void) {
    int port = open_audio();
    if (port < 0) {
        snprintf(status, sizeof(status), "Local tone: audio open failed 0x%08X", port);
        log_line("%s", status); return;
    }
    describe("Playing a short local tone. No computer connection is needed.");
    publish_ui(0,0,0,0,0,0,0,1);
    unsigned sample = 0;
    for (int block=0; block<48; ++block) {
        int16_t *output = vpcm_next_audio_buffer(&audio_buffers);
        for (int i=0; i<VPCM_FRAMES; ++i, ++sample) {
            int16_t value = (int16_t)(3500.0*sin(6.28318530718*440*sample/VPCM_RATE));
            output[2*i]=output[2*i+1]=value;
        }
        int rc=sceAudioOutOutput(port, output);
        if (rc<0) { snprintf(status,sizeof(status),"Local tone: output failed 0x%08X",rc);
            log_line("%s",status); sceAudioOutReleasePort(port); return; }
    }
    sceAudioOutOutput(port,NULL); sceAudioOutReleasePort(port);
    describe("Local tone finished. Waiting for computer.");
}
int main(void) {
    screen_policy_init(&screen,sceKernelGetProcessTimeWide());
    sceIoMkdir("ux0:data", 0777);
    sceIoMkdir("ux0:data/vita-audio-receiver", 0777);
    aq_init(&quality);aq_load(&quality,QUALITY_PATH);
    settings_menu_init(&settings);
    display_settings_load(&settings.timeout_seconds,"ux0:data/vita-audio-receiver/display.bin");
    screen_policy_set_timeout(&screen,settings.timeout_seconds);
    logfile = fopen("ux0:data/vita-audio-receiver/log.txt", "w");
    log_line("Vita Audio Receiver %s starting", RECEIVER_VERSION);
    int ui_result=ui_start();
    if (ui_result < 0) {
        log_line("UI initialization failed at %s: 0x%08X", ui_startup_stage(), ui_result);
        goto fatal;
    }
    log_line("UI started successfully (priority 127)");
    ui_started=1;
    sceCtrlSetSamplingMode(SCE_CTRL_MODE_DIGITAL);
    sceTouchSetSamplingState(SCE_TOUCH_PORT_FRONT,SCE_TOUCH_SAMPLING_STATE_START);
    if (sceSysmoduleLoadModule(SCE_SYSMODULE_NET) < 0) goto fatal;
    void *netmem = malloc(NET_HEAP_BYTES);
    if (!netmem) goto fatal;
    SceNetInitParam np = {0};
    np.memory = netmem; np.size = NET_HEAP_BYTES;
    if (sceNetInit(&np) < 0) { free(netmem); goto fatal; }
    if (sceNetCtlInit() < 0) { sceNetTerm(); free(netmem); goto fatal; }
    wireless_previous=scePowerGetUsingWireless();
    int wireless_result=scePowerSetUsingWireless(1);
    log_line("Wireless-use hint: previous=%d result=0x%08X",wireless_previous,wireless_result);
    network_ready=1;
    int link_result=pc_link_start();
    log_line("PC host discovery startup: 0x%08X",link_result);
    int controls_result=control_start();
    log_line("Spotify controls startup: 0x%08X (paired TLS)",controls_result);
    if (link_result<0 || controls_result<0)goto network_cleanup;
    describe("Connecting to the paired Windows host. SELECT changes the PC address.");
    int client = -1, audio = -1, muted = 0, playing = 0, eof = 0;
    size_t used = 0, have_header = 0;
    size_t compressed_read=0,compressed_have=0;
    unsigned old_buttons = 0;
    uint64_t last_data = 0, last_ui_update = 0, frames_played = 0;
    uint64_t received_bytes=0;
    unsigned underruns=0;
    int touch_was_down=0;
    int menu_held_touch=0,session_remote=0;
    uint8_t feedback[36];size_t feedback_sent=0,feedback_size=0;
    uint64_t next_feedback=0;unsigned sent_mode=~0u;
    int controls_were_online=0;
    AudioResetPolicy reset_policy={0};
    uint64_t last_touch=0;
    uint64_t last_power_tick=0;
    for (;;) {
        SceCtrlData pad = {0}; sceCtrlPeekBufferPositive(0, &pad, 1);
        /* System interception is a status bit, never a user's wake gesture. */
        unsigned buttons=pad.buttons & ~SCE_CTRL_INTERCEPTED;
        unsigned pressed = buttons & ~old_buttons; old_buttons = buttons;
        SceTouchData touch={0};
        int touch_ok=sceTouchPeek(SCE_TOUCH_PORT_FRONT,&touch,1)>=0;
        int touching=touch_ok && touch.reportNum;
        uint64_t input_time=sceKernelGetProcessTimeWide();
        int previous_screen=screen.mode;
        int screen_input=screen_policy_step(&screen,input_time,buttons,&pressed,touching,
            touching && !touch_was_down,touching?touch.report[0].x/2:0,touching?touch.report[0].y/2:0);
        if (previous_screen!=screen.mode) {
            log_line("Screen mode: %s",screen.mode==SCREEN_BLACK?"black / display off":
                     screen.mode==SCREEN_DIM?"dim":"active");
            /* Wake before the UI can queue another framebuffer flip. */
            if (previous_screen==SCREEN_BLACK)scePowerRequestDisplayOn();
            last_ui_update=0;
        }
        if (pressed & SCE_CTRL_START) break;
        if(!touching)menu_held_touch=0;
        int menu_consumed=0;
        if(!screen_input) {
            menu_consumed=settings_input(&pressed,touching && !touch_was_down,
                touching?touch.report[0].x/2:0,touching?touch.report[0].y/2:0);
            if(menu_consumed && touching)menu_held_touch=1;
        }
        int controls_are_online=control_online();
        uint32_t flush=0;unsigned hold=0;
        if(control_audio_flush(&flush,&hold) && audio_reset_event(&reset_policy,flush,hold,input_time)) {
            pc_link_audio_hold(1);
            if(client>=0) { secure_net_close(client);client=-1;pc_link_audio_closed(); }
            used=have_header=compressed_read=compressed_have=0;playing=eof=0;
            opus_stream_close(&opus);opus_bitrate=0;
            if(audio>=0) { sceAudioOutOutput(audio,NULL);sceAudioOutReleasePort(audio);audio=-1; }
            if(!hold)pc_link_audio_hold(0);
            describe(hold?"Updating Spotify selection; old audio discarded":"Buffering the new Spotify selection");
        }
        if(audio_reset_timeout(&reset_policy,input_time,controls_are_online)) {
            pc_link_audio_hold(0);
            describe("Playback update timed out; reconnecting audio");
        }
        if (controls_are_online && !controls_were_online) muted=0;
        controls_were_online=controls_are_online;
        if (!screen_input && !menu_consumed) {
            pressed &= ~pc_link_buttons(pressed,client>=0 || (controls_are_online && !capture_error));
            if(!capture_error)pressed &= ~control_buttons(pressed);
        }
        if (!capture_error && !screen_input && !menu_consumed && !menu_held_touch && !pc_link_editing() && touching && (!touch_was_down || input_time-last_touch>=100000)) {
            control_touch(touch.report[0].x/2,touch.report[0].y/2,!touch_was_down);
            last_touch=input_time;
        }
        touch_was_down=touching;
        if (control_take_disconnect()) pressed|=SCE_CTRL_CIRCLE;
        if (pressed & SCE_CTRL_CROSS) muted = !muted;
        if ((pressed & SCE_CTRL_CIRCLE) && client >= 0) {
            pc_link_request(0);
            secure_net_close(client); client = -1; used = have_header = 0;
            opus_stream_close(&opus);opus_bitrate=0;
            pc_link_audio_closed();
            playing = eof = 0; describe("Disconnected; waiting for computer");
            if (audio >= 0) { sceAudioOutOutput(audio, NULL); sceAudioOutReleasePort(audio); audio = -1; }
        }
        if ((pressed&SCE_CTRL_CIRCLE) && client<0)pc_link_request(0);
        if (pressed & SCE_CTRL_SQUARE) {
            if (client < 0) local_tone();
            else describe("Disconnect sender with Circle before local tone");
        }
        uint64_t now = sceKernelGetProcessTimeWide();
        if (client < 0) {
            int fd=pc_link_take_audio();
            if (fd>=0) {
                client=fd;have_header=used=0;playing=eof=0;
                session_remote=route_remote();feedback_sent=feedback_size=0;next_feedback=0;sent_mode=~0u;
                compressed_read=compressed_have=0;
                opus_stream_close(&opus);opus_bitrate=0;
                frames_played=0;received_bytes=0;underruns=0;last_data=now;
                describe("Paired TLS 1.3 connection; reading stream header");
            }
        }
        if (client >= 0 && !eof) {
          if (have_header==sizeof(header) && opus_bitrate) {
            if (CAPACITY-used>=VOPS_PCM_BYTES) {
                if (compressed_read==compressed_have) {
                    compressed_read=compressed_have=0;
                    int n=secure_net_read(client,compressed,sizeof(compressed));
                    if (n>0) { compressed_have=(size_t)n;last_data=now; }
                    else if (!n) {
                        eof=1;describe(opus_stream_partial(&opus)?"Truncated Opus packet; reconnecting":"Sender finished");
                    } else if (n != SECURE_NET_RETRY) {
                        eof=1;describe("Opus network connection lost; reconnecting");
                    }
                }
                if (compressed_read<compressed_have) {
                    size_t consumed=0,written=0;
                    int rc=opus_stream_feed(&opus,compressed+compressed_read,compressed_have-compressed_read,
                        queue+used,CAPACITY-used,&consumed,&written);
                    compressed_read+=consumed;used+=written;received_bytes+=written;
                    if(written && opus.last_bitrate>=96000 && opus.last_bitrate<=320000 && opus.last_bitrate%1000==0)
                        opus_bitrate=opus.last_bitrate;
                    if (rc<0) { eof=1;log_line("Opus packet rejected: %d",rc);describe("Invalid Opus stream; reconnecting"); }
                }
            }
          } else {
            uint8_t *dest; size_t room;
            if (have_header < sizeof(header)) { dest = header+have_header; room = sizeof(header)-have_header; }
            else { dest = queue+used; room = CAPACITY-used; }
            if (room) {
                int n = secure_net_read(client, dest, room);
                if (n > 0) {
                    last_data = now;
                    if (have_header < sizeof(header)) {
                        have_header += n;
                        if (have_header == sizeof(header)) {
                            int pcm_format=vpcm_header_valid(header),opus_format=vops_header_valid(header);
                            unsigned capture_code=vaer_code(header,sizeof(header));
                            if (capture_code) {
                                capture_error=capture_code;describe(vaer_message(capture_code));eof=1;
                            } else if (!pcm_format && !opus_format) {
                                describe("Wrong stream format: use matching package sender");
                                reply_to_sender(client,0,1); eof = 1;
                            }
                            else {
                                capture_error=0; /* Host capture is ready; later failures are local audio errors. */
                                if (opus_format) {
                                    int rc=opus_stream_open(&opus);
                                    if (rc<0) {
                                        log_line("Opus decoder initialization failed: %d",rc);
                                        describe("Could not initialize Opus decoder");reply_to_sender(client,0,2);eof=1;
                                    } else opus_bitrate=vpcm_le32(header+12);
                                }
                                if (!eof) {
                                audio = open_audio();
                                if (audio < 0) {
                                    snprintf(status, sizeof(status), "Cannot open audio port: 0x%08X", audio);
                                    log_line("%s", status); reply_to_sender(client,0,(uint32_t)audio); eof = 1;
                                } else {
                                    reply_to_sender(client,1,VPCM_RATE);
                                    if (opus_bitrate) {
                                        snprintf(status,sizeof(status),"Opus %u kbps ready; buffering stream",opus_bitrate/1000);
                                        log_line("%s",status);
                                    } else describe("PCM audio ready; buffering stream");
                                }
                                }
                            }
                        }
                    } else { used += n;received_bytes+=(unsigned)n; }
                } else if (n == 0) { eof = 1; describe("Sender finished"); }
                else if (n != SECURE_NET_RETRY) {
                    log_line("recv failed: rc=0x%08X errno=%d", n, *sceNetErrnoLoc());
                    eof = 1; describe("Network connection lost; see log.txt");
                }
            }
          }
            if (now-last_data > 5000000ULL) { eof = 1; describe("Audio timed out; retrying the Windows host automatically"); }
        }
        if (audio >= 0 && !playing && (used >= audio_start_bytes(session_remote) || (eof && used))) {
            playing = 1;
            describe("PC audio connected. Choose music in Spotify on your phone or PC.");
        }
        int wrote = 0;
        if (audio >= 0 && playing && (used >= VPCM_BLOCK_BYTES || (eof && used))) {
            size_t n = used < VPCM_BLOCK_BYTES ? used : VPCM_BLOCK_BYTES;
            n -= n % 4;
            int16_t *output = vpcm_prepare_audio(&audio_buffers, queue, n, muted);
            int out_result = sceAudioOutOutput(audio, output);
            if (out_result < 0) {
                log_line("Audio output failed: 0x%08X", out_result);
                eof = 1; used = 0; describe("Audio output failed; see log.txt");
            }
            else { memmove(queue, queue+n, used-n); used -= n; frames_played += n/4; }
            wrote = 1;
        } else if (playing && !eof && used < VPCM_BLOCK_BYTES) {
            playing = 0; ++underruns;
            log_line("Playback rebuffer %u: buffered=%u bytes frames=%llu", underruns,
                     (unsigned)used,(unsigned long long)frames_played);
            describe("Buffering after network interruption");
        }
        if (client >= 0 && eof && (!used || audio < 0 || used < 4)) {
            secure_net_close(client); client = -1; used = have_header = 0; playing = eof = 0;
            opus_stream_close(&opus);opus_bitrate=0;
            pc_link_audio_closed();
            if (audio >= 0) { sceAudioOutOutput(audio, NULL); sceAudioOutReleasePort(audio); audio = -1; }
        }
        if (now-last_power_tick>=1000000ULL) {
            if (client>=0 || controls_are_online)
                sceKernelPowerTick(SCE_KERNEL_POWER_TICK_DISABLE_AUTO_SUSPEND);
            /* Keep natural panel-off out of a pending framebuffer flip. The
             * app presents black first, then explicitly powers the panel off. */
            if (screen.mode!=SCREEN_BLACK)
                sceKernelPowerTick(SCE_KERNEL_POWER_TICK_DISABLE_OLED_OFF);
            last_power_tick=now;
        }
        control_audio_stats((unsigned)(used*1000/(VPCM_RATE*4)),underruns,(unsigned)(frames_played/VPCM_RATE),playing,
            opus_bitrate/1000,client>=0?session_remote:route_remote());
        if(client>=0 && audio>=0 && !eof) {
            unsigned mode=quality.modes[session_remote];
            if(feedback_sent==feedback_size && (now>=next_feedback || mode!=sent_mode)) {
                aq_report_v2(feedback,mode,underruns,(unsigned)(used*1000/(VPCM_RATE*4)),
                    (unsigned)(frames_played/VPCM_RATE),playing,session_remote,opus_bitrate/1000,(uint32_t)(received_bytes/4));
                feedback_sent=0;feedback_size=sizeof(feedback);sent_mode=mode;next_feedback=now+250000ULL;
            }
            if(feedback_sent<feedback_size) {
                int n=secure_net_write(client,feedback+feedback_sent,feedback_size-feedback_sent);
                if(n>0)feedback_sent+=(size_t)n;
                else if(n!=SECURE_NET_RETRY) { eof=1;describe("Audio feedback connection lost; reconnecting"); }
            }
        }
        if (now-last_ui_update >= 200000ULL) {
            publish_ui(client>=0,playing,muted,used,frames_played,underruns,0,0);
            last_ui_update = now;
        }
        if (!wrote) sceKernelDelayThread(5000);
    }
    if (client >= 0) secure_net_close(client);
    opus_stream_close(&opus);
    if (audio >= 0) { sceAudioOutOutput(audio, NULL); sceAudioOutReleasePort(audio); }
    scePowerRequestDisplayOn();
    ui_stop(); control_stop(); pc_link_stop(); ui_started=0; network_ready=0;
    if (wireless_previous>=0)scePowerSetUsingWireless(wireless_previous);
    sceNetCtlTerm(); sceNetTerm(); free(netmem);
    log_line("Clean exit"); if (logfile) fclose(logfile);
    sceKernelExitProcess(0); return 0;
network_cleanup:
    scePowerRequestDisplayOn();
    ui_stop(); control_stop(); pc_link_stop(); ui_started=0; network_ready=0;
    if (wireless_previous>=0)scePowerSetUsingWireless(wireless_previous);
    sceNetCtlTerm(); sceNetTerm(); free(netmem);
fatal:
    describe("Could not initialize receiver. See log.txt for details. Press START to exit.");
    if (ui_started) publish_ui(0,0,0,0,0,0,1,0);
    else {
        psvDebugScreenInit();
        psvDebugScreenPrintf("\nCould not initialize receiver. See ux0:data/vita-audio-receiver/log.txt\nStart: exit\n");
    }
    for (;;) { SceCtrlData p = {0}; sceCtrlPeekBufferPositive(0, &p, 1);
        if (p.buttons & SCE_CTRL_START) break;
        sceKernelDelayThread(50000); }
    log_line("Initialization failed"); if (logfile) fclose(logfile);
    if (ui_started) ui_stop();
    sceKernelExitProcess(1); return 1;
}
