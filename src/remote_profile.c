#include "remote_profile.h"
#include <string.h>
#include <stdlib.h>
static int alnum_ascii(char c) {
    return (c>='a' && c<='z') || (c>='A' && c<='Z') || (c>='0' && c<='9');
}
int remote_host_valid(const char *host) {
    size_t n=strlen(host),label=0;int numeric=1;
    if(!n || n>REMOTE_HOST_MAX)return 0;
    for(size_t i=0;i<n;++i) {
        char c=host[i];
        if(c=='.') {
            if(!label || label>63 || !alnum_ascii(host[i-1]))return 0;
            label=0;
        } else {
            if(!alnum_ascii(c) && c!='-')return 0;
            if(!label && !alnum_ascii(c))return 0;
            if(c<'0' || c>'9')numeric=0;
            ++label;
        }
    }
    if(!label || label>63 || !alnum_ascii(host[n-1]))return 0;
    if(numeric) {
        const char *p=host;unsigned octets[4];
        for(unsigned i=0;i<4;++i) {
            char *end;unsigned long value=strtoul(p,&end,10);
            if(end==p || value>255 || (end-p>1 && *p=='0'))return 0;
            octets[i]=(unsigned)value;
            if(i<3) { if(*end!='.')return 0;p=end+1; }
            else if(*end)return 0;
        }
        if(!(octets[0]|octets[1]|octets[2]|octets[3]) ||
            (octets[0]==255 && octets[1]==255 && octets[2]==255 && octets[3]==255))return 0;
    }
    return 1;
}
static int port(const char *s,unsigned *out) {
    unsigned value=0;if(!*s)return 0;
    for(;*s;++s) { if(*s<'0' || *s>'9')return 0;value=value*10+(unsigned)(*s-'0');if(value>65535)return 0; }
    if(!value)return 0;
    *out=value;return 1;
}
int remote_profile_parse(const char *data,size_t size,RemoteProfile *out) {
    if(!size || size>REMOTE_PROFILE_MAX || memchr(data,0,size))return 0;
    char buffer[REMOTE_PROFILE_MAX+1];memcpy(buffer,data,size);buffer[size]=0;
    RemoteProfile result={0};unsigned seen=0,lines=0;char *line=buffer;
    while(line) {
        char *next=strchr(line,'\n');if(next)*next++=0;
        size_t n=strlen(line);if(n && line[n-1]=='\r')line[--n]=0;
        if(!n) { if(!next)break;return 0; }
        if(!lines++) { if(strcmp(line,"VART1"))return 0; }
        else {
            const char *value;unsigned bit;
            if(!strncmp(line,"audio_host=",11)) { value=line+11;bit=1;if(!remote_host_valid(value))return 0;strcpy(result.audio_host,value); }
            else if(!strncmp(line,"audio_port=",11)) { bit=2;if(!port(line+11,&result.audio_port))return 0; }
            else if(!strncmp(line,"control_host=",13)) { value=line+13;bit=4;if(!remote_host_valid(value))return 0;strcpy(result.control_host,value); }
            else if(!strncmp(line,"control_port=",13)) { bit=8;if(!port(line+13,&result.control_port))return 0; }
            else return 0;
            if(seen&bit)return 0;
            seen|=bit;
        }
        line=next;
    }
    if(seen!=15)return 0;
    *out=result;return 1;
}
