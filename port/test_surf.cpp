#include <assert.h>
#include <stdio.h>
#include "../source/player/core/surf_clock.h"
static_assert(sizeof(SurfClock)<=48,"Surf timer memory budget");
int main() {
    SurfClock c;surf_clock_init(&c,60);
    assert(c.mode==SURF_OFF && surf_clock_seconds(&c)==60);
    surf_clock_toggle(&c,1000000,1);
    for(int f=2;f<=31;f++)assert(!surf_clock_step(&c,(uint64_t)f*1000000,f,false));
    assert(surf_clock_seconds(&c)==30);
    surf_clock_toggle(&c,31000000,31);
    assert(!surf_clock_step(&c,91000000,32,false));
    assert(surf_clock_seconds(&c)==30);
    surf_clock_toggle(&c,91000000,32);
    assert(!surf_clock_step(&c,121000000,32,false));
    assert(!surf_clock_step(&c,122000000,33,false));
    assert(surf_clock_seconds(&c)==30);
    for(int i=1;i<30;i++)assert(!surf_clock_step(&c,122000000ULL+i*1000000ULL,33+i,false));
    assert(surf_clock_step(&c,152000000,63,false));
    surf_clock_new_channel(&c,152000000,0);
    assert(surf_clock_seconds(&c)==60);
    assert(!surf_clock_step(&c,153000000,0,false));
    assert(!surf_clock_step(&c,154000000,1,true));
    assert(surf_clock_seconds(&c)==60);
    puts("Surf countdown, pause, stall exclusion, and channel reset passed");
}
