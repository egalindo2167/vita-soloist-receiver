#ifndef RECEIVER_REMOTE_PROFILE_H
#define RECEIVER_REMOTE_PROFILE_H
#include <stddef.h>
#define REMOTE_HOST_MAX 253
#define REMOTE_PROFILE_MAX 768
typedef struct {
    char audio_host[REMOTE_HOST_MAX+1],control_host[REMOTE_HOST_MAX+1];
    unsigned audio_port,control_port;
} RemoteProfile;
int remote_host_valid(const char *host);
/* Exact public configuration format. No tokens or pairing secrets belong here. */
int remote_profile_parse(const char *data,size_t size,RemoteProfile *out);
#endif
