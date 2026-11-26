#include "../source/api/jellop_insights.h"
#include <assert.h>
#include <string>
#include <stdio.h>
int main(){
    const std::string valid=R"({"JellopInsights":{"SchemaVersion":1,"PolicyKnown":1,"TotalChannels":4,"Eligible":2,"Hiatus":1,"Banned":1,"Sessions":5,"Active":1,"ObservedSessions":5,"StalledSessions":0,"SustainedSessions":2,"TransportFaultSessions":0,"MinReportedFreeKiB":27960,"ConfigRevision":7,"ConfigFault":0}})";
    JellopInsights s={};
    assert(jellop_insights_parse(valid.c_str(),&s));
    assert(s.eligible==2&&s.observed==5&&s.min_reported_free_kib==27960&&s.config_revision==7);
    std::string bad=valid;
    bad.replace(bad.find("\"Banned\":1"),10,"\"Banned\":2");
    assert(!jellop_insights_parse(bad.c_str(),&s));
    bad=valid;bad.replace(bad.find("\"Sessions\":5"),12,"\"Sessions\":25");
    assert(!jellop_insights_parse(bad.c_str(),&s));
    bad=valid;bad.replace(bad.find("\"PolicyKnown\":1"),15,"\"PolicyKnown\":0");
    assert(!jellop_insights_parse(bad.c_str(),&s));
    assert(!jellop_insights_parse((valid+"garbage").c_str(),&s));
    assert(!jellop_insights_parse("{}",&s));
    assert(s.eligible==2&&s.config_revision==7);
    puts("insights schema, bounds and consistency: passed");
}
