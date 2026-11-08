#ifndef RECEIVER_PC_LINK_H
#define RECEIVER_PC_LINK_H
#include "remote_profile.h"
typedef struct {
    char name[64],ip[32],message[112];
    unsigned desired,editing,selected,octets[4],manual,paired;
    unsigned remote_mode,remote_available;
    RemoteProfile remote;
} PcLinkView;
int pc_link_start(void);
void pc_link_stop(void);
void pc_link_snapshot(PcLinkView *view);
unsigned pc_link_buttons(unsigned pressed,int audio_connected);
void pc_link_request(int connect);
int pc_link_wanted(void);
int pc_link_editing(void);
int pc_link_remote_mode(void);
int pc_link_save_quality(unsigned local,unsigned remote);
int pc_link_save_display(unsigned timeout_seconds);
int pc_link_take_audio(void);
int pc_link_take_control(void);
void pc_link_audio_closed(void);
void pc_link_audio_hold(int hold);
void pc_link_control_closed(void);
#endif
