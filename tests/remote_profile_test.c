#include "../src/remote_profile.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static const char good[]="VART1\naudio_host=0.tcp.ngrok.io\naudio_port=12345\ncontrol_host=1.tcp.eu.ngrok.io\ncontrol_port=54321\n";
int main(void) {
    RemoteProfile profile={0};
    assert(remote_profile_parse(good,sizeof(good)-1,&profile));
    assert(!strcmp(profile.audio_host,"0.tcp.ngrok.io") && profile.audio_port==12345);
    assert(!strcmp(profile.control_host,"1.tcp.eu.ngrok.io") && profile.control_port==54321);
    const char *valid[]={"localhost","127.0.0.1","1.tcp.eu.ngrok.io","host-name.example","a"};
    for(unsigned i=0;i<sizeof(valid)/sizeof(*valid);++i)assert(remote_host_valid(valid[i]));
    const char *bad[]={"","0.0.0.0","255.255.255.255","256.0.1.1","127.1","0127.0.0.1","a..b","a.","-a","a-","https://a", "a:443","a/b","a b","a\nb","[::1]","é.example"};
    for(unsigned i=0;i<sizeof(bad)/sizeof(*bad);++i)assert(!remote_host_valid(bad[i]));
    char oversized[REMOTE_PROFILE_MAX+1];memset(oversized,'a',sizeof(oversized));
    assert(!remote_profile_parse(oversized,sizeof(oversized),&profile));
    char host[255];memset(host,'a',64);host[64]=0;assert(!remote_host_valid(host));
    const char *invalid[]={"VART2\n", "VART1\naudio_port=0\n", "VART1\naudio_port=65536\n", "VART1\naudio_port=9999999999999999999\n", "VART1\naudio_port=-1\n", "VART1\naudio_port=3x\n", "VART1\nunknown=secret\n"};
    RemoteProfile saved=profile;
    for(unsigned i=0;i<sizeof(invalid)/sizeof(*invalid);++i) {
        assert(!remote_profile_parse(invalid[i],strlen(invalid[i]),&profile));
        assert(!memcmp(&saved,&profile,sizeof(profile)));
    }
    for(size_t n=0;n<sizeof(good)-2;++n) {
        /* The final port may itself be valid when shorter, so truncate only
         * before the last field is present. */
        if(n<(size_t)(strstr(good,"control_port=")-good)+13)
            assert(!remote_profile_parse(good,n,&profile));
    }
    char extra[sizeof(good)+80];snprintf(extra,sizeof(extra),"%saudio_port=9\n",good);
    assert(!remote_profile_parse(extra,strlen(extra),&profile));
    snprintf(extra,sizeof(extra),"%s\nunknown=secret\n",good);
    assert(!remote_profile_parse(extra,strlen(extra),&profile));
    memcpy(extra,good,sizeof(good));extra[20]=0;
    assert(!remote_profile_parse(extra,sizeof(good)-1,&profile));
    puts("Remote profile: bounds, hosts, ports, duplicate/unknown fields, truncation and fail-closed updates passed.");
    return 0;
}
