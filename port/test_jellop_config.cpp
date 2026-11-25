#include <assert.h>
#include <stdio.h>
#include "../source/api/jellop_config.h"
int main(){
    JellopConfig c;
    assert(jellop_config_parse(R"J({"JellopConfig":{"schemaVersion":1,"revision":8,"surfDwellSeconds":90,"liveRingMiB":3}})J",&c));
    assert(c.revision==8&&c.dwell_seconds==90&&c.ring_mib==3);
    const char *bad[]={
        "{}",
        R"J({"JellopConfig":{"schemaVersion":1,"revision":8,"surfDwellSeconds":900,"liveRingMiB":3}})J",
        R"J({"JellopConfig":{"schemaVersion":1,"revision":8,"surfDwellSeconds":90,"liveRingMiB":30}})J",
        R"J({"JellopConfig":{"schemaVersion":1,"revision":8,"surfDwellSeconds":90.5,"liveRingMiB":3}})J",
        R"J({"JellopConfig":{"schemaVersion":1,"revision":8,"surfDwellSeconds":90,"liveRingMiB":"3"}})J",
        R"J({"JellopConfig":{"schemaVersion":1,"revision":9999999999999999999,"surfDwellSeconds":90,"liveRingMiB":3}})J"};
    for(unsigned i=0;i<sizeof bad/sizeof bad[0];i++){
        assert(!jellop_config_parse(bad[i],&c));
        assert(c.revision==0&&c.dwell_seconds==60&&c.ring_mib==6);
    }
    puts("Declarative native configuration bounds and fallback passed");
}
