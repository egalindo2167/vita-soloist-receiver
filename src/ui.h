#ifndef RECEIVER_UI_H
#define RECEIVER_UI_H

#include <stdint.h>
#include "control.h"
#include "pc_link.h"
#include "screen_policy.h"

#define UI_WIDTH 960
#define UI_HEIGHT 544

typedef struct {
    char status[128];
    uint64_t played_seconds;
    unsigned buffer_ms;
    unsigned underruns;
    int connected;
    int playing;
    int muted;
    int network_ready;
    int error;
    unsigned capture_error;
    int testing;
    int screen_mode;
    unsigned opus_bitrate;
    unsigned quality_modes[2],quality_tab;
    int quality_open;
    unsigned settings_open,settings_page,settings_selected,screen_timeout;
    PcLinkView link;
} ReceiverUiState;

/* The renderer is platform independent so the exact screen can be previewed. */
void ui_render_frame(uint32_t *pixels, const ReceiverUiState *state, const char *ip);
void ui_render_player(uint32_t *pixels,const ReceiverUiState *state,const char *ip,const SpotifyView *spotify);
void ui_apply_screen(uint32_t *pixels,int screen_mode);
int ui_start(void);
const char *ui_startup_stage(void);
/* Nonblocking: an occasional skipped visual update must never delay audio. */
void ui_publish(const ReceiverUiState *state);
void ui_stop(void);

#endif
