#ifndef RECEIVER_OPUS_STREAM_H
#define RECEIVER_OPUS_STREAM_H
#include "protocol.h"

typedef struct {
    void *decoder;
    uint8_t length[2],packet[VOPS_PACKET_MAX];
    size_t have_length,have_packet,packet_size;
    unsigned last_bitrate;
    int16_t decoded[VOPS_FRAMES*2];
} OpusStream;
int opus_stream_open(OpusStream *stream);
void opus_stream_close(OpusStream *stream);
/* Incremental TCP framing with bounded output and backpressure. A frame is
 * decoded only when one complete PCM frame fits. No input is lost on a short
 * read or when the PCM queue is full. Output is stereo 48 kHz signed 16-bit. */
int opus_stream_feed(OpusStream *stream,const uint8_t *input,size_t size,
                     uint8_t *output,size_t capacity,size_t *consumed,size_t *written);
int opus_stream_partial(const OpusStream *stream);
#endif
