// Host test for the favourite / played request builders
// (source/api/userdata_request.h): the method and the path, and what is
// refused.
//
//   make -f Makefile.host test_userdata && ./test_userdata
#include <stdio.h>
#include <string.h>

#include "userdata_request.h"

static int s_checks = 0, s_failed = 0;
#define CHECK(cond) do { s_checks++; if (!(cond)) { s_failed++; \
    printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); } } while (0)

int main(void) {
    const char *srv = "http://10.0.0.5:8096";
    const char *uid = "u0123abcd";
    const char *item = "0123456789abcdef0123456789abcdef";
    UserDataRequest r;

    // Favourite: POST; unfavourite: DELETE; the same path.
    CHECK(userdata_favourite_request(&r, srv, uid, item, true));
    CHECK(r.method == HTTP_POST);
    CHECK(!strcmp(r.url, "http://10.0.0.5:8096/Users/u0123abcd/FavoriteItems/0123456789abcdef0123456789abcdef"));
    CHECK(userdata_favourite_request(&r, srv, uid, item, false));
    CHECK(r.method == HTTP_DELETE);
    CHECK(!strcmp(r.url, "http://10.0.0.5:8096/Users/u0123abcd/FavoriteItems/0123456789abcdef0123456789abcdef"));

    // A queued request is a complete account-bound value: subsequent
    // changes to another user's request cannot redirect the first one.
    UserDataRequest queued = r;
    CHECK(userdata_favourite_request(&r, "http://10.0.0.5:18797", "another-user", item, true));
    CHECK(queued.method == HTTP_DELETE);
    CHECK(!strcmp(queued.url, "http://10.0.0.5:8096/Users/u0123abcd/FavoriteItems/0123456789abcdef0123456789abcdef"));
    CHECK(r.method == HTTP_POST);
    CHECK(strstr(r.url, ":18797/Users/another-user/") != NULL);

    // A bounded request must reject a URL that cannot fit.
    char large_server[512];
    memset(large_server, 'a', sizeof large_server - 1);
    large_server[sizeof large_server - 1] = '\0';
    CHECK(!userdata_favourite_request(&r, large_server, uid, item, true));

    // Played: the same shape on its own collection.
    CHECK(userdata_played_request(&r, srv, uid, item, true));
    CHECK(r.method == HTTP_POST && strstr(r.url, "/PlayedItems/") != NULL);
    CHECK(userdata_played_request(&r, srv, uid, item, false));
    CHECK(r.method == HTTP_DELETE);

    // Nothing that could rewrite the path or add a query goes in.
    CHECK(!userdata_favourite_request(&r, srv, uid, "../Items", true));
    CHECK(!userdata_favourite_request(&r, srv, uid, "abc?x=1", true));
    CHECK(!userdata_favourite_request(&r, srv, uid, "a/b", true));
    CHECK(!userdata_favourite_request(&r, srv, uid, "", true));
    CHECK(!userdata_favourite_request(&r, srv, uid, NULL, true));
    CHECK(!userdata_favourite_request(&r, srv, "bad user", item, true));
    CHECK(!userdata_favourite_request(&r, "", uid, item, true));
    CHECK(!userdata_favourite_request(&r, NULL, uid, item, true));
    // An id too long for the path buffer's sanity limit is refused too.
    char longid[80];
    memset(longid, 'a', sizeof longid - 1);
    longid[sizeof longid - 1] = '\0';
    CHECK(!userdata_favourite_request(&r, srv, uid, longid, true));

    printf("userdata requests: %d checks, %d failed\n", s_checks, s_failed);
    return s_failed ? 1 : 0;
}
