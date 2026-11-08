#ifndef UI_TEST_PLATFORM_H
#define UI_TEST_PLATFORM_H
#include <stdint.h>
#include <stddef.h>
typedef int SceUID;
typedef unsigned SceSize;
typedef struct {
    SceSize size;
    void *base;
    unsigned pitch, pixelformat, width, height;
} SceDisplayFrameBuf;
typedef struct { char ip_address[32]; } SceNetCtlInfo;
#define SCE_DISPLAY_PIXELFORMAT_A8B8G8R8 0
#define SCE_DISPLAY_SETBUF_IMMEDIATE 0
#define SCE_DISPLAY_SETBUF_NEXTFRAME 1
#define SCE_KERNEL_THREAD_CPU_AFFINITY_MASK_DEFAULT 0
#define SCE_KERNEL_MEMBLOCK_TYPE_USER_CDRAM_RW 1
#define SCE_NETCTL_INFO_GET_IP_ADDRESS 1
int sceDisplaySetFrameBuf(const SceDisplayFrameBuf *, int);
int sceDisplayWaitSetFrameBuf(void);
int scePowerRequestDisplayOff(void);
int scePowerRequestDisplayOn(void);
int sceKernelLockMutex(SceUID, int, unsigned *);
int sceKernelTryLockMutex(SceUID, int);
int sceKernelUnlockMutex(SceUID, int);
uint64_t sceKernelGetProcessTimeWide(void);
int sceNetCtlInetGetInfo(int, SceNetCtlInfo *);
int sceKernelDelayThread(unsigned);
SceUID sceKernelCreateMutex(const char *, unsigned, int, void *);
SceUID sceKernelAllocMemBlock(const char *, int, SceSize, void *);
int sceKernelGetMemBlockBase(SceUID, void **);
SceUID sceKernelCreateThread(const char *, int (*)(SceSize,void *), int,
                             SceSize, unsigned, int, const void *);
int sceKernelStartThread(SceUID, SceSize, void *);
int sceKernelDeleteThread(SceUID);
int sceKernelFreeMemBlock(SceUID);
int sceKernelDeleteMutex(SceUID);
int sceKernelWaitThreadEnd(SceUID, int *, unsigned *);
#endif
