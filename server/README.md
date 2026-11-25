# Jellop IPTV bridge

Optional server-side compatibility service for the existing Jealousfin IPTV gateway. It does not run on the PS3 and does not replace the production gateway. The native client can still use a normal Jellyfin server.

Run with Python 3 and FFmpeg (libx264 and libmp3lame support) on a separately authorized server:

```sh
python3 server/bridge.py --upstream http://YOUR-GATEWAY:PORT --bind 127.0.0.1 --port 18800
```

The default listener is loopback only. To use on a console, an operator must intentionally bind to an appropriate private network interface and restrict access with the host firewall; HTTP is not encrypted. Configure the PS3 with the bridge origin, and authenticate with the existing gateway credentials. No credentials are stored in source or printed to application logs. This source is not deployed.

Limits: one active transcode, 12 concurrent handlers, 100 rows per HTTP page, 2 MiB upstream JSON maximum, 48 KiB streaming reads, two recent catalogue snapshots, 16 one-use stream resolutions, 720p30 maximum, up to 4 Mbps video, stereo MP3 128 kbps. Actual decoder compatibility and CPU costs need measurement. The transcoder runs on a server, not the console.

The bridge delegates authentication, eligibility, programme data, favorites and session reporting to the gateway. It does not modify channel hiatus or mark server-side delivery as decoded playback success. Native PS3 rotation and decoded failure telemetry are separate future integration work. No periodic or scheduled tasks are installed.

The GitHub-hosted integration test creates a synthetic HLS stream, serves it from a temporary fixture gateway, and probes the adapter's actual MPEG-TS output. It never contacts the production service. The upstream gateway resource URL is passed to the server-side FFmpeg process, so the server operator must also restrict local process inspection to trusted users.

Authenticated `GET /Jellop/Diagnostics` returns at most 24 session records, filtered to the requesting token. Native frame progress, decoded milliseconds, stalls, ring occupancy and free main memory ride on the existing progress request (no additional polling thread). A sustained result requires at least 60 seconds of coherent progress samples; downloaded bytes alone never qualify. Source vs console vs transcoder failure attribution is deliberately not automated into gateway penalties. No policy mutation is performed.

## Bounded runtime configuration

An optional `--config /path/to/config.json` loads the example schema on playback requests. Change the revision monotonically and replace the file atomically. Invalid, oversized, duplicate-key, out-of-range or older revisions preserve the last accepted configuration while the process runs. To roll back, restore previous values with a new higher revision. Config controls Surf dwell (15–600 seconds), requested native ring cap (2–6 MiB), and server output ceilings (up to 720p/4 Mbps). No executable patches, polling process or scheduled task. Native ring sizing applies at the next full playback start; dwell and server output ceilings apply on the next channel open. Default behavior remains unchanged if no config is supplied. `GET /Jellop/Config` is authenticated and reports accepted values and fault state.
