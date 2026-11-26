#pragma once
#include "livetv_prefs.h"
#include <stdint.h>
#include <stdio.h>
#include <string.h>

// Two account scopes: English and Malay. Bounded MRU eviction, no token,
// no password, and no raw server/account names in the on-disk history.
#define RECENT_HISTORY_SLOTS 2
#define RECENT_HISTORY_FILE_MAX 2560
struct RecentHistorySlot {
    uint64_t scope;
    int count;
    char ids[LP_MAX_RECENT][LP_ID_MAX];
};
struct RecentHistory { RecentHistorySlot slots[RECENT_HISTORY_SLOTS]; };

static inline bool history_id_ok(const char *id) {
    if(!id||!*id)return false;
    unsigned n=0;
    for(;*id;id++,n++){
        char c=*id;
        if(n>=LP_ID_MAX-1||!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||
           (c>='0'&&c<='9')||c=='-'))return false;
    }
    return true;
}
static inline bool history_slot_valid(const RecentHistorySlot *s) {
    if(!s->scope||s->count<1||s->count>LP_MAX_RECENT)return false;
    for(int i=0;i<s->count;i++){
        if(!memchr(s->ids[i],0,LP_ID_MAX)||!history_id_ok(s->ids[i]))return false;
        for(int j=0;j<i;j++)if(!strcmp(s->ids[i],s->ids[j]))return false;
    }
    return true;
}
static inline bool history_get(const RecentHistory *h,uint64_t scope,LtPrefs *p) {
    if(!p)return false;
    p->n_recent=0;memset(p->recent,0,sizeof p->recent);
    if(!h||!scope)return false;
    for(int i=0;i<RECENT_HISTORY_SLOTS;i++){
        const RecentHistorySlot *s=&h->slots[i];
        if(s->scope==scope&&history_slot_valid(s)){
            p->n_recent=s->count;
            memcpy(p->recent,s->ids,sizeof p->recent);return true;
        }
    }
    return false;
}
static inline bool history_put(RecentHistory *h,uint64_t scope,const LtPrefs *p) {
    if(!h||!p||!scope)return false;
    RecentHistorySlot next={};
    next.scope=scope;next.count=p->n_recent;
    memcpy(next.ids,p->recent,sizeof next.ids);
    if(!history_slot_valid(&next))return false;
    int at=0;
    for(;at<RECENT_HISTORY_SLOTS;at++)if(h->slots[at].scope==scope)break;
    if(at==RECENT_HISTORY_SLOTS)at=RECENT_HISTORY_SLOTS-1;
    memmove(h->slots+1,h->slots,(size_t)at*sizeof h->slots[0]);
    h->slots[0]=next;return true;
}
static inline int history_format(const RecentHistory *h,char *out,size_t cap) {
    if(!h||!out||cap==0)return -1;
    size_t used=0;
    out[0]=0;
    for(int i=0;i<RECENT_HISTORY_SLOTS;i++){
        const RecentHistorySlot *s=&h->slots[i];
        if(!s->scope)continue;
        if(!history_slot_valid(s))return -1;
        int n=snprintf(out+used,cap-used,"1 %016llx",(unsigned long long)s->scope);
        if(n<0||(size_t)n>=cap-used)return -1;
        used+=(size_t)n;
        for(int j=0;j<s->count;j++){
            n=snprintf(out+used,cap-used," %s",s->ids[j]);
            if(n<0||(size_t)n>=cap-used)return -1;
            used+=(size_t)n;
        }
        if(cap-used<2)return -1;
        out[used++]='\n';out[used]=0;
    }
    return (int)used;
}
static inline bool history_parse(const char *text,RecentHistory *h) {
    if(!text||!h||strlen(text)>=RECENT_HISTORY_FILE_MAX)return false;
    RecentHistory value={};int count=0;
    const char *p=text;
    while(*p){
        if(count>=RECENT_HISTORY_SLOTS||strncmp(p,"1 ",2))return false;
        const char *end=strchr(p,'\n');
        if(!end||end-p<20)return false;
        p+=2;
        uint64_t scope=0;
        for(int i=0;i<16;i++){
            char c=*p++;
            int n=c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:-1;
            if(n<0)return false;
            scope=(scope<<4)|(unsigned)n;
        }
        if(!scope)return false;
        for(int i=0;i<count;i++)if(value.slots[i].scope==scope)return false;
        RecentHistorySlot *s=&value.slots[count++];s->scope=scope;
        while(p<end){
            if(*p++!=' '||s->count>=LP_MAX_RECENT)return false;
            const char *start=p;
            while(p<end&&*p!=' ')p++;
            size_t len=(size_t)(p-start);
            if(!len||len>=LP_ID_MAX)return false;
            memcpy(s->ids[s->count],start,len);
            s->ids[s->count++][len]=0;
        }
        if(!history_slot_valid(s))return false;
        p=end+1;
    }
    *h=value;return true;
}
