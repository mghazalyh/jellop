#pragma once
#include "jellop_config.h"

// Strict, bounded summary only; native code never downloads an unbounded
// telemetry archive or another account's session IDs for the Insights view.
struct JellopInsights {
    unsigned policy_known,total,eligible,hiatus,banned;
    unsigned sessions,active,observed,stalled,sustained,transport_faults;
    unsigned min_reported_free_kib,config_revision,config_fault;
};
static inline bool jellop_insights_parse(const char *json,JellopInsights *out){
    if(!json||!out||strlen(json)>=2048)return false;
    const char *end=json+strlen(json),*root=skip_ws(json,end);
    const char *root_end=object_end(root,end);
    if(!root_end||skip_ws(root_end,end)!=end)return false;
    const char *o=find_top_value(root,root_end,"JellopInsights");
    const char *e=object_end(o,root_end);
    JellopInsights v={};unsigned schema=0;
    if(!e||
       !jellop_config_uint(o,e,"SchemaVersion",1,1,&schema)||
       !jellop_config_uint(o,e,"PolicyKnown",0,1,&v.policy_known)||
       !jellop_config_uint(o,e,"TotalChannels",0,6000,&v.total)||
       !jellop_config_uint(o,e,"Eligible",0,v.total,&v.eligible)||
       !jellop_config_uint(o,e,"Hiatus",0,v.total,&v.hiatus)||
       !jellop_config_uint(o,e,"Banned",0,v.total,&v.banned)||
       !jellop_config_uint(o,e,"Sessions",0,24,&v.sessions)||
       !jellop_config_uint(o,e,"Active",0,v.sessions,&v.active)||
       !jellop_config_uint(o,e,"ObservedSessions",0,v.sessions,&v.observed)||
       !jellop_config_uint(o,e,"StalledSessions",0,v.observed,&v.stalled)||
       !jellop_config_uint(o,e,"SustainedSessions",0,v.observed,&v.sustained)||
       !jellop_config_uint(o,e,"TransportFaultSessions",0,v.sessions,&v.transport_faults)||
       !jellop_config_uint(o,e,"MinReportedFreeKiB",0,0xffffffffu,&v.min_reported_free_kib)||
       !jellop_config_uint(o,e,"ConfigRevision",1,2147483647u,&v.config_revision)||
       !jellop_config_uint(o,e,"ConfigFault",0,1,&v.config_fault))return false;
    unsigned classified=v.eligible+v.hiatus+v.banned;
    if((v.policy_known&&classified!=v.total)||(!v.policy_known&&classified)||
       (!v.observed&&v.min_reported_free_kib))return false;
    *out=v;return true;
}
