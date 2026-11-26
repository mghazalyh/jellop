#include "auth_data.h"
#include "profile_model.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <string>

static bool read_config(const std::string &text, JFSavedSession *session) {
    FILE *file = tmpfile();
    assert(file);
    assert(fwrite(text.data(), 1, text.size(), file) == text.size());
    rewind(file);
    bool ok = jf_read_session(file, session);
    fclose(file);
    return ok;
}

int main() {
    char body[800];
    assert(jf_build_login_body("Jane Doe", "  a\"b\\c\n\t  ", body, sizeof(body)));
    assert(strcmp(body, "{\"Username\":\"Jane Doe\",\"Pw\":\"  a\\\"b\\\\c\\u000a\\u0009  \"}") == 0);
    assert(jf_build_login_body("Ren\xc3\xa9", "", body, sizeof(body)));
    assert(strcmp(body, "{\"Username\":\"Ren\xc3\xa9\",\"Pw\":\"\"}") == 0);
    std::string controls(63, '\x01');
    assert(jf_build_login_body(controls.c_str(), controls.c_str(), body, sizeof(body)));
    size_t needed = strlen(body) + 1;
    assert(jf_build_login_body(controls.c_str(), controls.c_str(), body, needed));
    assert(!jf_build_login_body(controls.c_str(), controls.c_str(), body, needed - 1));
    assert(body[0] == '\0');
    char sentinel = 'x';
    assert(!jf_build_login_body("x", "y", &sentinel, 0));
    assert(sentinel == 'x');

    JFSavedSession session = {};
    assert(read_config("http://server:8096/\nJane Doe\ntoken\nuser-id\n", &session));
    assert(strcmp(session.username, "Jane Doe") == 0);
    assert(strcmp(session.token, "token") == 0);
    assert(strcmp(session.server, "http://server:8096") == 0);
    assert(read_config("http://server/jellyfin/\r\nJane Doe\r\ntoken\r\nuser-id", &session));
    assert(strcmp(session.server, "http://server/jellyfin") == 0);
    assert(read_config("http://server\n" + std::string(63, 'a') + "\ntoken\nid\n", &session));
    assert(read_config("http://server\r\n" + std::string(63, 'a') + "\r\ntoken\r\nid\r\n", &session));
    JFSavedSession before = session;
    const std::string invalid[] = {
        "", "http://server\nname\ntoken\n", "http://server\nname\n\nid\n",
        "http://server\n" + std::string(64, 'a') + "\ntoken\nid\n",
        std::string("http://server\nna\0me\ntoken\nid\n", 29),
        "http://server\nname\n" + std::string(256, 't') + "\nid\n"
    };
    for (size_t i = 0; i < sizeof(invalid) / sizeof(invalid[0]); ++i) {
        assert(!read_config(invalid[i], &session));
        assert(memcmp(&session, &before, sizeof(session)) == 0);
    }
    JellopProfiles profiles=profile_default(),decoded=profile_default();
    char text[560],url[256];
    assert(profile_normalize_url("http://gateway:18796/",profiles.url[0],256));
    assert(profile_normalize_url("https://gateway.example:18797/malay/",profiles.url[1],256));
    assert(!strcmp(profiles.url[0],"http://gateway:18796"));
    profiles.pending=1;
    assert(profile_format(&profiles,text,sizeof text)>0);
    assert(profile_parse(text,&decoded));
    assert(decoded.pending==1&&!strcmp(decoded.url[1],profiles.url[1]));
    assert(profile_active(&decoded,"http://gateway:18796/")==0);
    assert(profile_active(&decoded,"http://gateway:18798")==-1);
    const char *bad_urls[]={"http://", "ftp://gateway","http://user@gateway",
        "http://gateway:0","http://gateway:65536","http://gateway:12x",
        "http://gateway/?token=x","http://gateway/#fragment",
        "http://gateway/a/../b","http://gateway/a%2fb","http://gateway\nbad",
        "http://[::1]:8096","http://gateway/a//b"};
    for(const char *bad:bad_urls)assert(!profile_normalize_url(bad,url,sizeof url));
    assert(!profile_parse("JELLOP-PROFILES-1\n1\nhttp://gateway\n\n",&decoded));
    assert(!profile_parse("JELLOP-PROFILES-1\n0\nhttp://gateway\nhttp://gateway\n",&decoded));
    assert(!profile_parse("JELLOP-PROFILES-1\n-1\n\n\nextra",&decoded));
    assert(decoded.pending==1&&!strcmp(decoded.url[1],profiles.url[1]));
    puts("auth_data: credential escaping, saved-session and gateway profile regressions passed");
}
