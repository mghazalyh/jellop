#include <assert.h>
#include <stdio.h>
#include "../source/player/core/surf_state.h"
#include "../source/player/core/live_buffer.h"
#include "../source/player/core/live_exclusions.h"
static_assert(sizeof(SurfStore)<800,"checkpoint RAM budget");
static_assert(sizeof(SurfPool)<3100,"pool RAM budget");
int main(){
    SurfPool p={};p.keys[0]=surf_hash("a");p.keys[1]=surf_hash("b");p.count=2;assert(surf_pool_finish(&p));
    SurfPool q={};q.keys[0]=surf_hash("b");q.keys[1]=surf_hash("a");q.count=2;assert(surf_pool_finish(&q));
    assert(p.fingerprint==q.fingerprint&&surf_rank(&p,"b")==surf_rank(&q,"b"));
    SurfStore s={};SurfCheckpoint c=surf_restore(&s,1,&p,"a");
    c.remaining=23;surf_mark(&c,surf_rank(&p,"a"));surf_store_put(&s,&c);
    char buf[SURF_FILE_MAX];assert(surf_store_format(&s,buf,sizeof buf)>0);
    SurfStore loaded;assert(surf_store_parse(&loaded,buf));
    c=surf_restore(&loaded,1,&q,"a");assert(c.remaining==23&&surf_seen(&c,surf_rank(&q,"a")));
    assert(surf_restore(&loaded,1,&q,"b").remaining==60);
    assert(surf_restore(&loaded,2,&q,"a").remaining==60);
    q.keys[q.count++]=surf_hash("c");assert(surf_pool_finish(&q));
    c=surf_restore(&loaded,1,&q,"a");assert(c.cycle==2&&c.remaining==23&&!surf_seen(&c,surf_rank(&q,"a")));
    for(unsigned i=2;i<=5;i++){c=surf_restore(&loaded,i,&p,"a");surf_store_put(&loaded,&c);}
    assert(loaded.slots[0].scope==5&&loaded.slots[3].scope==2);
    assert(surf_store_format(&loaded,buf,sizeof buf)>0);
    assert(surf_store_parse(&s,buf));assert(s.slots[3].scope==2);
    assert(!surf_store_parse(&s,"1 2 3 4 5 a xyz\n"));assert(s.slots[0].scope==0);
    assert(live_ring_budget(0,false)==LIVE_RING_MIN);
    assert(live_ring_budget(9*1024*1024,true)==0);
    assert(live_ring_budget(10*1024*1024,true)==LIVE_RING_MIN);
    assert(live_ring_budget(12*1024*1024,true)==4*1024*1024);
    assert(live_ring_budget(32*1024*1024,true)==LIVE_RING_BYTES_MAX);
    c=surf_restore(&s,10,&p,"a");
    surf_mark(&c,surf_rank(&p,"a"));
    assert(!surf_rollover_if_alternative(&c,false)&&c.cycle==1&&surf_seen(&c,surf_rank(&p,"a")));
    assert(surf_rollover_if_alternative(&c,true)&&c.cycle==2&&!surf_seen(&c,surf_rank(&p,"a")));
    LiveExclusions ex={};live_exclude(&ex,"a",10);
    assert(live_excluded(&ex,"a",10+LIVE_EXCLUSION_US-1));
    assert(!live_excluded(&ex,"a",10+LIVE_EXCLUSION_US));
    live_exclude(&ex,"a",20);
    for(unsigned n=0;n<32;n++){char id[16];snprintf(id,sizeof id,"channel-%u",n);live_exclude(&ex,id,100+n);}
    assert(!live_excluded(&ex,"a",200));
    assert(live_excluded(&ex,"channel-0",200)&&live_excluded(&ex,"channel-31",200));
    puts("Scope isolation, stable cycle, LRU checkpoints, corrupt-state rejection, retry cooldown and memory budgets passed");
}
