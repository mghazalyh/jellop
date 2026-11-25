#pragma once
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "surf_clock.h"

#define SURF_POOL_MAX 384
#define SURF_SLOTS 4
#define SURF_MASK_BYTES (SURF_POOL_MAX/8)
#define SURF_FILE_MAX 1024
#define SURF_CHECKPOINT_US 15000000ULL

// No credential material is stored. Scope includes the server and user,
// plus the selected page/search. Membership uses a sorted ID fingerprint,
// not UI indices, so favouriting/reordering cannot corrupt a cycle.
static inline uint64_t surf_hash(const char *str,uint64_t h=14695981039346656037ULL) {
    if (str) for (;*str;str++) { h^=(unsigned char)*str;h*=1099511628211ULL; }
    h^=255;return h*1099511628211ULL;
}
static inline bool surf_id_ok(const char *s) {
    if (!s || !*s) return false;
    unsigned n=0;
    for (;*s;s++,n++) {
        if (n>=39 || !((*s>='0'&&*s<='9')||(*s>='a'&&*s<='z')||
            (*s>='A'&&*s<='Z')||*s=='-')) return false;
    }
    return true;
}
struct SurfPool {
    uint64_t keys[SURF_POOL_MAX];
    unsigned count;
    uint64_t fingerprint;
};
static inline int surf_key_cmp(const void *a,const void *b) {
    uint64_t x=*(const uint64_t *)a,y=*(const uint64_t *)b;
    return x<y?-1:x>y?1:0;
}
static inline bool surf_pool_finish(SurfPool *p) {
    if (!p || !p->count || p->count>SURF_POOL_MAX) return false;
    qsort(p->keys,p->count,sizeof p->keys[0],surf_key_cmp);
    uint64_t h=14695981039346656037ULL;
    for(unsigned i=0;i<p->count;i++) {
        if(i&&p->keys[i]==p->keys[i-1]) return false; // duplicate or hash collision
        for(unsigned j=0;j<8;j++){h^=(p->keys[i]>>(j*8))&255u;h*=1099511628211ULL;}
    }
    p->fingerprint=h?h:1;return true;
}
static inline int surf_rank(const SurfPool *p,const char *id) {
    if(!p||!surf_id_ok(id))return -1;
    uint64_t key=surf_hash(id);
    unsigned a=0,b=p->count;
    while(a<b){unsigned m=a+(b-a)/2;if(p->keys[m]<key)a=m+1;else b=m;}
    return a<p->count&&p->keys[a]==key?(int)a:-1;
}
struct SurfCheckpoint {
    uint64_t scope,pool;
    unsigned cycle,remaining;
    char channel[40];
    unsigned char visited[SURF_MASK_BYTES];
};
struct SurfStore { SurfCheckpoint slots[SURF_SLOTS]; };
static inline bool surf_seen(const SurfCheckpoint *c,int rank) {
    return rank>=0&&rank<SURF_POOL_MAX&&(c->visited[rank/8]&(1u<<(rank%8)));
}
static inline void surf_mark(SurfCheckpoint *c,int rank) {
    if(rank>=0&&rank<SURF_POOL_MAX)c->visited[rank/8]|=(unsigned char)(1u<<(rank%8));
}
static inline void surf_next_cycle(SurfCheckpoint *c) {
    memset(c->visited,0,sizeof c->visited);
    c->cycle=c->cycle==0xffffffffu?1:c->cycle+1;
}
static inline bool surf_rollover_if_alternative(SurfCheckpoint *c,bool alternative) {
    if(!alternative)return false;
    surf_next_cycle(c);return true;
}
static inline SurfCheckpoint surf_restore(const SurfStore *s,uint64_t scope,const SurfPool *p,const char *id,unsigned dwell=60) {
    if(dwell<15||dwell>600)dwell=60;
    SurfCheckpoint c={};c.scope=scope;c.pool=p->fingerprint;c.cycle=1;c.remaining=dwell;
    for(unsigned i=0;i<SURF_SLOTS;i++)if(s->slots[i].scope==scope){
        c=s->slots[i];
        if(c.pool!=p->fingerprint){c.pool=p->fingerprint;surf_next_cycle(&c);}
        break;
    }
    if(!id||strcmp(c.channel,id)||surf_rank(p,id)<0||c.remaining>dwell)c.remaining=dwell;
    if(surf_id_ok(id))snprintf(c.channel,sizeof c.channel,"%s",id);
    return c;
}
static inline void surf_store_put(SurfStore *s,const SurfCheckpoint *c) {
    unsigned i=0;
    for(;i<SURF_SLOTS;i++)if(s->slots[i].scope==c->scope)break;
    if(i==SURF_SLOTS)i=SURF_SLOTS-1;
    memmove(s->slots+1,s->slots,i*sizeof s->slots[0]);s->slots[0]=*c;
}
static inline int surf_hex(char c) {
    return c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:-1;
}
// Strict bounded text; never dump native struct padding or endianness.
static inline int surf_store_format(const SurfStore *s,char *out,unsigned cap) {
    unsigned used=0;if(!out||!cap)return -1;out[0]=0;
    for(unsigned i=0;i<SURF_SLOTS;i++){
        const SurfCheckpoint *c=s->slots+i;
        if(!c->scope||!c->pool||!c->cycle||c->remaining>600||!surf_id_ok(c->channel))continue;
        char mask[SURF_MASK_BYTES*2+1];const char hex[]="0123456789abcdef";
        for(unsigned j=0;j<SURF_MASK_BYTES;j++){mask[2*j]=hex[c->visited[j]>>4];mask[2*j+1]=hex[c->visited[j]&15];}
        mask[sizeof mask-1]=0;
        int n=snprintf(out+used,cap-used,"1 %016llx %016llx %u %u %s %s\n",
            (unsigned long long)c->scope,(unsigned long long)c->pool,c->cycle,c->remaining,c->channel,mask);
        if(n<0||(unsigned)n>=cap-used)return -1;
        used+=(unsigned)n;
    }return (int)used;
}
static inline bool surf_store_parse(SurfStore *s,const char *str) {
    memset(s,0,sizeof *s);if(!str||strlen(str)>=SURF_FILE_MAX)return false;
    SurfStore tmp={};unsigned count=0;
    while(*str){
        const char *e=strchr(str,'\n');if(!e||e-str>=256||count>=SURF_SLOTS)return false;
        char line[256],mask[SURF_MASK_BYTES*2+1],id[40];unsigned ver,cycle,rem;unsigned long long scope,pool;int used=0;
        memcpy(line,str,e-str);line[e-str]=0;
        if(sscanf(line,"%u %16llx %16llx %u %u %39s %96s%n",&ver,&scope,&pool,&cycle,&rem,id,mask,&used)!=7||
           ver!=1||!scope||!pool||!cycle||rem>600||!surf_id_ok(id)||strlen(mask)!=SURF_MASK_BYTES*2||line[used])return false;
        for(unsigned i=0;i<count;i++)if(tmp.slots[i].scope==scope)return false;
        SurfCheckpoint &c=tmp.slots[count++];c.scope=scope;c.pool=pool;c.cycle=cycle;c.remaining=rem;
        snprintf(c.channel,sizeof c.channel,"%s",id);
        for(unsigned j=0;j<SURF_MASK_BYTES;j++){
            int a=surf_hex(mask[2*j]),b=surf_hex(mask[2*j+1]);if(a<0||b<0)return false;
            c.visited[j]=(unsigned char)(a*16+b);
        }
        str=e+1;
    }*s=tmp;return true;
}
