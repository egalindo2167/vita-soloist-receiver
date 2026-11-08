#include "secure_net.h"
#include <mbedtls/ssl.h>
#include <mbedtls/md.h>
#include <mbedtls/platform_util.h>
#include <psa/crypto.h>
#include <psa/crypto_extra.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef SECURE_NET_HOST_TEST
#include <errno.h>
#include <pthread.h>
#include <sys/random.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>
static pthread_mutex_t lock=PTHREAD_MUTEX_INITIALIZER;
static int lock_ready=1;
static void enter(void) { pthread_mutex_lock(&lock); }
static void leave(void) { pthread_mutex_unlock(&lock); }
static uint64_t now_us(void) { struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (uint64_t)t.tv_sec*1000000+t.tv_nsec/1000; }
static void pause_io(void) { struct timespec t={0,5000000};nanosleep(&t,NULL); }
static void close_fd(int fd) { close(fd); }
static int send_fd(int fd,const void *p,size_t n) { return (int)send(fd,p,n,MSG_NOSIGNAL); }
static int recv_fd(int fd,void *p,size_t n) { return (int)recv(fd,p,n,0); }
static int again(void) { return errno==EAGAIN || errno==EWOULDBLOCK || errno==EINTR; }
static int os_random(void *p,size_t size) {
    unsigned char *out=p;
    while(size) { ssize_t n=getrandom(out,size,0);if(n<0 && errno==EINTR)continue;if(n<=0)return -1;out+=n;size-=(size_t)n; }
    return 0;
}
#else
#include <psp2/kernel/rng.h>
#include <psp2/kernel/processmgr.h>
#include <psp2/kernel/threadmgr.h>
#include <psp2/net/net.h>
static SceUID lock=-1;
static int lock_ready;
static void enter(void) { sceKernelLockMutex(lock,1,NULL); }
static void leave(void) { sceKernelUnlockMutex(lock,1); }
static uint64_t now_us(void) { return sceKernelGetProcessTimeWide(); }
static void pause_io(void) { sceKernelDelayThread(5000); }
static void close_fd(int fd) { sceNetSocketClose(fd); }
static int send_fd(int fd,const void *p,size_t n) { return sceNetSend(fd,p,n,0); }
static int recv_fd(int fd,void *p,size_t n) { return sceNetRecv(fd,p,n,0); }
static int again(void) { int e=*sceNetErrnoLoc();return e==SCE_NET_EAGAIN || e==SCE_NET_EINTR; }
static int os_random(void *p,size_t size) {
    unsigned char *out=p;
    while(size) { size_t n=size>64?64:size;if(sceKernelGetRandomNumber(out,n)<0)return -1;out+=n;size-=n; }
    return 0;
}
#endif

typedef struct { int fd,initialized,established,read_terminal;mbedtls_ssl_context ssl;mbedtls_ssl_config config; } Channel;
static Channel channels[2];
static unsigned char identity[16],psk[32],discovery[32],nonce[16],query_alias[16];
static int paired,last_error,nonce_valid;
static uint64_t nonce_time;
mbedtls_ms_time_t mbedtls_ms_time(void) { return (mbedtls_ms_time_t)(now_us()/1000); }

psa_status_t mbedtls_psa_external_get_random(mbedtls_psa_external_random_context_t *context,
    uint8_t *output,size_t size,size_t *written) {
    (void)context;*written=0;
    if(os_random(output,size)<0)return PSA_ERROR_INSUFFICIENT_ENTROPY;
    *written=size;return PSA_SUCCESS;
}
static int random_callback(void *context,unsigned char *data,size_t size) {
    (void)context;return os_random(data,size);
}
static int make_alias(const char *purpose,const unsigned char random[16],unsigned char out[16]) {
    unsigned char body[80],mac[32];
    int n=snprintf((char *)body,sizeof(body),"VitaAudioReceiver alias v2 %s",purpose);
    if(n<0 || (size_t)n+16>sizeof(body))return -1;
    memcpy(body+n,random,16);
    int rc=mbedtls_md_hmac(mbedtls_md_info_from_type(MBEDTLS_MD_SHA256),psk,32,body,(size_t)n+16,mac);
    if(!rc)memcpy(out,mac,16);
    mbedtls_platform_zeroize(mac,sizeof(mac));return rc;
}
static int tls_send(void *context,const unsigned char *data,size_t size) {
    Channel *c=context;int n=send_fd(c->fd,data,size);
    return n<0?(again()?MBEDTLS_ERR_SSL_WANT_WRITE:MBEDTLS_ERR_SSL_INTERNAL_ERROR):n;
}
static int tls_recv(void *context,unsigned char *data,size_t size) {
    Channel *c=context;int n=recv_fd(c->fd,data,size);
    return n<0?(again()?MBEDTLS_ERR_SSL_WANT_READ:MBEDTLS_ERR_SSL_INTERNAL_ERROR):n;
}
static int retry(int rc) { return rc==MBEDTLS_ERR_SSL_WANT_READ || rc==MBEDTLS_ERR_SSL_WANT_WRITE; }
static void drop(Channel *c,int close_socket) {
    if(c->initialized) { mbedtls_ssl_free(&c->ssl);mbedtls_ssl_config_free(&c->config); }
    if(close_socket && c->initialized && c->fd>=0)close_fd(c->fd);
    memset(c,0,sizeof(*c));c->fd=-1;
}
int secure_net_start(const char *path) {
    secure_net_stop();
    unsigned char data[57];FILE *f=fopen(path,"rb");
    if(!f)return -1;
    size_t n=fread(data,1,sizeof(data),f);int bad=ferror(f);fclose(f);
    if(bad || n!=56 || memcmp(data,"VASEC01\0",8)) { mbedtls_platform_zeroize(data,sizeof(data));return -1; }
#ifndef SECURE_NET_HOST_TEST
    if(!lock_ready) { lock=sceKernelCreateMutex("receiver-tls",0,0,NULL);if(lock<0) { mbedtls_platform_zeroize(data,sizeof(data));return -1; }lock_ready=1; }
#endif
    enter();
    for(unsigned i=0;i<2;++i) { memset(&channels[i],0,sizeof(channels[i]));channels[i].fd=-1; }
    memcpy(identity,data+8,16);memcpy(psk,data+24,32);mbedtls_platform_zeroize(data,sizeof(data));
    const unsigned char domain[]="VitaAudioReceiver discovery v1";
    int rc=mbedtls_md_hmac(mbedtls_md_info_from_type(MBEDTLS_MD_SHA256),psk,32,domain,sizeof(domain)-1,discovery);
    if(!rc && psa_crypto_init()!=PSA_SUCCESS)rc=-1;
    paired=rc==0;nonce_valid=0;last_error=rc;leave();return rc;
}
int secure_net_paired(void) { return paired; }
int secure_net_last_error(void) { return __atomic_load_n(&last_error,__ATOMIC_ACQUIRE); }
static Channel *find(int fd) {
    for(unsigned i=0;i<2;++i)if(channels[i].initialized && channels[i].fd==fd)return &channels[i];
    return NULL;
}
int secure_net_read(int fd,void *data,size_t size) {
    if(!paired || !lock_ready)return -1;
    enter();Channel *c=find(fd);int rc=-1;size_t total=0;
    if(c && c->established) {
        if(c->read_terminal)rc=c->read_terminal>0?0:-1;
        else for(unsigned i=0;i<16 && total<size;++i) {
            rc=mbedtls_ssl_read(&c->ssl,(unsigned char *)data+total,size-total);
            if(rc>0)total+=(size_t)rc;
            else if(retry(rc))break;
            else { c->read_terminal=rc==0 || rc==MBEDTLS_ERR_SSL_PEER_CLOSE_NOTIFY?1:-1;rc=c->read_terminal>0?0:-1;break; }
        }
    }
    leave();
    /* One TLS record may hold only 20 ms of Opus; collect available records so
     * the unchanged 1024-frame output loop can keep up with 960-frame packets. */
    return total?(int)total:retry(rc)?SECURE_NET_RETRY:rc<0?-1:rc;
}
int secure_net_write(int fd,const void *data,size_t size) {
    if(!paired || !lock_ready)return -1;
    enter();Channel *c=find(fd);int rc=c && c->established?mbedtls_ssl_write(&c->ssl,data,size):-1;leave();
    return retry(rc)?SECURE_NET_RETRY:rc<0?-1:rc;
}
int secure_net_handshake_host(int fd,int channel,const char *hostname,int (*keep_going)(void)) {
    if(!paired || channel<0 || channel>1)return -1;
    Channel *c=&channels[channel];int rc=-1;
    static const int suites[]={MBEDTLS_TLS1_3_CHACHA20_POLY1305_SHA256,MBEDTLS_TLS1_3_AES_128_GCM_SHA256,0};
    enter();
    if(c->initialized) { leave();return -1; }
    mbedtls_ssl_init(&c->ssl);mbedtls_ssl_config_init(&c->config);c->initialized=1;c->fd=fd;
    rc=mbedtls_ssl_config_defaults(&c->config,MBEDTLS_SSL_IS_CLIENT,MBEDTLS_SSL_TRANSPORT_STREAM,MBEDTLS_SSL_PRESET_DEFAULT);
    char name[69];unsigned char random[16],alias[16];
    if(!rc)rc=os_random(random,sizeof(random));
    if(!rc)rc=make_alias("tls",random,alias);
    if(!rc) {
        memcpy(name,"v2:",3);
        for(unsigned i=0;i<16;++i)snprintf(name+3+2*i,3,"%02x",random[i]);
        name[35]=':';
        for(unsigned i=0;i<16;++i)snprintf(name+36+2*i,3,"%02x",alias[i]);
        rc=mbedtls_ssl_conf_psk(&c->config,psk,32,(const unsigned char *)name,68);
    }
    if(!rc) {
        mbedtls_ssl_conf_min_tls_version(&c->config,MBEDTLS_SSL_VERSION_TLS1_3);
        mbedtls_ssl_conf_max_tls_version(&c->config,MBEDTLS_SSL_VERSION_TLS1_3);
        mbedtls_ssl_conf_tls13_key_exchange_modes(&c->config,MBEDTLS_SSL_TLS1_3_KEY_EXCHANGE_MODE_PSK_EPHEMERAL);
        mbedtls_ssl_conf_ciphersuites(&c->config,suites);
        mbedtls_ssl_conf_rng(&c->config,random_callback,NULL);
        rc=mbedtls_ssl_setup(&c->ssl,&c->config);
        if(!rc && hostname && hostname[0])rc=mbedtls_ssl_set_hostname(&c->ssl,hostname);
        if(!rc)mbedtls_ssl_set_bio(&c->ssl,c,tls_send,tls_recv,NULL);
    }
    leave();
    uint64_t deadline=now_us()+10000000ULL;
    if(!rc) {
        do {
            if((keep_going && !keep_going()) || now_us()>deadline) { rc=-1;break; }
            enter();rc=mbedtls_ssl_handshake(&c->ssl);leave();
            if(retry(rc))pause_io();
        } while(retry(rc));
    }
    if(!rc) {
        enter();c->established=1;leave();
        const char *role=channel?"VRC3":"VRA3";size_t sent=0,got=0;unsigned char reply[4];
        deadline=now_us()+2500000ULL;
        while(sent<4 && now_us()<deadline && (!keep_going || keep_going())) {
            int n=secure_net_write(fd,role+sent,4-sent);
            if(n>0)sent+=(size_t)n;else if(n==SECURE_NET_RETRY)pause_io();else break;
        }
        while(sent==4 && got<4 && now_us()<deadline && (!keep_going || keep_going())) {
            int n=secure_net_read(fd,reply+got,4-got);
            if(n>0)got+=(size_t)n;else if(n==SECURE_NET_RETRY)pause_io();else break;
        }
        if(got!=4 || memcmp(reply,"VSA1",4))rc=-1;
    }
    if(rc<0) { enter();drop(c,0);leave(); }
    __atomic_store_n(&last_error,rc,__ATOMIC_RELEASE);return rc;
}
int secure_net_handshake(int fd,int channel,int (*keep_going)(void)) {
    return secure_net_handshake_host(fd,channel,NULL,keep_going);
}
void secure_net_close(int fd) {
    if(!lock_ready)return;
    enter();Channel *c=find(fd);if(c)drop(c,1);leave();
}
void secure_net_stop(void) {
    if(!lock_ready)return;
    enter();for(unsigned i=0;i<2;++i)drop(&channels[i],1);
    paired=nonce_valid=0;mbedtls_platform_zeroize(psk,sizeof(psk));mbedtls_platform_zeroize(discovery,sizeof(discovery));
    mbedtls_platform_zeroize(identity,sizeof(identity));mbedtls_platform_zeroize(query_alias,sizeof(query_alias));
    mbedtls_psa_crypto_free();leave();
#ifndef SECURE_NET_HOST_TEST
    sceKernelDeleteMutex(lock);lock=-1;lock_ready=0;
#endif
}
int secure_net_query(uint8_t out[SECURE_DISCOVERY_QUERY]) {
    if(!paired)return -1;
    enter();nonce_valid=0;int rc=os_random(nonce,16);
    if(!rc) {
        rc=make_alias("discovery",nonce,query_alias);
        memcpy(out,"VAD2",4);memcpy(out+4,query_alias,16);memcpy(out+20,nonce,16);
        if(!rc)rc=mbedtls_md_hmac(mbedtls_md_info_from_type(MBEDTLS_MD_SHA256),discovery,32,out,36,out+36);
        nonce_valid=rc==0;nonce_time=now_us();
    }
    leave();return rc;
}
int secure_net_reply(const uint8_t *data,size_t size,unsigned *audio,unsigned *control,char name[32]) {
    if(!paired || size!=SECURE_DISCOVERY_REPLY)return 0;
    unsigned char mac[32];enter();int valid=0;
    if(nonce_valid && now_us()-nonce_time<=3000000ULL && !memcmp(data,"VAH2",4) &&
        !memcmp(data+4,query_alias,16) && !memcmp(data+20,nonce,16) &&
        !mbedtls_md_hmac(mbedtls_md_info_from_type(MBEDTLS_MD_SHA256),discovery,32,data,72,mac)) {
        volatile unsigned diff=0;for(unsigned i=0;i<32;++i)diff|=mac[i]^data[72+i];
        unsigned ap=data[36]|(unsigned)data[37]<<8,cp=data[38]|(unsigned)data[39]<<8;
        if(!diff && ap && cp) {
            *audio=ap;*control=cp;memcpy(name,data+40,32);name[31]=0;nonce_valid=0;valid=1;
        }
    }
    leave();return valid;
}
