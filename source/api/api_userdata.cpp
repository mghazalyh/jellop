// Favourite and played: see api_userdata.h.

#include <stdio.h>
#include <string.h>
#include <sys/thread.h>

#include "api_userdata.h"
#include "userdata_request.h"
#include "jellyfin_api.h"
#include "plog.h"

static bool send_userdata(const UserDataRequest *r, const char *what, const char *id) {
    static char resp[2048];
    resp[0] = '\0';
    const int st = http_request(r->method, r->url, "", g_token, resp, sizeof resp);
    char msg[160];
    snprintf(msg, sizeof msg, "userdata: %s %.40s -> %d", what, id, st);
    plog(msg);
    return st >= 200 && st < 300;
}

bool jf_set_favourite(const char *item_id, bool favourite) {
    UserDataRequest r;
    if (!userdata_favourite_request(&r, g_server, g_userid, item_id, favourite)) return false;
    return send_userdata(&r, favourite ? "favourite" : "unfavourite", item_id);
}

bool jf_set_played(const char *item_id, bool played) {
    UserDataRequest r;
    if (!userdata_played_request(&r, g_server, g_userid, item_id, played)) return false;
    return send_userdata(&r, played ? "played" : "unplayed", item_id);
}

// Static storage outlives the player; only one request can be outstanding.
// Publication barriers protect the worker's input and result.
namespace {
enum { FAV_IDLE, FAV_RUNNING, FAV_READY };
struct FavouriteJob {
    volatile int state;
    UserDataRequest request;
    char server[256], user[64], token[256];
    JFFavouriteResult result;
};
FavouriteJob favourite_job = {};

void favourite_worker(void *) {
    char response[2048] = {};
    favourite_job.result.status = http_userdata_mutation(
        favourite_job.request.method, favourite_job.request.url,
        favourite_job.token, response, sizeof response);
    char line[128];
    snprintf(line, sizeof line, "userdata: fullscreen favourite %.40s -> %d",
             favourite_job.result.id, favourite_job.result.status);
    plog(line);
    __sync_synchronize();
    favourite_job.state = FAV_READY;
    sysThreadExit(0);
}
}

bool jf_favourite_async_pending(void) {
    return favourite_job.state != FAV_IDLE;
}

bool jf_favourite_async_start(const char *id, bool favourite) {
    if (jf_favourite_async_pending() || !g_token[0] ||
        !userdata_favourite_request(&favourite_job.request, g_server, g_userid, id, favourite))
        return false;
    snprintf(favourite_job.server, sizeof favourite_job.server, "%s", g_server);
    snprintf(favourite_job.user, sizeof favourite_job.user, "%s", g_userid);
    snprintf(favourite_job.token, sizeof favourite_job.token, "%s", g_token);
    snprintf(favourite_job.result.id, sizeof favourite_job.result.id, "%s", id);
    favourite_job.result.favourite = favourite;
    favourite_job.result.status = -1;
    favourite_job.state = FAV_RUNNING;
    __sync_synchronize();
    sys_ppu_thread_t tid;
    if (sysThreadCreate(&tid, favourite_worker, NULL, 1100, 32 * 1024, 0, "jf_favourite") != 0) {
        memset(favourite_job.token, 0, sizeof favourite_job.token);
        favourite_job.state = FAV_IDLE;
        plog("userdata: favourite worker creation failed");
        return false;
    }
    return true;
}

bool jf_favourite_async_take(JFFavouriteResult *out) {
    if (!out || favourite_job.state != FAV_READY) return false;
    __sync_synchronize();
    const bool same = !strcmp(favourite_job.server, g_server) &&
                      !strcmp(favourite_job.user, g_userid) &&
                      !strcmp(favourite_job.token, g_token);
    *out = favourite_job.result;
    memset(favourite_job.token, 0, sizeof favourite_job.token);
    __sync_synchronize();
    favourite_job.state = FAV_IDLE;
    if (same && out->status == 401) g_auth_expired = true;
    return same;
}
