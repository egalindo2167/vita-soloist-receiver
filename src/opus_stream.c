#include "opus_stream.h"
#include <opus.h>
#include <string.h>

void opus_stream_close(OpusStream *stream) {
    if (stream->decoder)opus_decoder_destroy((OpusDecoder *)stream->decoder);
    memset(stream,0,sizeof(*stream));
}
int opus_stream_open(OpusStream *stream) {
    opus_stream_close(stream);
    int error=0;stream->decoder=opus_decoder_create(VPCM_RATE,2,&error);
    return stream->decoder?0:(error<0?error:-1);
}
int opus_stream_partial(const OpusStream *stream) {
    return stream->have_length!=0 || stream->have_packet!=0;
}
int opus_stream_feed(OpusStream *stream,const uint8_t *input,size_t size,
                     uint8_t *output,size_t capacity,size_t *consumed,size_t *written) {
    *consumed=*written=0;
    if (!stream->decoder)return -1;
    while (*consumed<size && capacity-*written>=VOPS_PCM_BYTES) {
        if (stream->have_length<2) {
            stream->length[stream->have_length++]=input[(*consumed)++];
            if (stream->have_length<2)continue;
            stream->packet_size=stream->length[0]|(size_t)stream->length[1]<<8;
            if (!stream->packet_size || stream->packet_size>VOPS_PACKET_MAX)return -2;
        }
        size_t available=size-*consumed;
        size_t need=stream->packet_size-stream->have_packet;
        if (available>need)available=need;
        memcpy(stream->packet+stream->have_packet,input+*consumed,available);
        stream->have_packet+=available;*consumed+=available;
        if (stream->have_packet<stream->packet_size)continue;
        if (opus_packet_get_nb_samples(stream->packet,(opus_int32)stream->packet_size,VPCM_RATE)!=VOPS_FRAMES)return -3;
        int frames=opus_decode((OpusDecoder *)stream->decoder,stream->packet,
            (opus_int32)stream->packet_size,stream->decoded,VOPS_FRAMES,0);
        if (frames!=VOPS_FRAMES)return -4;
        /* CBR 20 ms frames: packet bytes * 8 * 50. Opus carries its own
         * decoding parameters; bitrate changes need no decoder reset. */
        stream->last_bitrate=(unsigned)stream->packet_size*400;
        memcpy(output+*written,stream->decoded,VOPS_PCM_BYTES);*written+=VOPS_PCM_BYTES;
        stream->have_length=stream->have_packet=stream->packet_size=0;
    }
    return 0;
}
