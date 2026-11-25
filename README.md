# Jellop

Jealousfin-compatible PlayStation 3 client.

Based on JellyFin [PS] for PS3 by jw-notes - https://github.com/jw-notes/JellyFin-PS3. The pinned source baseline is mghazalyh/JellyFin-PS3 at d71be13498e7888b3f12038e47a0c70d8c9974b0. Original LICENSE, NOTICE, CREDITS and per-component notices are retained when imported. Jellop modifications are GPL-3.0-or-later.

Development and builds use GitHub-hosted Linux runners only. No personal machines are used. No scheduled workflows.

The PS3 client is a thin, hardware-decoded MPEG-TS player. Server-side catalogue, programme titles, release years, transcoding and channel policy remain server responsibilities. Do not run a WebView, general scripting runtime, EPG scraper or software video transcoder on the PS3. Real hardware acceptance is required before declaring playback compatible.

The native source was imported from the pinned revision. GitHub Actions builds and verifies candidate packages. Initial package compilation passed; physical playback has not been accepted.

During Live TV playback, press L3 to start or pause/resume the opt-in 60-second Surf timer. The timer advances only on decoded frame progress, and the current page defines the rotation pool. O exits playback. Recently decoded channels are saved using the native recent-channel preferences. Four scoped rotation checkpoints now persist in the existing per-user save bundle; L3 in the Live TV list explicitly resumes the last eligible channel in that scope. Membership changes reset cycle bits safely while retaining the last channel and countdown when available. O stops without silently resuming on launch. Checkpoints are updated on transitions and every 15 seconds of active playback, and packed into the console save on normal exit. PS3 decoded-playback evidence is sent in the existing progress heartbeat and retained in a bounded authenticated bridge diagnostic ring. Global failure penalties remain deliberately disabled until source attribution is validated on hardware.

The optional `server/bridge.py` converts the existing gateway's HLS to bounded MPEG-TS. It is not deployed. See [bridge documentation](server/README.md).
