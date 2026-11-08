#ifndef VPCM_PROTOCOL_H
#define VPCM_PROTOCOL_H
#include <stdint.h>
#include <stddef.h>
#define VPCM_RATE 48000
#define VPCM_FRAMES 1024
#define VPCM_BLOCK_BYTES (VPCM_FRAMES * 4)
#define VPCM_HEADER_BYTES 16
#define VPCM_REPLY_BYTES 8
#define VOPS_FRAMES 960
#define VOPS_PCM_BYTES (VOPS_FRAMES * 4)
#define VOPS_PACKET_MAX 1275
static inline void vpcm_reply(uint8_t *p, int ok, uint32_t code) {
    p[0]='V'; p[1]='P'; p[2]=ok ? 'O' : 'E'; p[3]=ok ? 'K' : 'R';
    p[4]=code; p[5]=code>>8; p[6]=code>>16; p[7]=code>>24;
}
static inline uint32_t vpcm_le32(const uint8_t *p) {
    return (uint32_t)p[0] | (uint32_t)p[1]<<8 | (uint32_t)p[2]<<16 | (uint32_t)p[3]<<24;
}
/* This status is sent only after paired TLS authentication, instead of audio. */
static inline unsigned vaer_code(const uint8_t *p,size_t n) {
    if(n!=16 || p[0]!='V' || p[1]!='A' || p[2]!='E' || p[3]!='R' ||
       vpcm_le32(p+8)!=1 || vpcm_le32(p+12)!=0)return 0;
    uint32_t code=vpcm_le32(p+4);return code>=1 && code<=8?code:0;
}
static inline const char *vaer_message(unsigned code) {
    switch(code) {
        case 1:return "Choose a virtual cable on the PC";
        case 2:return "Virtual cable device is missing";
        case 3:return "Soloist is not running on the PC";
        case 4:return "Soloist output is not the saved cable";
        case 5:return "Process capture needs Windows 11";
        case 6:return "Could not start Soloist audio capture";
        case 7:return "Soloist cable routing is not verified";
        case 8:return "Soloist build expired on the PC";
        default:return "Check audio setup on the PC";
    }
}
static inline int vpcm_header_valid(const uint8_t *p) {
    return p[0]=='V' && p[1]=='P' && p[2]=='C' && p[3]=='M' &&
        vpcm_le32(p+4)==VPCM_RATE && p[8]==2 && p[9]==0 &&
        p[10]==16 && p[11]==0 && vpcm_le32(p+12)==VPCM_FRAMES;
}
static inline int vops_header_valid(const uint8_t *p) {
    uint32_t bitrate=vpcm_le32(p+12);
    return p[0]=='V' && p[1]=='O' && p[2]=='P' && p[3]=='S' &&
        vpcm_le32(p+4)==VPCM_RATE && p[8]==2 && p[9]==0 &&
        p[10]==(VOPS_FRAMES&255) && p[11]==(VOPS_FRAMES>>8) &&
        bitrate>=96000 && bitrate<=320000 && bitrate%1000==0;
}
#endif
