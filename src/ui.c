#include "ui.h"
#ifdef UI_HOST_TEST
#include "ui_test_platform.h"
#else
#include <psp2/display.h>
#include <psp2/kernel/sysmem.h>
#include <psp2/kernel/processmgr.h>
#include <psp2/kernel/threadmgr.h>
#include <psp2/net/netctl.h>
#include <psp2/power.h>
#endif
#include <stdio.h>
#include <string.h>

/* Scanout owns one framebuffer; the UI only draws into the other. No drawing,
 * framebuffer swaps, VBlank waits or IP lookups run in the audio loop. */
#define FB_BYTES (2*1024*1024)
/* Explicit user priority, also used by existing Vita homebrew. The previous
 * 0x10000120 was not a supported relative/default priority encoding. Keep UI
 * work below the usual main-thread priority without extending that encoding. */
#define UI_THREAD_PRIORITY 127
static SceUID blocks[2] = {-1,-1}, mutex = -1, thread = -1;
static uint32_t *pixels[2];
static ReceiverUiState shared;
static int stop_requested;
/* Artwork is larger than the UI thread's stack. Keep the snapshot in static RAM. */
static SpotifyView spotify;
static PcLinkView pc;
static const char *startup_stage = "not started";

const char *ui_startup_stage(void) { return startup_stage; }

static int present(int index) {
    SceDisplayFrameBuf fb = { sizeof(fb), pixels[index], UI_WIDTH,
        SCE_DISPLAY_PIXELFORMAT_A8B8G8R8, UI_WIDTH, UI_HEIGHT };
    int rc = sceDisplaySetFrameBuf(&fb, SCE_DISPLAY_SETBUF_NEXTFRAME);
    if (rc < 0) return rc;
    /* The old scanout buffer is not reusable until this flip has latched. */
    return sceDisplayWaitSetFrameBuf();
}

static int run_ui(SceSize argc, void *argv) {
    (void)argc; (void)argv;
    ReceiverUiState state, previous = {0};
    char ip[32] = "Checking Wi-Fi", previous_ip[32] = {0};
    uint64_t last_ip_check = 0;
    int back = 1, first = 1, blanked = 0;
    for (;;) {
        sceKernelLockMutex(mutex, 1, NULL);
        state = shared;
        int stop = stop_requested;
        sceKernelUnlockMutex(mutex, 1);
        if (stop) {
            if (blanked)scePowerRequestDisplayOn();
            break;
        }
        if (state.screen_mode==SCREEN_BLACK) {
            if (!blanked) {
                /* No persistent text, artwork, clock or logo on the idle frame.
                 * Do this before turning the display off; do not wait for VBlank
                 * or touch scanout buffers again until the user wakes the app. */
                ui_apply_screen(pixels[back],SCREEN_BLACK);
                if (present(back)<0)break;
                back^=1;
                scePowerRequestDisplayOff();blanked=1;
            }
            sceKernelDelayThread(100000);
            continue;
        }
        if (blanked) { scePowerRequestDisplayOn();blanked=0;first=1; }
        uint64_t now = sceKernelGetProcessTimeWide();
        if (!state.network_ready) {
            snprintf(ip, sizeof(ip), "%s", state.error ? "Unavailable" : "Checking Wi-Fi");
        } else if (!last_ip_check || now-last_ip_check >= 3000000ULL) {
            SceNetCtlInfo info = {0};
            if (sceNetCtlInetGetInfo(SCE_NETCTL_INFO_GET_IP_ADDRESS, &info) >= 0 &&
                info.ip_address[0] && strcmp(info.ip_address, "0.0.0.0"))
                snprintf(ip, sizeof(ip), "%s", info.ip_address);
            else snprintf(ip, sizeof(ip), "Connect to Wi-Fi");
            last_ip_check = now;
        }
        int spotify_changed=control_snapshot(&spotify);
        pc_link_snapshot(&pc);state.link=pc;
        if (first || spotify_changed || memcmp(&previous, &state, sizeof(state)) || strcmp(previous_ip, ip)) {
            ui_render_player(pixels[back], &state, ip, &spotify);
            ui_apply_screen(pixels[back],state.screen_mode);
            if (present(back) < 0) break;
            back ^= 1;
            previous = state;
            snprintf(previous_ip, sizeof(previous_ip), "%s", ip);
            first = 0;
        }
        sceKernelDelayThread(100000);
    }
    return 0;
}

int ui_start(void) {
    memset(&shared, 0, sizeof(shared));
    snprintf(shared.status, sizeof(shared.status), "Open the Windows host once. This Vita connects automatically.");
    stop_requested = 0;
    startup_stage = "create UI mutex";
    mutex = sceKernelCreateMutex("receiver-ui-state", 0, 0, NULL);
    if (mutex < 0) return mutex;
    int rc = -1;
    for (int i=0; i<2; ++i) {
        startup_stage = i ? "allocate back framebuffer" : "allocate front framebuffer";
        blocks[i] = sceKernelAllocMemBlock(i ? "receiver-ui-back" : "receiver-ui-front",
                         SCE_KERNEL_MEMBLOCK_TYPE_USER_CDRAM_RW, FB_BYTES, NULL);
        if (blocks[i] < 0) { rc=blocks[i]; goto fail; }
        startup_stage = i ? "map back framebuffer" : "map front framebuffer";
        rc = sceKernelGetMemBlockBase(blocks[i], (void **)&pixels[i]);
        if (rc < 0) goto fail;
    }
    ui_render_frame(pixels[0], &shared, "Checking Wi-Fi");
    startup_stage = "present initial framebuffer";
    rc = present(0);
    if (rc < 0) goto fail;
    startup_stage = "create UI thread (priority 127)";
    thread = sceKernelCreateThread("receiver-ui", run_ui, UI_THREAD_PRIORITY, 0x10000,
                                  0, SCE_KERNEL_THREAD_CPU_AFFINITY_MASK_DEFAULT, NULL);
    if (thread < 0) { rc=thread; goto fail; }
    startup_stage = "start UI thread";
    rc = sceKernelStartThread(thread, 0, NULL);
    if (rc < 0) { sceKernelDeleteThread(thread); thread=-1; goto fail; }
    startup_stage = "running";
    return 0;
fail:
    sceDisplaySetFrameBuf(NULL, SCE_DISPLAY_SETBUF_IMMEDIATE);
    for (int i=0; i<2; ++i) if (blocks[i] >= 0) {
        sceKernelFreeMemBlock(blocks[i]); blocks[i]=-1;
    }
    sceKernelDeleteMutex(mutex); mutex=-1;
    return rc;
}

void ui_publish(const ReceiverUiState *state) {
    if (mutex < 0 || sceKernelTryLockMutex(mutex, 1) < 0) return;
    shared = *state;
    sceKernelUnlockMutex(mutex, 1);
}

void ui_stop(void) {
    if (mutex < 0) return;
    sceKernelLockMutex(mutex, 1, NULL);
    stop_requested = 1;
    sceKernelUnlockMutex(mutex, 1);
    if (thread >= 0) {
        sceKernelWaitThreadEnd(thread, NULL, NULL);
        sceKernelDeleteThread(thread); thread=-1;
    }
    sceDisplaySetFrameBuf(NULL, SCE_DISPLAY_SETBUF_IMMEDIATE);
    for (int i=0; i<2; ++i) if (blocks[i] >= 0) {
        sceKernelFreeMemBlock(blocks[i]); blocks[i]=-1;
    }
    sceKernelDeleteMutex(mutex); mutex=-1;
}
