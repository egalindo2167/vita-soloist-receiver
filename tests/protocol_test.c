#include <assert.h>
#include <string.h>
#include "../src/protocol.h"
int main(void) {
    uint8_t h[16] = {'V','P','C','M',0x80,0xbb,0,0,2,0,16,0,0,4,0,0};
    assert(vpcm_header_valid(h));
    for (int i=0;i<16;i++) { h[i]^=1; assert(!vpcm_header_valid(h)); h[i]^=1; }
    h[4]=0x44; h[5]=0xac; /* 0.1 used an invalid MAIN rate; reject it. */
    assert(!vpcm_header_valid(h));
    uint8_t o[16]={'V','O','P','S',0x80,0xbb,0,0,2,0,0xc0,3,0,0xe2,4,0};
    assert(vops_header_valid(o) && !vpcm_header_valid(o));
    for(int i=0;i<12;++i) { o[i]^=1;assert(!vops_header_valid(o));o[i]^=1; }
    o[12]=o[13]=o[14]=o[15]=0;assert(!vops_header_valid(o));
    uint8_t reply[8]; vpcm_reply(reply,1,VPCM_RATE);
    assert(!memcmp(reply,"VPOK",4)); assert(vpcm_le32(reply+4)==48000);
    vpcm_reply(reply,0,0x80260003u);
    assert(!memcmp(reply,"VPER",4)); assert(vpcm_le32(reply+4)==0x80260003u);
    uint8_t error[16]={'V','A','E','R',2,0,0,0,1,0,0,0,0,0,0,0};
    assert(vaer_code(error,16)==2);
    for(unsigned n=0;n<16;++n)assert(!vaer_code(error,n));
    for(unsigned code=1;code<=8;++code) { error[4]=code;assert(vaer_code(error,16)==code);assert(strlen(vaer_message(code))<52); }
    error[4]=9;assert(!vaer_code(error,16));error[4]=0;assert(!vaer_code(error,16));error[4]=2;
    for(unsigned i=0;i<16;++i) {
        if(i==4)continue;
        error[i]^=1;assert(!vaer_code(error,16));error[i]^=1;
    }
    assert(!vpcm_header_valid(error) && !vops_header_valid(error));
    return 0;
}
