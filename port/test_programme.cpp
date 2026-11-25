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
    const char *provider = R"({"Items":[{"Id":"abc","Name":"Channel","CurrentProgram":{"Name":"Movie (2020)","JealousfinProgramme":{"title":"Movie","source":"provider-catalogue","observedAt":1795620000.125,"year":2020}}}],"TotalRecordCount":1})";
    JFChannel c = parse(provider);
    assert(!strcmp(c.now_title,"Movie (2020)"));
    assert(c.now_start_ticks == 0 && c.now_end_ticks == 0);
    assert(livetv_current_title_valid(&c,jf_ticks_from_unix(1795620001)));
    assert(!livetv_current_title_valid(&c,jf_ticks_from_unix(1795620150)));
    const char *guide = R"({"Items":[{"Id":"abc","CurrentProgram":{"Name":"Scheduled: Film (1992)","JealousfinProgramme":{"source":"corroborated-external-schedule","observedAt":1795620000}}}]})";
    c = parse(guide);
    assert(!strcmp(c.now_title,"Film (1992)"));
    assert(livetv_current_title_valid(&c,jf_ticks_from_unix(1795621799)));
    assert(!livetv_current_title_valid(&c,jf_ticks_from_unix(1795621800)));
    c = parse(R"({"Items":[{"Id":"abc","CurrentProgram":{"Name":"Bad","JealousfinProgramme":{"source":"unknown","observedAt":1795620000}}}]})");
    assert(!livetv_current_title_valid(&c,jf_ticks_from_unix(1795620001)));
    c = parse(R"({"Items":[{"Id":"abc","CurrentProgram":{"Name":"Undated ordinary item"}}]})");
    assert(!livetv_current_title_valid(&c,jf_ticks_from_unix(1795620001)));
    c = parse(R"({"Items":[{"Id":"abc","CurrentProgram":{"Name":"Regular EPG","StartDate":"2026-11-25T00:00:00Z","EndDate":"2026-11-26T00:00:00Z"}}]})");
    assert(livetv_current_title_valid(&c,jf_ticks_from_iso8601("2026-11-25T23:59:59Z")));
    assert(!livetv_current_title_valid(&c,jf_ticks_from_iso8601("2026-11-26T00:00:00Z")));
    assert(!livetv_current_title_valid(NULL,1));
    puts("Jellop current-only programme and live ring regression checks passed");
}
