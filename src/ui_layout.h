#ifndef RECEIVER_UI_LAYOUT_H
#define RECEIVER_UI_LAYOUT_H
/* Visuals and input share these bounds. Insets belong to drawing, never to the
 * touch target; transport targets are at least 64 x 80 screen pixels. */
typedef struct { int x,y,w,h; } UiRect;
static inline int ui_hit(UiRect r,int x,int y) {
    return x>=r.x && x<r.x+r.w && y>=r.y && y<r.y+r.h;
}
#define UI_NAV_PLAYER ((UiRect){12,110,144,56})
#define UI_NAV_QUEUE ((UiRect){12,180,144,56})
#define UI_NAV_FAVORITES ((UiRect){12,250,144,56})
#define UI_GEAR ((UiRect){882,12,64,64})
#define UI_SCREEN_OFF ((UiRect){12,430,144,64})
#define UI_PAGE_UP ((UiRect){20,358,64,56})
#define UI_PAGE_DOWN ((UiRect){88,358,64,56})
#define UI_SHUFFLE ((UiRect){324,452,64,84})
#define UI_PREVIOUS ((UiRect){400,452,64,84})
#define UI_PLAY ((UiRect){472,448,88,88})
#define UI_NEXT ((UiRect){568,452,64,84})
#define UI_REPEAT ((UiRect){644,452,64,84})
#define UI_VOLUME_MUTE ((UiRect){716,454,56,80})
#define UI_VOLUME ((UiRect){772,454,160,80})
#define UI_SETTINGS_DONE ((UiRect){752,468,176,60})
#define UI_QUEUE_SEARCH ((UiRect){196,60,604,48})
#define UI_QUEUE_CLEAR ((UiRect){808,60,120,48})
#define UI_CONFIRM_GO ((UiRect){568,344,360,64})
#define UI_CONFIRM_CANCEL ((UiRect){196,344,348,64})
#define UI_SEEK ((UiRect){188,390,748,58})
#define UI_PROGRESS_X 204
#define UI_PROGRESS_W 704
#define UI_VOLUME_X 784
#define UI_VOLUME_W 132
#define UI_LIST_X 192
#define UI_LIST_Y 108
#define UI_LIST_W 740
#define UI_LIST_ROW_H 56
#define UI_LIST_ROWS 5
#define UI_SETTINGS_ROW_Y 112
#define UI_SETTINGS_ROW_H 68
#define UI_QUALITY_LOCAL ((UiRect){196,104,350,64})
#define UI_QUALITY_REMOTE ((UiRect){558,104,370,64})
static inline UiRect ui_quality_choice(unsigned i) {
    return (UiRect){196+(int)(i%4)*184,200+(int)(i/4)*76,172,64};
}
/* 0: player, 1: queue, 2: favorites; -1: outside navigation. */
static inline int ui_nav_at(int x,int y) {
    return ui_hit(UI_NAV_PLAYER,x,y)?0:ui_hit(UI_NAV_QUEUE,x,y)?1:
        ui_hit(UI_NAV_FAVORITES,x,y)?2:-1;
}
#endif
