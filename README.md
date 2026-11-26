# Jellop

Jealousfin-compatible PlayStation 3 client.

Based on JellyFin [PS] for PS3 by jw-notes - https://github.com/jw-notes/JellyFin-PS3. The pinned source baseline is mghazalyh/JellyFin-PS3 at d71be13498e7888b3f12038e47a0c70d8c9974b0. Original LICENSE, NOTICE, CREDITS and per-component notices are retained when imported. Jellop modifications are GPL-3.0-or-later.

Development and builds use GitHub-hosted Linux runners only. No personal machines are used. No scheduled workflows.

The PS3 client is a thin, hardware-decoded MPEG-TS player. Server-side catalogue, programme titles, release years, transcoding and channel policy remain server responsibilities. Do not run a WebView, general scripting runtime, EPG scraper or software video transcoder on the PS3. Real hardware acceptance is required before declaring playback compatible.

The native source was imported from the pinned revision. GitHub Actions builds and verifies candidate packages. Initial package compilation passed; physical playback has not been accepted.

During Live TV playback, press L3 to start or pause/resume the opt-in 60-second Surf timer. The timer advances only on decoded frame progress, and the current page defines the rotation pool. O exits playback. Recently decoded channels are saved using the native recent-channel preferences. Four scoped rotation checkpoints now persist in the existing per-user save bundle; L3 in the Live TV list explicitly resumes the last eligible channel in that scope. Membership changes reset cycle bits safely while retaining the last channel and countdown when available. O stops without silently resuming on launch. Checkpoints are updated on transitions and every 15 seconds of active playback, and packed into the console save on normal exit. PS3 decoded-playback evidence is sent in the existing progress heartbeat and retained in a bounded authenticated bridge diagnostic ring. Global failure penalties remain deliberately disabled until source attribution is validated on hardware.

The optional `server/bridge.py` converts the existing gateway's HLS to bounded MPEG-TS. It is not deployed. See [bridge documentation](server/README.md).

Optional declarative runtime configuration is supported by the bridge. It is bounded by hard-coded native and server limits; no script engine is introduced. See `server/config.example.json` and the bridge documentation for revision-based rollback.

Native channel switching explicitly closes the previous bridge transcode using the existing Jellyfin stop endpoint. Session and token checks prevent unrelated sessions from stopping it.

## Storage and retry isolation

Jellop uses its own `/dev_hdd0/tmp/jellop` scratch directory, separate PS3 savedata identity, and `jellop_offline` media directories. It does not import the original application's temporary login or preferences. Login errors are logged as status codes only. Surf keeps the sole healthy channel instead of manufacturing cycle rollovers. Failed opens receive a five-minute local cooldown, never an automatic gateway ban. The existing native save-data fallback may lose scratch state after a reboot; permanent save failures are logged rather than claimed as successful.

For bridge-backed Live TV, the validated 720p output contract permits a compact 12-slot 720p decoded frame buffer instead of the ordinary 8-slot 1080p safety reserve. At macroblock-aligned dimensions this is 15.82 MiB versus 23.91 MiB (approximately 8.09 MiB saved). Oversize frames are still rejected before they can overwrite a slot. The decoder's existing HD setup and arena remain intact. Cached larger slots are reclaimed only when starting this bridge mode, not while decoding. The memory savings are theoretical until physical measurement.

## RPCS3 development

See [RPCS3 setup and source review](docs/RPCS3.md). A distinct emulator target preserves the existing RPCS3 renderer work without changing the default hardware target.

## Cross-client parity

Jealousfin and Jealouswin are the reference clients. Jellop's bridge now validates the full `sqlite-policy-v2` catalogue with exact identity membership, filters banned/hiatus channels, exposes an authenticated paginated excluded-channel view, and derives Sports and Movies & Series categories from server tags. Native rows retain bounded genre bits rather than complete tag lists. Malay media paths are accepted with the same token check. The actual PS3 does not load the Flutter website or execute web scripts. A separate public synthetic HLS fixture can be retrieved from Jealouswin Pages for GitHub-hosted testing; no private streams or credentials are published.

Live TV Options (START) now includes native brightness (-20 to +10, persisted), PCM mute without changing saved volume, and playback pause/resume. Media PLAY/PAUSE keys also work for Live TV; the existing live-watch logic reopens stale streams on resume. Brightness uses the existing inline GPU quad and does not allocate another framebuffer. The controller UI differs from touch/web sliders; visual and audible acceptance remain pending.

Live TV Options > Surf interval lets the user choose the server default, 15 or 30 seconds, or any whole-minute interval from 1 to 10 minutes. Preferences are atomically saved per PS3 user. Explicit changes reset the current dwell without resuming paused Surf, and survive channel changes. The PS3 keeps its existing 600-second native checkpoint limit rather than claiming the iOS client's 24-hour range.

Recent-channel history now retains thirty unique decoded channel IDs. Bounded batches of six are fetched using the existing worker buffer, avoiding overflow of the native 512-byte HTTP path and rejecting mismatched/duplicate server rows. The existing per-user storage cap is unchanged; host regressions cover all thirty maximum-length IDs and hidden preferences.

Live TV Options includes a Favourite toggle for the current channel. The request uses the authenticated server's shared favourite state and runs on a bounded on-demand worker rather than the video render thread. The UI changes the cached favourite flag only after a successful response, preserves active Surf membership, and refreshes the catalogue after playback. Physical controller acceptance is still required.

The optional bridge exposes a read-only native Hiatus / Banned category. The existing catalogue worker and buffers are reused; the page shows permanent bans or hiatus expiry in UTC. It is never a playback or Surf scope. The console retains its 384-channel resident cap and displays the server total if the exclusion list is longer. Ordinary Jellyfin servers without the endpoint keep the existing layout.
