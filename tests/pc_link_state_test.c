/* Reproduce a route switch between delivery of a pending socket and adoption
 * by the audio thread. Uses real pc_link state/UI code, not a copied policy. */
#define PC_LINK_STATE_TEST
#include "../src/pc_link.c"
#include <assert.h>
static int closed_audio=-1;
void secure_net_close(int fd) { closed_audio=fd; }
int main(void) {
    ready=1;mutex=1;shared.paired=shared.desired=1;wanted=1;
    assert(pc_link_save_quality(320,128) && save_quality_pending);
    assert(saved_quality.modes[0]==320 && saved_quality.modes[1]==128);
    assert(!pc_link_save_quality(320,127) && saved_quality.modes[1]==128);
    assert(pc_link_save_display(120) && save_display_pending && saved_display==120);
    assert(!pc_link_save_display(31) && saved_display==120);
    audio_fd=10;audio_busy=1;control_fd=-1;control_busy=0;
    assert(pc_link_buttons(SCE_CTRL_TRIANGLE,0)&SCE_CTRL_TRIANGLE);
    assert(shared.remote_mode && switch_pending && !pc_link_wanted());
    assert(pc_link_take_audio()==-1 && audio_fd==10);
    pc_link_request(1);assert(!pc_link_wanted());
    finish_switch();assert(switch_pending && !pc_link_wanted());
    /* Network worker discards its old pending socket. */
    audio_fd=-1;audio_busy=0;finish_switch();
    assert(!switch_pending && pc_link_wanted());
    audio_fd=11;audio_busy=1;assert(pc_link_take_audio()==11 && audio_fd==-1);
    pc_link_audio_closed();assert(!audio_busy);
    audio_fd=14;audio_busy=1;control_busy=1;unsigned prior_serial=serial;
    pc_link_audio_hold(1);assert(audio_hold && audio_fd==-1 && !audio_busy && control_busy && closed_audio==14);
    assert(serial!=prior_serial && pc_link_wanted() && pc_link_take_audio()==-1);
    pc_link_audio_hold(0);assert(!audio_hold && control_busy && pc_link_wanted());
    control_busy=0;
    shared.remote_available=1;
    pc_link_buttons(SCE_CTRL_SELECT,0);assert(shared.editing && !pc_link_wanted());
    pc_link_buttons(SCE_CTRL_CIRCLE,0);assert(!shared.editing && pc_link_wanted());
    /* Active control worker must close before a new route is eligible. */
    control_busy=1;
    pc_link_buttons(SCE_CTRL_TRIANGLE,0);assert(!shared.remote_mode && !pc_link_wanted());
    pc_link_buttons(SCE_CTRL_CROSS,0);assert(!pc_link_wanted());
    finish_switch();assert(switch_pending);
    pc_link_control_closed();finish_switch();assert(pc_link_wanted() && !switch_pending);
    assert(pc_link_buttons(SCE_CTRL_TRIANGLE,1)==0 && !shared.remote_mode);
    pc_link_request(0);assert(!pc_link_wanted());
    audio_fd=12;assert(pc_link_take_audio()==-1);
    shared.paired=0;assert(pc_link_buttons(SCE_CTRL_SELECT|SCE_CTRL_CROSS,0)==(SCE_CTRL_SELECT|SCE_CTRL_CROSS));
    puts("PC link: local/remote handover, pending socket ownership, retry, details and active playback policy passed.");
    return 0;
}
