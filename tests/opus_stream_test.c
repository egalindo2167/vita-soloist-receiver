#include "../src/opus_stream.h"
#include <opus.h>
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static int decode_stdio(void) {
    OpusStream stream={0};uint8_t input[163],output[VOPS_PCM_BYTES];
    if(opus_stream_open(&stream)<0)return 2;
    size_t count;
    while((count=fread(input,1,sizeof(input),stdin))>0) {
        size_t at=0;
        while(at<count) {
            size_t consumed=0,written=0;
            if(opus_stream_feed(&stream,input+at,count-at,output,sizeof(output),&consumed,&written)<0 || !consumed) {
                opus_stream_close(&stream);return 2;
            }
            at+=consumed;
            if(written && fwrite(output,1,written,stdout)!=written) { opus_stream_close(&stream);return 2; }
        }
    }
    int partial=opus_stream_partial(&stream);opus_stream_close(&stream);
    return partial?2:0;
}
int main(int argc,char **argv) {
    if(argc==2 && !strcmp(argv[1],"--decode"))return decode_stdio();
    int error=0;OpusEncoder *encoder=opus_encoder_create(48000,2,OPUS_APPLICATION_AUDIO,&error);
    assert(encoder && !error);assert(opus_encoder_ctl(encoder,OPUS_SET_BITRATE(320000))==0);
    assert(opus_encoder_ctl(encoder,OPUS_SET_VBR(0))==0);
    int16_t pcm[VOPS_FRAMES*2];uint8_t packet[VOPS_PACKET_MAX],wire[8020];
    size_t wire_size=0;
    for(unsigned frame=0;frame<10;++frame) {
        for(unsigned i=0;i<VOPS_FRAMES;++i) {
            unsigned t=frame*VOPS_FRAMES+i;
            pcm[2*i]=(int16_t)(7000*sin(t*6.28318530718*440/48000));
            pcm[2*i+1]=(int16_t)(7000*sin(t*6.28318530718*997/48000));
        }
        int n=opus_encode(encoder,pcm,VOPS_FRAMES,packet,sizeof(packet));assert(n==800);
        wire[wire_size++]=(uint8_t)n;wire[wire_size++]=(uint8_t)(n>>8);
        memcpy(wire+wire_size,packet,(size_t)n);wire_size+=(size_t)n;
    }
    OpusStream stream={0};assert(opus_stream_open(&stream)==0);
    uint8_t guarded[10*VOPS_PCM_BYTES+2];memset(guarded,0x7b,sizeof(guarded));
    size_t consumed=9,written=9;
    assert(!opus_stream_feed(&stream,wire,wire_size,guarded+1,VOPS_PCM_BYTES-1,&consumed,&written));
    assert(!consumed && !written); /* full-frame output space is required */
    size_t input_at=0,output_at=0;
    while(input_at<wire_size) {
        size_t n=wire_size-input_at;if(n>7)n=7;
        assert(!opus_stream_feed(&stream,wire+input_at,n,guarded+1+output_at,
            10*VOPS_PCM_BYTES-output_at,&consumed,&written));
        assert(consumed==n);input_at+=consumed;output_at+=written;
    }
    assert(output_at==10*VOPS_PCM_BYTES && !opus_stream_partial(&stream));
    assert(guarded[0]==0x7b && guarded[sizeof(guarded)-1]==0x7b);
    /* Compare the entire decoded stream with a direct native Opus decoder. */
    OpusDecoder *reference=opus_decoder_create(48000,2,&error);assert(reference);
    int16_t decoded[VOPS_FRAMES*2];
    for(unsigned i=0;i<10;++i) {
        assert(opus_decode(reference,wire+i*802+2,800,decoded,VOPS_FRAMES,0)==VOPS_FRAMES);
        assert(!memcmp(guarded+1+i*VOPS_PCM_BYTES,decoded,VOPS_PCM_BYTES));
    }
    opus_decoder_destroy(reference);
    /* Coalesced TCP packets must obey queue capacity without losing bytes. */
    assert(opus_stream_open(&stream)==0);
    assert(!opus_stream_feed(&stream,wire,1604,guarded+1,VOPS_PCM_BYTES,&consumed,&written));
    assert(consumed==802 && written==VOPS_PCM_BYTES);
    assert(!opus_stream_feed(&stream,wire+consumed,802,guarded+1,VOPS_PCM_BYTES,&consumed,&written));
    assert(consumed==802 && written==VOPS_PCM_BYTES);
    /* Reject oversized/zero lengths and a valid but unsupported 10 ms frame. */
    const uint8_t bad[][2]={{0,0},{0xfc,4},{0xff,0xff}};
    for(unsigned i=0;i<3;++i) {
        assert(opus_stream_open(&stream)==0);
        assert(opus_stream_feed(&stream,bad[i],2,guarded+1,VOPS_PCM_BYTES,&consumed,&written)<0);
    }
    int n=opus_encode(encoder,pcm,480,packet,sizeof(packet));assert(n>0);
    wire[0]=(uint8_t)n;wire[1]=(uint8_t)(n>>8);memcpy(wire+2,packet,(size_t)n);
    assert(opus_stream_open(&stream)==0);
    assert(opus_stream_feed(&stream,wire,(size_t)n+2,guarded+1,VOPS_PCM_BYTES,&consumed,&written)<0);
    assert(opus_stream_open(&stream)==0);
    assert(!opus_stream_feed(&stream,wire,1,guarded+1,VOPS_PCM_BYTES,&consumed,&written));
    assert(opus_stream_partial(&stream));
    opus_stream_close(&stream);opus_stream_close(&stream);opus_encoder_destroy(encoder);
    puts("Opus stream: real stereo decoding, fragmented/coalesced framing, queue backpressure, invalid lengths/durations and cleanup passed.");
    return 0;
}
