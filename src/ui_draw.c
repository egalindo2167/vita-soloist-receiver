#include "ui_draw.h"
#include "ui_font_data.h"
#include "ui.h"
#include <math.h>
#include <string.h>

static void pixel(uint32_t *p,int x,int y,uint32_t c,unsigned a) {
    if((unsigned)x>=UI_WIDTH || (unsigned)y>=UI_HEIGHT || !a)return;
    uint32_t *d=p+y*UI_WIDTH+x;
    if(a>=255) { *d=c;return; }
    unsigned b=255-a,r=((c&255)*a+(*d&255)*b+127)/255;
    unsigned g=(((c>>8)&255)*a+((*d>>8)&255)*b+127)/255;
    unsigned blue=(((c>>16)&255)*a+((*d>>16)&255)*b+127)/255;
    *d=UI_RGB(r,g,blue);
}
void ud_rect(uint32_t *p,UiRect r,uint32_t c) {
    int right=r.x+r.w,bottom=r.y+r.h;
    if(r.x<0)r.x=0;
    if(r.y<0)r.y=0;
    if(right>UI_WIDTH)right=UI_WIDTH;
    if(bottom>UI_HEIGHT)bottom=UI_HEIGHT;
    for(int y=r.y;y<bottom;++y)for(int x=r.x;x<right;++x)p[y*UI_WIDTH+x]=c;
}
void ud_round(uint32_t *p,UiRect r,int radius,uint32_t c) {
    if(radius<=0) { ud_rect(p,r,c);return; }
    if(radius>r.w/2)radius=r.w/2;
    if(radius>r.h/2)radius=r.h/2;
    for(int yy=0;yy<r.h;++yy) {
        float dy=yy<radius?radius-yy-0.5f:yy>=r.h-radius?yy-(r.h-radius)+0.5f:0;
        float inset=dy>0?radius-sqrtf((float)radius*radius-dy*dy):0;
        int edge=(int)inset;
        ud_rect(p,(UiRect){r.x+edge+1,r.y+yy,r.w-2*edge-2,1},c);
        unsigned alpha=(unsigned)((1-(inset-edge))*255);
        pixel(p,r.x+edge,r.y+yy,c,alpha);pixel(p,r.x+r.w-1-edge,r.y+yy,c,alpha);
    }
}
void ud_circle(uint32_t *p,float x,float y,float r,uint32_t c) {
    for(int yy=(int)floorf(y-r);yy<=(int)ceilf(y+r);++yy) {
        float dy=yy+0.5f-y;
        if(fabsf(dy)>=r)continue;
        float span=sqrtf(r*r-dy*dy),left=x-span,right=x+span;
        int a=(int)floorf(left),b=(int)floorf(right);
        if(b>a)ud_rect(p,(UiRect){a+1,yy,b-a-1,1},c);
        pixel(p,a,yy,c,(unsigned)((1-(left-a))*255));
        pixel(p,b,yy,c,(unsigned)((right-b)*255));
    }
}
void ud_line(uint32_t *p,float ax,float ay,float bx,float by,float width,uint32_t c) {
    float vx=bx-ax,vy=by-ay,length=vx*vx+vy*vy,r=width/2;
    int left=(int)floorf(fminf(ax,bx)-r-1),right=(int)ceilf(fmaxf(ax,bx)+r+1);
    int top=(int)floorf(fminf(ay,by)-r-1),bottom=(int)ceilf(fmaxf(ay,by)+r+1);
    for(int y=top;y<=bottom;++y)for(int x=left;x<=right;++x) {
        float px=x+0.5f-ax,py=y+0.5f-ay,t=length?(px*vx+py*vy)/length:0;
        if(t<0)t=0;
        if(t>1)t=1;
        float dx=px-t*vx,dy=py-t*vy,d=r+0.5f-sqrtf(dx*dx+dy*dy);
        if(d>0)pixel(p,x,y,c,d>=1?255:(unsigned)(d*255));
    }
}
static void tri(uint32_t *p,float ax,float ay,float bx,float by,float cx,float cy,uint32_t c) {
    float sign=(bx-ax)*(cy-ay)-(by-ay)*(cx-ax);
    int left=(int)floorf(fminf(ax,fminf(bx,cx))),right=(int)ceilf(fmaxf(ax,fmaxf(bx,cx)));
    int top=(int)floorf(fminf(ay,fminf(by,cy))),bottom=(int)ceilf(fmaxf(ay,fmaxf(by,cy)));
    for(int y=top;y<=bottom;++y)for(int x=left;x<=right;++x) {
        unsigned coverage=0;
        for(unsigned yy=0;yy<2;++yy)for(unsigned xx=0;xx<2;++xx) {
            float px=x+0.25f+xx*0.5f,py=y+0.25f+yy*0.5f;
            if(((bx-ax)*(py-ay)-(by-ay)*(px-ax))*sign>=0 &&
               ((cx-bx)*(py-by)-(cy-by)*(px-bx))*sign>=0 &&
               ((ax-cx)*(py-cy)-(ay-cy)*(px-cx))*sign>=0)++coverage;
        }
        if(coverage)pixel(p,x,y,c,coverage*255/4);
    }
}
static void arc(uint32_t *p,float cx,float cy,float r,float start,float end,float w,uint32_t c) {
    float x=cx+cosf(start)*r,y=cy+sinf(start)*r;
    for(unsigned i=1;i<=20;++i) {
        float a=start+(end-start)*i/20,xx=cx+cosf(a)*r,yy=cy+sinf(a)*r;
        ud_line(p,x,y,xx,yy,w,c);x=xx;y=yy;
    }
}
void ud_icon(uint32_t *p,int icon,int cx,int cy,float size,uint32_t c) {
    float k=size/32,w=2.2f*k;
#define L(a,b,d,e) ud_line(p,cx+(a)*k,cy+(b)*k,cx+(d)*k,cy+(e)*k,w,c)
#define T(a,b,d,e,f,g) tri(p,cx+(a)*k,cy+(b)*k,cx+(d)*k,cy+(e)*k,cx+(f)*k,cy+(g)*k,c)
    switch(icon) {
        case ICON_SEARCH:arc(p,cx-3*k,cy-3*k,9*k,0,6.2831853f,w,c);L(4,4,13,13);break;
        case ICON_PLAYER:ud_round(p,(UiRect){cx-(int)(12*k),cy-(int)(12*k),(int)(24*k),(int)(24*k)},(int)(5*k),c);
            tri(p,cx-3*k,cy-7*k,cx-3*k,cy+7*k,cx+7*k,cy,UI_RGB(0,0,0));break;
        case ICON_PLAY:T(-7,-12,-7,12,12,0);break;
        case ICON_PAUSE:
            ud_round(p,(UiRect){cx-(int)(9*k),cy-(int)(11*k),(int)(6*k),(int)(22*k)},(int)(1*k),c);
            ud_round(p,(UiRect){cx+(int)(3*k),cy-(int)(11*k),(int)(6*k),(int)(22*k)},(int)(1*k),c);break;
        case ICON_PREVIOUS:L(-11,-11,-11,11);T(9,-11,9,11,-7,0);break;
        case ICON_NEXT:L(11,-11,11,11);T(-9,-11,-9,11,7,0);break;
        case ICON_SHUFFLE:
            L(-14,-9,-9,-9);L(-9,-9,9,9);L(9,9,14,9);L(10,5,14,9);L(14,9,10,13);
            L(-14,9,-9,9);L(-9,9,-4,4);L(4,-4,9,-9);L(9,-9,14,-9);L(10,-13,14,-9);L(14,-9,10,-5);break;
        case ICON_REPEAT:
            L(-13,2,-13,-4);L(-13,-4,-9,-8);L(-9,-8,12,-8);L(8,-12,12,-8);L(12,-8,8,-4);
            L(13,-2,13,4);L(13,4,9,8);L(9,8,-12,8);L(-8,4,-12,8);L(-12,8,-8,12);break;
        case ICON_SPEAKER:
            T(-10,-5,-3,-5,-3,5);T(-10,-5,-10,5,-3,5);T(-3,-5,5,-12,5,12);T(-3,-5,-3,5,5,12);
            arc(p,cx+2*k,cy,11*k,-0.75f,0.75f,w,c);arc(p,cx+2*k,cy,16*k,-0.75f,0.75f,w,c);break;
        case ICON_GEAR:
            for(unsigned i=0;i<8;++i) { float a=(float)i*0.78539816f;
                ud_line(p,cx+cosf(a)*10*k,cy+sinf(a)*10*k,cx+cosf(a)*14*k,cy+sinf(a)*14*k,4*k,c); }
            arc(p,cx,cy,10*k,0,6.2831853f,2.6f*k,c);arc(p,cx,cy,3.6f*k,0,6.2831853f,2*k,c);break;
        case ICON_QUEUE:
            L(-13,-9,-9,-9);L(-4,-9,13,-9);L(-13,0,-9,0);L(-4,0,13,0);L(-13,9,-9,9);L(-4,9,13,9);break;
        case ICON_HEART: {
            /* Parametric heart outline, scaled to the same optical size as navigation icons. */
            float last_x=0,last_y=0;
            for(unsigned i=0;i<=64;++i) { float a=(float)i*6.2831853f/64,s=sinf(a);
                float x=13*s*s*s,y=-(10*cosf(a)-4*cosf(2*a)-2*cosf(3*a)-cosf(4*a));
                if(i) L(last_x,last_y,x,y);
                last_x=x;last_y=y;
            }break;
        }
        case ICON_MOON:
            arc(p,cx,cy,11*k,0.1f,4.6f,w,c);
            arc(p,cx+6*k,cy-5*k,10*k,1.5f,3.7f,w,c);break;
        case ICON_UP:L(-7,4,0,-3);L(0,-3,7,4);break;
        case ICON_DOWN:L(-7,-4,0,3);L(0,3,7,-4);break;
        case ICON_CHEVRON:L(-3,-7,4,0);L(4,0,-3,7);break;
        case ICON_BACK:L(4,-7,-3,0);L(-3,0,4,7);break;
        case ICON_LINK:
            arc(p,cx-4*k,cy+4*k,7*k,0.3f,5.1f,w,c);arc(p,cx+4*k,cy-4*k,7*k,3.4f,8.2f,w,c);L(-5,5,5,-5);break;
        case ICON_CHECK:L(-8,0,-2,6);L(-2,6,10,-7);break;
        default:L(-5,9,-5,-10);L(-5,-10,9,-13);L(9,-13,9,5);
            ud_circle(p,cx-9*k,cy+10*k,4*k,c);ud_circle(p,cx+5*k,cy+6*k,4*k,c);break;
    }
#undef L
#undef T
}
static unsigned next_code(const char **s) {
    const unsigned char *p=(const unsigned char *)*s;
    unsigned a=*p++;if(a<128) { *s=(const char *)p;return a; }
    unsigned count=a>=0xc2 && a<0xe0?1:a<0xf0 && a>=0xe0?2:a>=0xf0 && a<=0xf4?3:0;
    if(!count) { *s=(const char *)p;return '?'; }
    unsigned code=a&((1u<<(6-count))-1);
    for(unsigned i=0;i<count;++i) {
        if((p[i]&0xc0)!=0x80) { *s=(const char *)p;return '?'; }
        code=(code<<6)|(p[i]&63);
    }
    *s=(const char *)(p+count);return code;
}
static const UiFontGlyph *glyph(unsigned font,unsigned code) {
    if(font>UF_HERO)font=UF_BODY;
    unsigned at=code>=32 && code<256?code-32:'?'-32;
    for(unsigned i=0;i<9;++i)if(ui_font_extra[i]==code)at=224+i;
    return ui_font_glyphs+font*UI_FONT_GLYPHS+at;
}
int ud_width(unsigned font,const char *s) {
    int width=0;while(*s)width+=glyph(font,next_code(&s))->advance;return width;
}
static void draw_glyph(uint32_t *p,int x,int y,const UiFontGlyph *g,uint32_t c) {
    const uint8_t *alpha=ui_font_pixels+g->offset;
    for(unsigned yy=0;yy<g->height;++yy)for(unsigned xx=0;xx<g->width;++xx)
        pixel(p,x+g->left+(int)xx,y+g->top+(int)yy,c,alpha[yy*g->width+xx]);
}
void ud_text(uint32_t *p,int x,int y,unsigned font,uint32_t c,const char *s,int width) {
    if(width<=0)return;
    int at=0,ellipsis=ud_width(font,"…");
    int clipped=ud_width(font,s)>width;
    while(*s) {
        const UiFontGlyph *g=glyph(font,next_code(&s));
        if(at+g->advance>width-(clipped?ellipsis:0)) {
            if(clipped && at+ellipsis<=width)draw_glyph(p,x+at,y,glyph(font,0x2026),c);
            return;
        }
        draw_glyph(p,x+at,y,g,c);at+=g->advance;
    }
}
void ud_wrap(uint32_t *p,int x,int y,unsigned font,uint32_t c,const char *s,int width,unsigned lines,int spacing) {
    for(unsigned row=0;row<lines && *s;++row) {
        if(row==lines-1) { ud_text(p,x,y+(int)row*spacing,font,c,s,width);return; }
        const char *at=s,*last=s,*space=NULL;int used=0;
        while(*at) { const char *begin=at;const UiFontGlyph *g=glyph(font,next_code(&at));
            if(used+g->advance>width) { at=begin;break; }
            if(*begin==' ')space=begin;
            used+=g->advance;last=at;
        }
        if(!*at) { ud_text(p,x,y+(int)row*spacing,font,c,s,width);return; }
        const char *end=space && space>s?space:last;
        if(end<=s)return;
        char line[256];size_t n=(size_t)(end-s);if(n>=sizeof(line))n=sizeof(line)-1;
        memcpy(line,s,n);line[n]=0;ud_text(p,x,y+(int)row*spacing,font,c,line,width);
        s=end;while(*s==' ')++s;
    }
}
