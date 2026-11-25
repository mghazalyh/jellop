"""End-to-end fixture; no external services, accounts or private hosts."""
import contextlib
import http.server
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from bridge import Bridge, Server, STREAM_CHUNK

TOKEN="fixture-token"
CID="a"*32
SID="b"*32
RID="c"*32
MEDIA="/media/"+TOKEN+"/"
PREFIX=MEDIA+RID+".m3u8"

@contextlib.contextmanager
def running(server):
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:yield "http://127.0.0.1:"+str(server.server_port)
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)

class PipelineTests(unittest.TestCase):
    def test_fixture_hls_to_actual_mpeg_ts(self):
        self.assertTrue(shutil.which("ffmpeg"),"ffmpeg is required for the integration gate")
        self.assertTrue(shutil.which("ffprobe"),"ffprobe is required for the integration gate")
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            subprocess.run(["ffmpeg","-v","error","-y","-f","lavfi","-i","testsrc2=size=640x360:rate=24",
                "-f","lavfi","-i","sine=frequency=440:sample_rate=48000","-t","3",
                "-c:v","libx264","-pix_fmt","yuv420p","-threads","2","-g","24",
                "-c:a","aac","-f","hls","-hls_time","1","-hls_list_size","0",
                "-hls_segment_filename",str(root/"seg%03d.ts"),str(root/(RID+".m3u8"))],
                check=True,timeout=45,capture_output=True)
            attempts=[]
            class Gateway(http.server.BaseHTTPRequestHandler):
                def log_message(self,*args):pass
                def response(self,status,data,mime="application/json"):
                    if not isinstance(data,bytes):data=json.dumps(data).encode()
                    self.send_response(status);self.send_header("Content-Type",mime)
                    self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data)
                def do_GET(self):
                    if self.path.startswith(MEDIA):
                        name=self.path[len(MEDIA):]
                        if name not in {p.name for p in root.glob("*.ts")} | {RID+".m3u8"}:
                            self.response(404,{});return
                        self.response(200,(root/name).read_bytes(),"application/vnd.apple.mpegurl" if name.endswith(".m3u8") else "video/mp2t");return
                    if self.headers.get("X-Emby-Token")!=TOKEN:self.response(401,{});return
                    if self.path=="/LiveTv/Channels":
                        self.response(200,{"Items":[{"Id":CID,"Name":"Fixture"}]})
                    else:self.response(404,{})
                def do_POST(self):
                    n=int(self.headers.get("Content-Length","0"))
                    if n:self.rfile.read(n)
                    if self.headers.get("X-Emby-Token")!=TOKEN:self.response(401,{});return
                    if self.path=="/Items/"+CID+"/PlaybackInfo":
                        attempts.append(CID)
                        self.response(200,{"PlaySessionId":SID,"MediaSources":[{"TranscodingUrl":PREFIX}]})
                    else:self.response(404,{})
            with running(http.server.ThreadingHTTPServer(("127.0.0.1",0),Gateway)) as upstream:
                b=Bridge(upstream)
                with running(Server(("127.0.0.1",0),b)) as bridge:
                    hdr={"X-Emby-Token":TOKEN}
                    req=urllib.request.Request(bridge+"/Items/"+CID+"/PlaybackInfo",data=b"{}",headers=hdr)
                    with urllib.request.urlopen(req,timeout=15) as r:
                        info=json.load(r)
                    self.assertEqual(info["PlaySessionId"],SID)
                    self.assertNotIn(TOKEN,json.dumps(info))
                    endpoint=bridge+"/Videos/"+CID+"/stream.ts?PlaySessionId="+SID+"&MaxWidth=320&MaxHeight=180&VideoBitrate=800000"
                    out=root/"output.mpegts"
                    with urllib.request.urlopen(urllib.request.Request(endpoint,headers=hdr),timeout=45) as r, out.open("wb") as f:
                        self.assertEqual(r.headers.get_content_type(),"video/mp2t")
                        total=0
                        while True:
                            chunk=r.read(STREAM_CHUNK)
                            if not chunk:break
                            total+=len(chunk)
                            self.assertLess(total,4*1024*1024)
                            f.write(chunk)
                    self.assertGreater(total,188*30)
                    self.assertEqual(attempts,[CID],"single upstream resolution per actual playback")
                    probe=subprocess.run(["ffprobe","-v","error","-show_streams","-of","json",str(out)],capture_output=True,check=True,timeout=20)
                    streams=json.loads(probe.stdout)["streams"]
                    video=next(s for s in streams if s["codec_type"]=="video")
                    audio=next(s for s in streams if s["codec_type"]=="audio")
                    self.assertEqual(video["codec_name"],"h264")
                    self.assertLessEqual(video["width"],320)
                    self.assertLessEqual(video["height"],180)
                    self.assertEqual(video["pix_fmt"],"yuv420p")
                    self.assertEqual(audio["codec_name"],"mp3")
                    self.assertEqual(audio["channels"],2)
                    self.assertEqual(audio["sample_rate"],"48000")
                    with self.assertRaises(urllib.error.HTTPError) as error:
                        urllib.request.urlopen(urllib.request.Request(bridge+"/Videos/"+("d"*32)+"/stream.ts",headers=hdr),timeout=10)
                    self.assertEqual(error.exception.code,409)
                    self.assertTrue(b.transcode.acquire(blocking=False),"transcode slot released")
                    b.transcode.release()
if __name__=="__main__":unittest.main()
