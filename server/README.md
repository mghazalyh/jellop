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
