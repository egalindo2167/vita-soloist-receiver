#ifndef RECEIVER_CONTROL_H
#define RECEIVER_CONTROL_H
#include <stdint.h>
#include <stddef.h>
#include "search_keyboard.h"
#define CTL_ITEMS 32
#define CTL_ART_EDGE 224
#define CTL_ART_BYTES (CTL_ART_EDGE*CTL_ART_EDGE*2)
#define CTL_STATE_BYTES (44+192*3+128+160)
#define CTL_ITEM_BYTES 384
#define CTL_COMMAND_BYTES 136
#define CTL_MAX_PAYLOAD (CTL_ART_BYTES+4)
typedef struct { char title[128], artist[128], uri[128];uint32_t position; } ControlItem;
typedef struct {
    uint32_t generation, online, api_online, logged_in, active, status;
    uint32_t volume, shuffle, repeat, position_ms, duration_ms, art_id, has_art, art_received;
    char title[192], artist[192], album[192], uri[128], message[160];
    uint32_t queue_count, favorite_count, browser, tab, selected;
    uint32_t audio_flush_id,audio_flush_hold;
    uint32_t queue_paged,queue_request_id,queue_revision,queue_offset,queue_total,queue_available,queue_flags;
    uint32_t queue_loading,queue_wanted_offset,queue_select_last;
    char queue_query[128];
    uint32_t queue_confirm,confirm_distance,jump_done,jump_total;
    char confirm_token[128],confirm_title[128];
    SearchKeyboard keyboard;
    ControlItem queue[CTL_ITEMS], favorites[CTL_ITEMS];
    uint16_t art[CTL_ART_EDGE*CTL_ART_EDGE];
} SpotifyView;
enum { CTL_TOGGLE=1, CTL_PREV, CTL_NEXT, CTL_VOLUME_DELTA, CTL_VOLUME,
       CTL_SHUFFLE, CTL_REPEAT, CTL_PLAY_URI, CTL_SEEK_DELTA, CTL_SEEK, CTL_REFRESH, CTL_PLAY_QUEUE,
       CTL_QUEUE_SEARCH,CTL_QUEUE_PAGE,CTL_QUEUE_CANCEL };
uint32_t ctl_read32(const uint8_t *p);
void ctl_write32(uint8_t *p, uint32_t n);
int ctl_frame_valid(const uint8_t *tag, uint32_t n);
int ctl_apply(SpotifyView *view, const uint8_t *tag, const uint8_t *payload, size_t n);
int control_start(void);
void control_stop(void);
int control_snapshot(SpotifyView *view);
unsigned control_buttons(unsigned pressed);
void control_touch(int x, int y, int fresh);
void control_navigate(unsigned page);
int control_take_disconnect(void);
int control_online(void);
int control_audio_flush(uint32_t *id,unsigned *hold);
void control_audio_stats(unsigned buffer_ms,unsigned underruns,unsigned seconds,int playing,unsigned kbps,int remote);
#endif
