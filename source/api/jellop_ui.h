#pragma once
#include "livetv.h"
#include "livetv_prefs.h"

// IPTV category ordering shared with Jealousfin and Jealouswin. No inferred
// channel-number categories; keep the native recent-history extension.
inline int jellop_ui_categories(int *keys, int cap, bool policy) {
    if (!keys || cap < 0) return 0;
    const int ordered[] = {1, LP_FAVS, LP_GENRE(LG_SPORTS),
                           LP_GENRE(LG_MOVIES), -3, LP_RECENT};
    int n = 0;
    for (unsigned i = 0; i < sizeof ordered / sizeof ordered[0]; ++i) {
        if (ordered[i] == -3 && !policy) continue;
        if (n >= cap) break;
        keys[n++] = ordered[i];
    }
    return n;
}
