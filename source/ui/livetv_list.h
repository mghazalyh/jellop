#pragma once
#include "livetv.h"

// The Live TV tab's channel list in display order (xmb/ui_livetv.cpp), for the
// player's channel up/down.  Render thread only.
int  xmb_livetv_count(void);
bool xmb_livetv_get(int index, JFChannel *out);
int  xmb_livetv_index_of(const char *channel_id);

// Record a decoded channel without rebuilding the active page.
void xmb_livetv_record_played(const char *channel_id);

struct SurfStore;
uint64_t xmb_livetv_surf_scope(void);
bool xmb_livetv_surf_requested(void);
bool xmb_livetv_surf_load(SurfStore *store);
bool xmb_livetv_surf_save(const SurfStore *store);

// Consume a completed fullscreen favourite request on the render thread.
// Returns 1 for success, -1 for failure, or 0 if no result is ready.
int xmb_livetv_favourite_result(void);

// Emulator-only, armed by the authenticated fixture driver.
#if BUILD_FOR_RPCS3
bool xmb_livetv_smoke_active(void);
#endif
