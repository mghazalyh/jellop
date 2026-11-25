#pragma once
#include <stdint.h>
#include <stdbool.h>

// No timer thread, heap, or work while playback is not progressing.
enum SurfMode { SURF_OFF=0, SURF_RUNNING, SURF_PAUSED };
struct SurfClock {
    SurfMode mode;
    uint64_t dwell_us, remaining_us, last_frame_us;
    int last_frame;
};
static inline void surf_clock_init(SurfClock *c,unsigned seconds) {
    if (seconds<15) seconds=15;
    if (seconds>600) seconds=600;
    c->mode=SURF_OFF;c->dwell_us=(uint64_t)seconds*1000000ULL;
    c->remaining_us=c->dwell_us;c->last_frame_us=0;c->last_frame=0;
}
static inline void surf_clock_rebase(SurfClock *c,uint64_t now,int frame) {
    c->last_frame_us=now;c->last_frame=frame;
}
static inline void surf_clock_new_channel(SurfClock *c,uint64_t now,int frame) {
    c->remaining_us=c->dwell_us;surf_clock_rebase(c,now,frame);
}
static inline void surf_clock_toggle(SurfClock *c,uint64_t now,int frame) {
    if (c->mode==SURF_OFF) c->remaining_us=c->dwell_us;
    c->mode=c->mode==SURF_RUNNING ? SURF_PAUSED : SURF_RUNNING;
    surf_clock_rebase(c,now,frame);
}
static inline bool surf_clock_step(SurfClock *c,uint64_t now,int frame,bool hold) {
    if (c->mode!=SURF_RUNNING || hold || frame<=0 || frame<c->last_frame || now<c->last_frame_us) {
        surf_clock_rebase(c,now,frame);return false;
    }
    if (frame==c->last_frame) return false;
    const uint64_t elapsed=now-c->last_frame_us;
    surf_clock_rebase(c,now,frame);
    // A long gap is not credited as successfully decoded playback.
    if (elapsed<=1000000ULL) {
        c->remaining_us=elapsed>=c->remaining_us ? 0 : c->remaining_us-elapsed;
    }
    return c->remaining_us==0;
}
static inline unsigned surf_clock_seconds(const SurfClock *c) {
    return (unsigned)((c->remaining_us+999999ULL)/1000000ULL);
}
