"""Local-only synthetic IPTV gateway for the graphical RPCS3 test."""
import contextlib
import http.server
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import urllib.parse
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"server"))
import bridge
from config import DEFAULT

TOKEN="fixture-token"
USER="1"*32
CHANNELS=["a"*32,"b"*32]
RID="c"*32

class Gateway(http.server.BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def send_data(self,data,status=200,mime="application/json"):
        if not isinstance(data,bytes): data=json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type",mime)
        self.send_header("Content-Length",str(len(data)))
        self.end_headers()
        try:self.wfile.write(data)
        except (BrokenPipeError,ConnectionResetError): pass
    def do_GET(self):
        path=urllib.parse.urlsplit(self.path).path
        if path.startswith("/media/"+TOKEN+"/"):
            name=path.rsplit("/",1)[-1]
            if name not in self.server.media: return self.send_data({},404)
            return self.send_data((self.server.root/name).read_bytes(),mime="application/vnd.apple.mpegurl" if name.endswith(".m3u8") else "video/mp2t")
        if path=="/System/Info/Public":
            return self.send_data({"ServerName":"Jellop CI fixture","Version":"10.11.0","Id":"f"*32})
        if self.headers.get("X-Emby-Token")!=TOKEN:return self.send_data({},401)
        now=int(time.time())
        programs=[{"Id":str(i+3)*32,"ChannelId":cid,"Name":"Fixture Film "+str(i+1)+" (2020)",
                   "JealousfinProgramme":{"source":"provider-catalogue","observedAt":now}} for i,cid in enumerate(CHANNELS)]
        if path=="/LiveTv/Channels":
            return self.send_data({"Items":[{"Id":cid,"Name":"Fixture "+str(i+1),"Number":str(i+1),
                "UserData":{"IsFavorite":False},"CurrentProgram":programs[i]} for i,cid in enumerate(CHANNELS)]})
        if path=="/LiveTv/Programs":return self.send_data({"Items":programs})
        if path=="/LiveTv/Recordings":return self.send_data({"Items":[]})
        return self.send_data({},404)
    def do_POST(self):
        path=urllib.parse.urlsplit(self.path).path
        size=int(self.headers.get("Content-Length","0"))
        if size>65536:return self.send_data({},413)
        if size:self.rfile.read(size)
        if path=="/Users/AuthenticateByName":
            return self.send_data({"AccessToken":TOKEN,"User":{"Id":USER,"Name":"fixture"}})
        if self.headers.get("X-Emby-Token")!=TOKEN:return self.send_data({},401)
        for cid in CHANNELS:
            if path=="/Items/"+cid+"/PlaybackInfo":
                import uuid
                return self.send_data({"PlaySessionId":uuid.uuid4().hex,
                    "MediaSources":[{"TranscodingUrl":"/media/"+TOKEN+"/"+RID+".m3u8"}]})
        if path.startswith("/Sessions/") or path=="/LiveStreams/Close":return self.send_data({})
        return self.send_data({},404)

@contextlib.contextmanager
def fixture():
    with tempfile.TemporaryDirectory(prefix="jellop-fixture-") as d:
        root=Path(d)
        subprocess.run(["ffmpeg","-v","error","-y","-f","lavfi","-i","testsrc2=size=640x360:rate=24",
            "-f","lavfi","-i","sine=frequency=440:sample_rate=48000","-t","90",
            "-c:v","libx264","-preset","ultrafast","-pix_fmt","yuv420p","-threads","2","-g","48",
            "-c:a","aac","-f","hls","-hls_time","2","-hls_list_size","0",
            "-hls_segment_filename",str(root/"seg%03d.ts"),str(root/(RID+".m3u8"))],check=True,timeout=120)
        upstream=http.server.ThreadingHTTPServer(("127.0.0.1",0),Gateway)
        upstream.root=root
        upstream.media={p.name for p in root.iterdir()}
        cfg=root/"config.json"
        cfg.write_text(json.dumps(dict(DEFAULT,surfDwellSeconds=15,maxWidth=640,maxHeight=360,maxVideoBitrate=1000000)))
        b=bridge.Bridge("http://127.0.0.1:"+str(upstream.server_port),config_path=str(cfg))
        original=bridge.ffmpeg_args
        def paced(*args,**kwargs):
            cmd=original(*args,**kwargs);cmd.insert(cmd.index("-i"),"-re");return cmd
        bridge.ffmpeg_args=paced
        server=bridge.Server(("127.0.0.1",18096),b)
        threads=[threading.Thread(target=x.serve_forever,daemon=True) for x in (upstream,server)]
        for t in threads:t.start()
        try:yield b
        finally:
            for x in (server,upstream):x.shutdown();x.server_close()
            bridge.ffmpeg_args=original
