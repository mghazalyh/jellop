"""Actual HTTPS deployment + bridge transport acceptance, on a GitHub runner."""
import json
from pathlib import Path
import subprocess
import tempfile
import urllib.request
import urllib.error
from rpcs3_fixture import fixture, TOKEN, USER, CHANNELS, EXCLUDED

def main():
    with fixture() as b, tempfile.TemporaryDirectory() as d:
        base="http://127.0.0.1:18096"
        hdr={"Authorization":'MediaBrowser Client="PS3", Token="'+TOKEN+'"'}
        def call(path,body=None):
            req=urllib.request.Request(base+path,data=body,headers=hdr)
            with urllib.request.urlopen(req,timeout=20) as r:return json.load(r)
        assert call("/Users/"+USER+"/Views")["Items"][0]["CollectionType"]=="livetv"
        rows=call("/LiveTv/Channels?Limit=25")["Items"]
        assert {r["Id"] for r in rows}==set(CHANNELS)
        assert {r["JellopGenreMask"] for r in rows}=={2,4}
        assert {r["Id"] for r in call("/Jellop/ChannelPolicy")["Items"]}==set(EXCLUDED)
        for cid in EXCLUDED:
            try:call("/Items/"+cid+"/PlaybackInfo",b"{}")
            except urllib.error.HTTPError as e:assert e.code==409
            else:raise AssertionError("Excluded channel was opened")
        for cid in CHANNELS:
            info=call("/Items/"+cid+"/PlaybackInfo",b"{}")
            out=Path(d)/(cid+".ts")
            url=base+"/Videos/"+cid+"/stream.ts?PlaySessionId="+info["PlaySessionId"]
            with urllib.request.urlopen(urllib.request.Request(url,headers=hdr),timeout=40) as r,out.open("wb") as f:
                while f.tell()<188*3000:
                    chunk=r.read(188*256)
                    if not chunk:break
                    f.write(chunk)
            probe=subprocess.run(["ffprobe","-v","error","-show_streams","-of","json",str(out)],check=True,capture_output=True,timeout=20)
            streams=json.loads(probe.stdout)["streams"]
            assert any(s["codec_name"]=="h264" and s["width"]<=1280 and s["height"]<=720 for s in streams)
            assert any(s["codec_name"]=="mp3" and s["channels"]==2 for s in streams)
            req=urllib.request.Request(base+"/Videos/ActiveEncodings?PlaySessionId="+info["PlaySessionId"],headers=hdr,method="DELETE")
            with urllib.request.urlopen(req,timeout=10) as r:assert r.status==200
            print("Verified deployed media -> authenticated bridge -> H.264/MP3 MPEG-TS",cid,flush=True)
if __name__=="__main__":main()
