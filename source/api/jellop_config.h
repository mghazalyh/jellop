#pragma once
#include "json_lite.h"

// Declarative, bounded settings only. No executable patch format.
struct JellopConfig {
    unsigned revision,dwell_seconds,ring_mib;
};
static inline JellopConfig jellop_config_default() {
    JellopConfig c={0,60,6};return c;
}
static inline bool jellop_config_uint(const char *o,const char *e,const char *key,
                                      unsigned min,unsigned max,unsigned *out) {
    const char *v=find_top_value(o,e,key);
    if(!v||v>=e||*v<'0'||*v>'9')return false;
    unsigned n=0;
    for(;v<e&&*v>='0'&&*v<='9';v++){
        unsigned d=(unsigned)(*v-'0');
        if(d>max||n>(max-d)/10)return false;
        n=n*10+d;
    }
    v=skip_ws(v,e);
    if(v>=e||(*v!=','&&*v!='}')||n<min||n>max)return false;
    *out=n;return true;
}
static inline bool jellop_config_parse(const char *json,JellopConfig *out) {
    if(!out)return false;
    *out=jellop_config_default();
    if(!json)return false;
    const char *end=json+strlen(json),*root=skip_ws(json,end);
    const char *o=find_top_value(root,end,"JellopConfig");
    const char *e=object_end(o,end);
    unsigned version=0;JellopConfig c={};
    if(!e||!jellop_config_uint(o,e,"schemaVersion",1,1,&version)||
       !jellop_config_uint(o,e,"revision",1,2147483647u,&c.revision)||
       !jellop_config_uint(o,e,"surfDwellSeconds",15,600,&c.dwell_seconds)||
       !jellop_config_uint(o,e,"liveRingMiB",2,6,&c.ring_mib))return false;
    *out=c;return true;
}
