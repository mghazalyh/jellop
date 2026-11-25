#include <assert.h>
#include <stdio.h>
#include "../source/player/core/live_evidence.h"
static_assert(sizeof(LiveEvidence)<=48,"evidence memory budget");
int main(){
    LiveEvidence e;live_evidence_reset(&e,0,0);
    for(int i=1;i<=60;i++)live_evidence_step(&e,i*1000000ULL,i*25,false);
    assert(e.frames==1500&&e.decoded_us==60000000&&e.stalls==0);
    live_evidence_step(&e,67000000,1500,false);assert(e.stalls==1);
    live_evidence_step(&e,68000000,1500,false);assert(e.stalls==1);
    live_evidence_step(&e,69000000,1525,false);assert(e.stalls==1&&e.decoded_us==60000000);
    live_evidence_step(&e,70000000,1550,false);assert(e.decoded_us==61000000);
    live_evidence_step(&e,90000000,1550,true);assert(e.stalls==1);
    live_evidence_reset(&e,90000000,1550);assert(!e.frames&&!e.stalls&&!e.decoded_us);
    puts("Decoded evidence, stall exclusion, pause and session reset passed");
}
