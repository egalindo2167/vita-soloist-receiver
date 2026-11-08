/* Run the real UI startup against a constrained OS stub. The old unsupported
 * priority must fail this test; partial initialization must release resources.
 * This does not emulate rendering threads or replace a physical Vita check. */
#include "ui_test_platform.h"
#include "../src/ui.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum { OK, SECOND_ALLOCATION, SECOND_MAPPING, PRESENT, CREATE_THREAD, START_THREAD };
static int fault, allocations, frees, mutex_live, thread_live, started, priority;
static int off_calls,on_calls;
static int (*ui_entry)(SceSize,void *);
static int exercise_screen,screen_stage,flips,off_flips,off_error;
static void *memory[2], *displayed;
#define FAILURE ((int)0x80028023u)
int control_snapshot(SpotifyView *view) { (void)view; return 0; }
void pc_link_snapshot(PcLinkView *view) { (void)view; }

int sceDisplaySetFrameBuf(const SceDisplayFrameBuf *fb, int sync) {
    (void)sync;
    if (fb && fault==PRESENT) return FAILURE;
    displayed=fb ? fb->base : NULL;
    if (fb)++flips;
    return 0;
}
int sceDisplayWaitSetFrameBuf(void) { return 0; }
int scePowerRequestDisplayOff(void) {
    assert(displayed);
    const uint32_t *frame=displayed;
    for(unsigned i=0;i<UI_WIDTH*UI_HEIGHT;++i)assert(frame[i]==0xff000000);
    ++off_calls;off_flips=flips;return off_error?FAILURE:0;
}
int scePowerRequestDisplayOn(void) { ++on_calls;return 0; }
int sceKernelLockMutex(SceUID id, int count, unsigned *timeout) {
    (void)id; (void)count; (void)timeout; assert(mutex_live); return 0;
}
int sceKernelTryLockMutex(SceUID id, int count) {
    return sceKernelLockMutex(id,count,NULL);
}
int sceKernelUnlockMutex(SceUID id, int count) { (void)id; (void)count; return 0; }
uint64_t sceKernelGetProcessTimeWide(void) { return 1000000; }
int sceNetCtlInetGetInfo(int kind, SceNetCtlInfo *info) { (void)kind; (void)info; return -1; }
int sceKernelDelayThread(unsigned n) {
    (void)n;
    if (exercise_screen) {
        ReceiverUiState state={0};
        switch(screen_stage++) {
            case 0:state.screen_mode=SCREEN_BLACK;ui_publish(&state);break;
            case 1:
                assert(off_calls==1 && flips==off_flips);
                state.screen_mode=SCREEN_BLACK;state.played_seconds=99;ui_publish(&state);break;
            case 2:
                assert(flips==off_flips && off_calls==1); /* metadata cannot redraw a blank screen */
                state.screen_mode=SCREEN_ACTIVE;ui_publish(&state);break;
            case 3:
                assert(on_calls>=1 && flips>off_flips);
                fault=PRESENT;state.screen_mode=SCREEN_DIM;ui_publish(&state);break;
            default:assert(!"UI did not leave the test loop");
        }
    }
    return 0;
}
SceUID sceKernelCreateMutex(const char *name, unsigned attr, int n, void *opt) {
    (void)name; (void)attr; (void)n; (void)opt;
    assert(!mutex_live); mutex_live=1; return 10;
}
SceUID sceKernelAllocMemBlock(const char *name, int kind, SceSize size, void *opt) {
    (void)name; (void)kind; (void)opt;
    if (allocations==1 && fault==SECOND_ALLOCATION) return FAILURE;
    int i=allocations++;
    assert(i<2 && !memory[i]); memory[i]=calloc(1,size); assert(memory[i]);
    return 100+i;
}
int sceKernelGetMemBlockBase(SceUID id, void **p) {
    if (id==101 && fault==SECOND_MAPPING) return FAILURE;
    assert(id>=100 && id<=101); *p=memory[id-100]; return 0;
}
SceUID sceKernelCreateThread(const char *name, int (*entry)(SceSize,void *), int p,
                            SceSize stack, unsigned attr, int affinity, const void *opt) {
    (void)name; (void)stack; (void)attr; (void)affinity; (void)opt;
    ui_entry=entry;
    priority=p;
    /* Accept the conventional user-priority range and documented default.
     * In particular, do not accept arbitrary edits to the default encoding. */
    if ((p<64 || p>127) && p!=0x10000100) return FAILURE;
    if (fault==CREATE_THREAD) return FAILURE;
    assert(!thread_live); thread_live=1; return 20;
}
int sceKernelStartThread(SceUID id, SceSize n, void *p) {
    (void)n; (void)p; assert(id==20 && thread_live);
    if (fault==START_THREAD) return FAILURE;
    started=1; return 0;
}
int sceKernelDeleteThread(SceUID id) {
    assert(id==20 && thread_live); thread_live=started=0; return 0;
}
int sceKernelFreeMemBlock(SceUID id) {
    assert(id>=100 && id<=101);
    void *p=memory[id-100]; assert(p && p!=displayed);
    free(p); memory[id-100]=NULL; ++frees; return 0;
}
int sceKernelDeleteMutex(SceUID id) { assert(id==10 && mutex_live); mutex_live=0; return 0; }
int sceKernelWaitThreadEnd(SceUID id, int *status, unsigned *timeout) {
    (void)status; (void)timeout; assert(id==20 && thread_live && started); return 0;
}

int main(void) {
    const char *stages[]={"running", "allocate back framebuffer", "map back framebuffer",
                          "present initial framebuffer", "create UI thread (priority 127)",
                          "start UI thread"};
    for (fault=OK; fault<=START_THREAD; ++fault) {
        allocations=frees=priority=0;
        int rc=ui_start();
        assert(!strcmp(ui_startup_stage(),stages[fault]));
        if (fault==OK) {
            assert(rc==0 && started);
            assert(priority>=64 && priority<=127);
            ReceiverUiState state={0}; ui_publish(&state);
        } else assert(rc==FAILURE);
        ui_stop();
        assert(allocations==frees && !mutex_live && !thread_live && !displayed);
        assert(!memory[0] && !memory[1]);
        ui_stop(); /* Repeated cleanup is harmless. */
    }
    puts("UI startup: valid priority and five partial-failure cleanup paths passed.");
    for (off_error=0;off_error<=1;++off_error) {
        fault=OK;allocations=frees=priority=off_calls=on_calls=screen_stage=flips=0;
        assert(ui_start()==0);
        exercise_screen=1;assert(ui_entry(0,NULL)==0);exercise_screen=0;
        ui_stop();
        assert(off_calls==1 && on_calls>=1 && allocations==frees && !displayed);
    }
    puts("UI screen lifecycle: black before panel-off, no flips while blank, wake and failed-off fallback passed.");
    return 0;
}
