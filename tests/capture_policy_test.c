#include "../pc/native_src/capture_policy.h"
#include <assert.h>
#include <stdio.h>
int main(void) {
    CaptureRoutes empty={0},on_cable={1,0,0,0},idle_cable={0,0,1,0};
    CaptureRoutes speakers={0,1,0,0},both={1,1,0,0},old_speakers={0,0,0,1},moved={1,0,0,1};
    assert(capture_route_error(empty)==CAP_OK && !capture_route_verified(empty));
    assert(capture_route_error(on_cable)==CAP_OK && capture_route_verified(on_cable));
    assert(capture_route_verified(idle_cable));
    assert(capture_route_error(speakers)==CAP_ROUTE_MISMATCH && !capture_route_verified(speakers));
    assert(capture_route_error(both)==CAP_ROUTE_MISMATCH && !capture_route_verified(both));
    assert(capture_route_error(old_speakers)==CAP_ROUTE_MISMATCH);
    /* An inactive abandoned session is harmless when the selected route exists. */
    assert(capture_route_verified(moved));
    assert(capture_identity_matches(1234,1234,1));
    assert(!capture_identity_matches(1234,1235,1)); /* Reused PID, different birth time. */
    assert(!capture_identity_matches(1234,1234,0)); /* Unrelated executable. */
    assert(!capture_identity_matches(0,0,1));
    puts("Capture policy: missing/ambiguous routes and reused process identities rejected.");
    return 0;
}
