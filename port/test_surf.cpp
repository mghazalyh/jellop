#include <assert.h>
#include <stdio.h>
#include "../source/player/core/surf_clock.h"
#include "../source/player/core/surf_preference.h"
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
    surf_clock_toggle(&c,154000000,1);assert(c.mode==SURF_PAUSED);
    surf_clock_set_dwell(&c,120,155000000,1);
    assert(c.mode==SURF_PAUSED&&surf_clock_seconds(&c)==120);
    surf_clock_toggle(&c,155000000,1);
    assert(!surf_clock_step(&c,156000000,2,false)&&surf_clock_seconds(&c)==119);
    unsigned n=0;
    assert(surf_dwell_parse("120\n",&n)&&n==120);
    assert(surf_dwell_parse("0",&n)&&n==0);
    assert(!surf_dwell_parse("-1",&n)&&!surf_dwell_parse("61",&n)&&!surf_dwell_parse("600oops",&n));
    assert(surf_dwell_effective(0,15)==15&&surf_dwell_effective(120,15)==120&&surf_dwell_effective(0,999)==60);
    puts("Surf countdown, pause, stall exclusion, interval preference and channel reset passed");
}
