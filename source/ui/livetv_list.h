#pragma once
#include "livetv.h"

// The Live TV tab's channel list in display order (xmb/ui_livetv.cpp), for the
// player's channel up/down.  Render thread only.
int  xmb_livetv_count(void);
bool xmb_livetv_get(int index, JFChannel *out);
int  xmb_livetv_index_of(const char *channel_id);

// Record a decoded channel without rebuilding the active page.
void xmb_livetv_record_played(const char *channel_id);
