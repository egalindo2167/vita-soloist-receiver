#ifndef VITA_CAPTURE_POLICY_H
#define VITA_CAPTURE_POLICY_H
#include <stdint.h>
enum { CAP_OK=0,CAP_NOT_CONFIGURED=1,CAP_DEVICE_MISSING=2,CAP_PROCESS_MISSING=3,
       CAP_ROUTE_MISMATCH=4,CAP_UNSUPPORTED=5,CAP_OPEN_FAILED=6,CAP_ROUTE_UNVERIFIED=7 };
typedef struct { unsigned selected_active,other_active,selected_idle,other_idle; } CaptureRoutes;
static inline int capture_route_error(CaptureRoutes r) {
    if(r.other_active)return CAP_ROUTE_MISMATCH;
    if(!r.selected_active && !r.selected_idle && r.other_idle)return CAP_ROUTE_MISMATCH;
    return CAP_OK;
}
static inline int capture_route_verified(CaptureRoutes r) {
    return capture_route_error(r)==CAP_OK && (r.selected_active || r.selected_idle);
}
static inline int capture_identity_matches(uint64_t expected,uint64_t actual,int same_exe) {
    return expected && expected==actual && same_exe;
}
#endif
