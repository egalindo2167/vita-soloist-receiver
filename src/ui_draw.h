#ifndef RECEIVER_UI_DRAW_H
#define RECEIVER_UI_DRAW_H
#include <stdint.h>
#include "ui_layout.h"
enum { UF_SMALL,UF_BODY,UF_LABEL,UF_TITLE,UF_HERO };
enum { ICON_PLAY,ICON_PAUSE,ICON_PREVIOUS,ICON_NEXT,ICON_SHUFFLE,ICON_REPEAT,
       ICON_SPEAKER,ICON_GEAR,ICON_PLAYER,ICON_QUEUE,ICON_HEART,ICON_MOON,
       ICON_UP,ICON_DOWN,ICON_CHEVRON,ICON_BACK,ICON_LINK,ICON_CHECK,ICON_MUSIC,ICON_SEARCH };
#define UI_RGB(r,g,b) (0xff000000u|((uint32_t)(b)<<16)|((uint32_t)(g)<<8)|(r))
void ud_rect(uint32_t *p,UiRect r,uint32_t c);
void ud_round(uint32_t *p,UiRect r,int radius,uint32_t c);
void ud_circle(uint32_t *p,float x,float y,float radius,uint32_t c);
void ud_line(uint32_t *p,float x1,float y1,float x2,float y2,float width,uint32_t c);
void ud_icon(uint32_t *p,int icon,int x,int y,float size,uint32_t c);
int ud_width(unsigned font,const char *text);
void ud_text(uint32_t *p,int x,int y,unsigned font,uint32_t c,const char *text,int width);
void ud_wrap(uint32_t *p,int x,int y,unsigned font,uint32_t c,const char *text,int width,unsigned lines,int spacing);
#endif
