#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "../source/api/livetv.h"
#include "../source/player/core/live_buffer.h"

static_assert(sizeof(JFChannel) <= 360, "Channel record size budget exceeded");
static_assert(LIVE_RING_BYTES_MAX == 6u * 1024u * 1024u, "Live ring budget changed");

static JFChannel parse(const char *json) {
    JFChannel result = {};
    int total = 0;
    bool truncated = false;
    assert(livetv_parse_channels(json, (int)strlen(json), &result, 1, &total, &truncated) == 1);
    assert(!truncated && total == 1);
    return result;
}

int main() {
    const char *provider = R"JSON({"Items":[{"Id":"abc","Name":"Channel","CurrentProgram":{"Name":"Movie (2020)","JealousfinProgramme":{"title":"Movie","source":"provider-catalogue","observedAt":1795620000.125,"year":2020}}}],"TotalRecordCount":1})JSON";
    JFChannel c = parse(provider);
    assert(!strcmp(c.now_title,"Movie (2020)"));
    assert(c.now_start_ticks == 0 && c.now_end_ticks == 0);
    assert(livetv_current_title_valid(&c,jf_ticks_from_unix(1795620001)));
    assert(!livetv_current_title_valid(&c,jf_ticks_from_unix(1795619900)));
    assert(!livetv_current_title_valid(&c,jf_ticks_from_unix(1795620150)));
    const char *guide = R"JSON({"Items":[{"Id":"abc","CurrentProgram":{"Name":"Scheduled: Film (1992)","JealousfinProgramme":{"source":"corroborated-external-schedule","observedAt":1795620000}}}]})JSON";
    c = parse(guide);
    assert(!strcmp(c.now_title,"Film (1992)"));
    assert(livetv_current_title_valid(&c,jf_ticks_from_unix(1795621799)));
    assert(!livetv_current_title_valid(&c,jf_ticks_from_unix(1795621800)));
    c = parse(R"JSON({"Items":[{"Id":"abc","CurrentProgram":{"Name":"Bad","JealousfinProgramme":{"source":"unknown","observedAt":1795620000}}}]})JSON");
    assert(!livetv_current_title_valid(&c,jf_ticks_from_unix(1795620001)));
    c = parse(R"JSON({"Items":[{"Id":"abc","CurrentProgram":{"Name":"Undated ordinary item"}}]})JSON");
    assert(!livetv_current_title_valid(&c,jf_ticks_from_unix(1795620001)));
    c = parse(R"JSON({"Items":[{"Id":"abc","CurrentProgram":{"Name":"Regular EPG","StartDate":"2026-11-25T00:00:00Z","EndDate":"2026-11-26T00:00:00Z"}}]})JSON");
    assert(livetv_current_title_valid(&c,jf_ticks_from_iso8601("2026-11-25T23:59:59Z")));
    assert(!livetv_current_title_valid(&c,jf_ticks_from_iso8601("2026-11-26T00:00:00Z")));
    assert(!livetv_current_title_valid(NULL,1));
    const char *programmes=R"JSON({"Items":[{"ChannelId":"a","Name":"Film (2020)","JealousfinProgramme":{"source":"provider-catalogue","observedAt":1795620000}},{"ChannelId":"b","Name":"Wrong channel","JealousfinProgramme":{"source":"provider-catalogue","observedAt":1795620000}}]})JSON";
    JFProgram rows[2]={};
    assert(livetv_parse_programs(programmes,strlen(programmes),rows,2,0,0)==2);
    assert(livetv_current_programme_index(rows,2,"a",jf_ticks_from_unix(1795620001))==0);
    assert(livetv_current_programme_index(rows,2,"a",jf_ticks_from_unix(1795620150))==-1);
    assert(livetv_current_programme_index(rows,2,"c",jf_ticks_from_unix(1795620001))==-1);
    c=parse(R"JSON({"Items":[{"Id":"abc","Name":"Sports","JellopGenreMask":0}]})JSON");
    assert(c.genre_authoritative && livetv_channel_genres(&c)==0);
    c=parse(R"JSON({"Items":[{"Id":"abc","Name":"Unknown","JellopGenreMask":4}]})JSON");
    assert(livetv_channel_genres(&c)==(1u<<LG_MOVIES));
    c=parse(R"JSON({"Items":[{"Id":"abc","Name":"Blocked","JellopHealth":{"banned":true,"eligible":false,"hiatusUntil":0}}]})JSON");
    assert(c.policy_state==LT_POLICY_BANNED && livetv_policy_excluded(&c));
    c=parse(R"JSON({"Items":[{"Id":"abc","Name":"Cooldown","JellopHealth":{"banned":false,"eligible":false,"hiatusUntil":4102444800}}]})JSON");
    assert(c.policy_state==LT_POLICY_HIATUS && c.policy_until_unix==4102444800u && livetv_policy_excluded(&c));
    c=parse(R"JSON({"Items":[{"Id":"abc","JellopHealth":{"banned":false,"eligible":true,"hiatusUntil":0}}]})JSON");
    assert(c.policy_state==LT_POLICY_ELIGIBLE && !livetv_policy_excluded(&c));
    c=parse(R"JSON({"Items":[{"Id":"abc","JellopHealth":{"banned":true,"eligible":true,"hiatusUntil":0}}]})JSON");
    assert(c.policy_state==LT_POLICY_UNKNOWN);
    c=parse(R"JSON({"Items":[{"Id":"abc","JellopHealth":{"banned":"true","eligible":false,"hiatusUntil":0}}]})JSON");
    assert(c.policy_state==LT_POLICY_UNKNOWN);
    puts("Jellop current-only programme, policy, authoritative categories and live ring regression checks passed");
}
