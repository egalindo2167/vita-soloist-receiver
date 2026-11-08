#ifndef RECEIVER_SCREEN_POLICY_H
#define RECEIVER_SCREEN_POLICY_H
#include <stdint.h>
#include "ui_layout.h"

enum { SCREEN_ACTIVE, SCREEN_DIM, SCREEN_BLACK };
#define SCREEN_DIM_US 30000000ULL
#define SCREEN_BLACK_US 60000000ULL
/* The screen-off control has the same hit area on every page. */
#define SCREEN_BUTTON_X 12
#define SCREEN_BUTTON_Y 430
#define SCREEN_BUTTON_W 144
#define SCREEN_BUTTON_H 64

typedef struct {
    uint64_t last_activity;
    unsigned blocked_buttons;
    int mode,blocked_touch;
    unsigned timeout_seconds;
} ScreenPolicy;
void screen_policy_init(ScreenPolicy *state,uint64_t now);
void screen_policy_set_timeout(ScreenPolicy *state,unsigned seconds);
/* Returns nonzero when this input is only a screen action, never a music action.
 * Waking consumes the first gesture and suppresses held input until release. */
int screen_policy_step(ScreenPolicy *state,uint64_t now,unsigned buttons,
                       unsigned *pressed,int touching,int fresh_touch,int x,int y);
#endif
