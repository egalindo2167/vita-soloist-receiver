#ifndef RECEIVER_SECURE_NET_H
#define RECEIVER_SECURE_NET_H
#include <stddef.h>
#include <stdint.h>
#define SECURE_NET_RETRY (-2)
#define SECURE_DISCOVERY_QUERY 68
#define SECURE_DISCOVERY_REPLY 104
int secure_net_start(const char *pairing_path);
int secure_net_paired(void);
/* Adopts a nonblocking socket only on success. channel 0=audio, 1=control.
 * keep_going is polled during handshake; it must return nonzero to continue. */
int secure_net_handshake(int fd,int channel,int (*keep_going)(void));
/* Optional DNS name is sent as SNI for TLS-routing relays. Authentication still
 * requires the paired PSK; this never enables certificate or plaintext modes. */
int secure_net_handshake_host(int fd,int channel,const char *hostname,int (*keep_going)(void));
int secure_net_read(int fd,void *data,size_t size);
int secure_net_write(int fd,const void *data,size_t size);
void secure_net_close(int fd);
void secure_net_stop(void);
int secure_net_last_error(void);
int secure_net_query(uint8_t out[SECURE_DISCOVERY_QUERY]);
/* Returns 1 only for a valid, fresh paired-host response; otherwise 0. */
int secure_net_reply(const uint8_t *data,size_t size,unsigned *audio,unsigned *control,char name[32]);
#endif
