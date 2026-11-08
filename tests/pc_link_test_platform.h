/* State/ownership tests only. These networking stubs are never executed. */
#ifndef PC_LINK_TEST_PLATFORM_H
#define PC_LINK_TEST_PLATFORM_H
#include <stdint.h>
#include <stddef.h>
typedef int SceUID;
typedef unsigned SceSize;
typedef struct { uint32_t s_addr; } SceNetInAddr;
typedef struct { unsigned char sin_len,sin_family;unsigned short sin_port;SceNetInAddr sin_addr; } SceNetSockaddrIn;
typedef SceNetSockaddrIn SceNetSockaddr;
typedef struct { unsigned events;union { int fd; } data; } SceNetEpollEvent;
#define SCE_CTRL_SELECT 1
#define SCE_CTRL_UP 16
#define SCE_CTRL_RIGHT 32
#define SCE_CTRL_DOWN 64
#define SCE_CTRL_LEFT 128
#define SCE_CTRL_LTRIGGER 256
#define SCE_CTRL_RTRIGGER 512
#define SCE_CTRL_TRIANGLE 4096
#define SCE_CTRL_CIRCLE 8192
#define SCE_CTRL_CROSS 16384
#define SCE_CTRL_SQUARE 32768
#define SCE_NET_AF_INET 2
#define SCE_NET_SOCK_STREAM 1
#define SCE_NET_SOCK_DGRAM 2
#define SCE_NET_SOL_SOCKET 1
#define SCE_NET_SO_NBIO 1
#define SCE_NET_SO_ERROR 2
#define SCE_NET_SO_BROADCAST 3
#define SCE_NET_EAGAIN 11
#define SCE_NET_EINTR 4
#define SCE_NET_EINPROGRESS 115
#define SCE_NET_EALREADY 114
#define SCE_NET_EPOLLOUT 4
#define SCE_NET_EPOLLERR 8
#define SCE_NET_EPOLLHUP 16
#define SCE_NET_EPOLL_CTL_ADD 1
#define SCE_NET_INADDR_ANY 0
#define SCE_NET_INADDR_BROADCAST 0xffffffffu
static int fake_ok() { return 0; }
static int fake_error() { return -1; }
static int fake_errno_value;
static int *sceNetErrnoLoc(void) { return &fake_errno_value; }
static uint64_t sceKernelGetProcessTimeWide(void) { return 0; }
#define sceNetHtonl(x) (x)
#define sceNetHtons(x) (x)
#define sceNetSocket fake_error
#define sceNetSocketClose fake_ok
#define sceNetSetsockopt fake_ok
#define sceNetGetsockopt fake_error
#define sceNetResolverCreate fake_error
#define sceNetResolverStartNtoa fake_error
#define sceNetResolverDestroy fake_ok
#define sceNetConnect fake_error
#define sceNetEpollCreate fake_error
#define sceNetEpollControl fake_error
#define sceNetEpollWait fake_error
#define sceNetEpollDestroy fake_ok
#define sceNetBind fake_error
#define sceNetSendto fake_error
#define sceNetRecvfrom fake_error
#define sceNetInetPton fake_error
static const char *sceNetInetNtop() { return NULL; }
#define sceKernelDelayThread fake_ok
#define sceKernelCreateMutex fake_ok
#define sceKernelDeleteMutex fake_ok
#define sceKernelLockMutex fake_ok
#define sceKernelTryLockMutex fake_ok
#define sceKernelUnlockMutex fake_ok
#define sceKernelCreateThread fake_ok
#define sceKernelStartThread fake_ok
#define sceKernelWaitThreadEnd fake_ok
#define sceKernelDeleteThread fake_ok
#endif
