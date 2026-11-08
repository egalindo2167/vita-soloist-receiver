#include "control.h"
#include <string.h>
uint32_t ctl_read32(const uint8_t *p) {
    return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);
}
void ctl_write32(uint8_t *p, uint32_t n) {
    for (unsigned i=0;i<4;++i) p[i]=(uint8_t)(n>>(8*i));
}
int ctl_frame_valid(const uint8_t *tag, uint32_t n) {
    if (!memcmp(tag,"STAT",4)) return n==CTL_STATE_BYTES;
    if (!memcmp(tag,"AFLU",4)) return n==8;
    if (!memcmp(tag,"QJMP",4)) return n==8;
    if (!memcmp(tag,"QPAG",4)) return n>=156 && n<=156+5*388 && (n-156)%388==0;
    if (!memcmp(tag,"ARTW",4)) return n==CTL_ART_BYTES+4;
    if (!memcmp(tag,"ARTC",4)) return n>=10 && n<=4104 && (n-8)%2==0;
    if (!memcmp(tag,"QUEU",4)||!memcmp(tag,"FAVS",4))
        return n>=4 && n<=4+CTL_ITEMS*CTL_ITEM_BYTES && (n-4)%CTL_ITEM_BYTES==0;
    return 0;
}
static void field(char *out, const uint8_t **p, size_t n) {
    memcpy(out,*p,n); out[n-1]=0; *p+=n;
}
int ctl_apply(SpotifyView *v, const uint8_t *tag, const uint8_t *p, size_t n) {
    if (n>CTL_MAX_PAYLOAD || !ctl_frame_valid(tag,(uint32_t)n)) return 0;
    if (!memcmp(tag,"QJMP",4)) {
        unsigned done=ctl_read32(p),total=ctl_read32(p+4);
        if(total>256 || done>total)return 0;
        v->jump_done=done;v->jump_total=total;
    } else if(!memcmp(tag,"QPAG",4)) {
        unsigned id=ctl_read32(p),revision=ctl_read32(p+4),offset=ctl_read32(p+8),total=ctl_read32(p+12);
        unsigned available=ctl_read32(p+16),flags=ctl_read32(p+20),count=ctl_read32(p+24);
        if(id>0x7fffffffu || total>available || available>10000 || flags>3 || offset>total || offset%5 ||
           count>5 || count>total-offset || count!=(total-offset>5?5:total-offset) || n!=156+count*388 || p[155])return 0;
        for(unsigned i=0;i<count;++i) {
            unsigned position=ctl_read32(p+156+i*388);
            if(!position || position>available || (i && position<=ctl_read32(p+156+(i-1)*388)))return 0;
        }
        /* A response from the previous query/page must never restore stale rows
         * or make an old selection playable while a newer request is pending. */
        if(id!=v->queue_request_id)return 1;
        if(v->queue_loading && offset!=v->queue_wanted_offset &&
           !(v->queue_wanted_offset>=total && offset==(total?((total-1)/5)*5:0)))return 1;
        if(v->queue_paged && (int32_t)(revision-v->queue_revision)<0)return 1;
        int changed=v->queue_offset!=offset;
        v->queue_paged=1;v->queue_revision=revision;v->queue_offset=offset;v->queue_total=total;
        v->queue_available=available;v->queue_flags=flags;v->queue_loading=0;
        const uint8_t *query=p+28;field(v->queue_query,&query,128);p+=156;
        for(unsigned i=0;i<count;++i) {
            v->queue[i].position=ctl_read32(p);p+=4;
            field(v->queue[i].title,&p,128);field(v->queue[i].artist,&p,128);field(v->queue[i].uri,&p,128);
        }
        v->queue_count=count;
        if(!v->tab && (changed || v->queue_select_last))v->selected=v->queue_select_last && count?count-1:0;
        v->queue_select_last=0;
        if(!v->tab && v->selected>=count)v->selected=count?count-1:0;
    } else if (!memcmp(tag,"AFLU",4)) {
        uint32_t id=ctl_read32(p),hold=ctl_read32(p+4);
        if(!id || hold>1)return 0;
        v->audio_flush_id=id;v->audio_flush_hold=hold;
    } else if (!memcmp(tag,"STAT",4)) {
        uint32_t x[11]; for (unsigned i=0;i<11;++i) x[i]=ctl_read32(p+4*i);
        if (x[0]!=1 || x[1]>1 || x[2]>1 || x[3]>1 || x[4]>3 || x[5]>100 ||
            x[6]>1 || x[7]>2) return 0;
        v->api_online=x[1]; v->logged_in=x[2]; v->active=x[3]; v->status=x[4];
        v->volume=x[5]; v->shuffle=x[6]; v->repeat=x[7];
        v->position_ms=x[8]; v->duration_ms=x[9];
        if (v->art_id!=x[10]) { v->has_art=0; v->art_received=0; }
        v->art_id=x[10]; p+=44;
        field(v->title,&p,192); field(v->artist,&p,192); field(v->album,&p,192);
        field(v->uri,&p,128); field(v->message,&p,160); v->online=1;
    } else if (!memcmp(tag,"ARTC",4)) {
        uint32_t id=ctl_read32(p),offset=ctl_read32(p+4);size_t bytes=n-8;
        if (id!=v->art_id) return 1;
        if (offset>CTL_ART_BYTES || bytes>CTL_ART_BYTES-offset || offset%2) return 0;
        if (!offset) { v->art_received=0; v->has_art=0; }
        if (offset!=v->art_received) return 0;
        for (unsigned i=0;i<bytes/2;++i)
            v->art[offset/2+i]=(uint16_t)p[8+2*i]|((uint16_t)p[9+2*i]<<8);
        v->art_received+=(uint32_t)bytes;
        if (v->art_received<CTL_ART_BYTES) return 1;
        v->has_art=1;
    } else if (!memcmp(tag,"ARTW",4)) {
        if (ctl_read32(p)!=v->art_id) return 1; /* Ignore artwork for a skipped track. */
        for (unsigned i=0;i<CTL_ART_EDGE*CTL_ART_EDGE;++i)
            v->art[i]=(uint16_t)p[4+2*i]|((uint16_t)p[5+2*i]<<8);
        v->has_art=1;v->art_received=CTL_ART_BYTES;
    } else {
        uint32_t count=ctl_read32(p); p+=4;
        if (count>CTL_ITEMS || n!=4+count*CTL_ITEM_BYTES) return 0;
        int favorites=!memcmp(tag,"FAVS",4);
        if(!favorites && v->queue_paged)return 1;
        ControlItem *items=favorites ? v->favorites : v->queue;
        for (unsigned i=0;i<count;++i) {
            field(items[i].title,&p,128); field(items[i].artist,&p,128); field(items[i].uri,&p,128);
            items[i].position=i+1;
        }
        if (favorites) v->favorite_count=count; else v->queue_count=count;
        unsigned visible=v->tab ? v->favorite_count : v->queue_count;
        if (v->selected>=visible) v->selected=visible ? visible-1 : 0;
    }
    ++v->generation;
    return 1;
}
