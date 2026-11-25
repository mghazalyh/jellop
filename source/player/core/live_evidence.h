#pragma once
#include <stdint.h>
#include <stdbool.h>
struct LiveEvidence {
    uint64_t decoded_us,last_advance_us;
    unsigned frames,stalls;
    int last_frame;
    bool stalled;
};
static inline void live_evidence_reset(LiveEvidence *e,uint64_t now,int frame){
    e->decoded_us=0;e->last_advance_us=now;e->frames=0;e->stalls=0;
    e->last_frame=frame;e->stalled=false;
}
static inline void live_evidence_step(LiveEvidence *e,uint64_t now,int frame,bool hold){
    if(hold||frame<e->last_frame||now<e->last_advance_us){
        e->last_frame=frame;e->last_advance_us=now;e->stalled=false;return;
    }
    const uint64_t gap=now-e->last_advance_us;
    if(frame>e->last_frame){
        unsigned delta=(unsigned)(frame-e->last_frame);
        if(e->frames<=0xffffffffu-delta)e->frames+=delta;
        if(gap<=1000000ULL)e->decoded_us+=gap;
        else if(gap>=6000000ULL&&!e->stalled&&e->stalls<0xffffffffu)e->stalls++;
        e->last_frame=frame;e->last_advance_us=now;e->stalled=false;
    }else if(e->frames&&gap>=6000000ULL&&!e->stalled){
        if(e->stalls<0xffffffffu)e->stalls++;
        e->stalled=true;
    }
}
