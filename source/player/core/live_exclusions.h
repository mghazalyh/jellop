#pragma once
#include <stdint.h>
#include <string.h>
#include "surf_state.h"

// Local retry cooldown only. Never implies a source failure or server ban.
#define LIVE_EXCLUSION_MAX 32
#define LIVE_EXCLUSION_US 300000000ULL
struct LiveExclusion { uint64_t until; char id[40]; };
struct LiveExclusions { LiveExclusion slots[LIVE_EXCLUSION_MAX]; };
static inline bool live_excluded(const LiveExclusions *s,const char *id,uint64_t now){
    if(!surf_id_ok(id))return false;
    for(unsigned i=0;i<LIVE_EXCLUSION_MAX;i++)
        if(s->slots[i].until>now&&!strcmp(s->slots[i].id,id))return true;
    return false;
}
static inline void live_exclude(LiveExclusions *s,const char *id,uint64_t now){
    if(!surf_id_ok(id))return;
    unsigned slot=0;
    for(unsigned i=0;i<LIVE_EXCLUSION_MAX;i++){
        if(!strcmp(s->slots[i].id,id)){slot=i;break;}
        if(s->slots[i].until<s->slots[slot].until)slot=i;
    }
    snprintf(s->slots[slot].id,sizeof s->slots[slot].id,"%s",id);
    s->slots[slot].until=now>UINT64_MAX-LIVE_EXCLUSION_US?UINT64_MAX:now+LIVE_EXCLUSION_US;
}
