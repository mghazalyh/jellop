"""Jellop IPTV compatibility bridge. Runs on a server, never on the PS3.

Expose a small Jellyfin-shaped API and turn an authorized gateway HLS source
into a bounded H.264 + stereo MP3 MPEG-TS stream. No shared policy mutations.
"""
import argparse
import hmac
import http.server
import json
import os
import re
import selectors
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.parse as url
import urllib.request as request
from collections import OrderedDict
from config import Config, DEFAULT

MAX_JSON = 2 * 1024 * 1024
MAX_BODY = 64 * 1024
MAX_CATALOGUE = 2048
MAX_PAGE = 100
MAX_HANDLERS = 12
STREAM_CHUNK = 188 * 256
ID = r"[0-9a-fA-F]{32}"
ITEM = re.compile(r"/Users/([^/]+)/Items/("+ID+r")")
PLAYBACK = re.compile(r"/Items/("+ID+r")/PlaybackInfo")
STREAM = re.compile(r"/Videos/("+ID+r")/stream\.ts")
FAVORITE = re.compile(r"/Users/([^/]+)/FavoriteItems/("+ID+r")")
LIVE_VIEW = "00000000000000000000000000000001"

class Failure(Exception):
    def __init__(self, status, code):
        self.status, self.code = status, code
        super().__init__(code)

class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def first(q, key, default=""):
    return q.get(key.casefold(), [default])[0]

def number(q, key, default, low, high):
    try: n = int(first(q, key, str(default)))
    except (ValueError, TypeError): n = default
    return max(low, min(high, n))

def client_token(headers, q):
    token = headers.get("X-Emby-Token", "") or first(q, "api_key")
    if not token:
        for key in ("Authorization", "X-Emby-Authorization"):
            m = re.search(r'(?:^|[ ,])Token="([^"\r\n]+)"', headers.get(key, ""), re.I)
            if m:
                token = m.group(1)
                break
    if not token or len(token)>512 or not re.fullmatch(r"[A-Za-z0-9_.~-]+", token):
        raise Failure(401,"authentication-required")
    return token

def origin(value):
    p = url.urlsplit(value)
    if p.scheme not in ("http","https") or not p.hostname or p.username or p.password or p.path not in ("","/") or p.query or p.fragment:
        raise ValueError("Upstream must be a trusted HTTP(S) origin")
    return p.scheme+"://"+p.netloc

def page_rows(rows,q):
    start = number(q,"StartIndex",0,0,MAX_CATALOGUE)
    limit = number(q,"Limit",25,1,MAX_PAGE)
    return {"Items":rows[start:start+limit],"TotalRecordCount":len(rows)}

def filtered_channels(rows,q):
    term = first(q,"SearchTerm").casefold()
    ids = set(first(q,"Ids").split(",")) if first(q,"Ids") else None
    fav = first(q,"IsFavorite").casefold()=="true" or "isfavorite" in first(q,"Filters").casefold().split(",")
    result = []
    for row in rows:
        if not isinstance(row,dict) or not re.fullmatch(ID,str(row.get("Id",""))): continue
        if ids is not None and row["Id"] not in ids: continue
        if term and term not in str(row.get("Name","")).casefold(): continue
        if fav and not (row.get("UserData") or {}).get("IsFavorite"): continue
        # No poster fetches for IPTV. CurrentProgram is kept as received.
        item = {k:row[k] for k in ("Id","Name","Number","ChannelNumber","UserData","CurrentProgram") if k in row}
        item["Type"]="TvChannel"
        item["IsFolder"]=False
        if first(q,"AddCurrentProgram").casefold()=="false":
            item.pop("CurrentProgram",None)
        result.append(item)
    return sorted(result,key=lambda x:(str(x.get("Name","")).casefold(),x["Id"]))

def hls_url(base,path,token):
    # Gateway-generated resource identifiers are opaque and authorization-bound.
    # Never accept client-provided input URLs, redirects or a different origin.
    p = url.urlsplit(path)
    if p.scheme or p.netloc or p.query or p.fragment:
        raise Failure(502,"invalid-upstream-media-path")
    m = re.fullmatch(r"/media/([A-Za-z0-9_.~-]+)/([a-f0-9]{32})\.m3u8",p.path)
    if not m or not hmac.compare_digest(m[1],token):
        raise Failure(502,"invalid-upstream-media-path")
    return base+p.path

def media_source(cid):
    return {"Id":cid,"Name":"Jellop Live TV","Container":"ts",
            "SupportsDirectPlay":False,"SupportsDirectStream":False,
            "SupportsTranscoding":True,"IsRemote":True,
            "MediaStreams":[{"Type":"Video","Index":0,"Codec":"h264"},
                            {"Type":"Audio","Index":1,"Codec":"mp3","Channels":2,
                             "SampleRate":48000,"IsDefault":True}]}

def ffmpeg_args(binary,source,q,config=None):
    config=DEFAULT if config is None else config
    # The client may request 1080p or higher bitrates; the bridge clamps the
    # actual output to 720p30 and 4 Mbps video (with bounded audio).
    width=number(q,"MaxWidth",1280,320,config["maxWidth"])
    height=number(q,"MaxHeight",720,180,config["maxHeight"])
    width-=width%2; height-=height%2
    rate=number(q,"VideoBitrate",3500000,500000,config["maxVideoBitrate"])
    return [binary,"-nostdin","-hide_banner","-loglevel","error",
            "-rw_timeout","12000000","-protocol_whitelist","http,https,tcp,tls,crypto",
            "-i",source,"-map","0:v:0","-map","0:a:0?",
            "-vf",f"scale=w={width}:h={height}:force_original_aspect_ratio=decrease:force_divisible_by=2,fps=30",
            "-c:v","libx264","-profile:v","high","-level:v","4.1",
            "-preset","veryfast","-tune","zerolatency","-pix_fmt","yuv420p",
            "-threads","2","-filter_threads","1","-g","60","-bf","0",
            "-b:v",str(rate),"-maxrate",str(rate),"-bufsize",str(rate*2),
            "-c:a","libmp3lame","-ac","2","-ar","48000","-b:a","128k",
            "-f","mpegts","-mpegts_flags","+resend_headers","-flush_packets","1","pipe:1"]

class ActiveStream:
    """One slot, owned by exactly one authenticated session."""
    def __init__(self,token,cid,requested,sock):
        self.token,self.cid,self.requested=token,cid,requested
        self.sid=""
        self.sock=sock
        self.proc=None
        self.lock=threading.Lock()
        self.cancelled=threading.Event()
        self.done=threading.Event()

    def attach(self,proc):
        with self.lock:
            self.proc=proc
            if self.cancelled.is_set():
                try:proc.terminate()
                except OSError:pass
                return False
            return True

    def cancel(self):
        self.cancelled.set()
        with self.lock:
            if self.proc is not None:
                try:self.proc.terminate()
                except OSError:pass
            try:self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:pass


class Bridge:
    def __init__(self,upstream,binary="ffmpeg",config_path=None):
        self.base=origin(upstream)
        self.config=Config(config_path)
        self.binary=binary
        self.opener=request.build_opener(NoRedirect(),request.ProxyHandler({}))
        self.lock=threading.Lock()
        self.catalogues=OrderedDict()
        self.sessions=OrderedDict()
        self.evidence=OrderedDict()
        self.active=None
        self.transcode=threading.BoundedSemaphore(1)

    def upstream(self,path,token="",method="GET",body=None):
        headers={"Accept":"application/json"}
        if token:headers["X-Emby-Token"]=token
        if body is not None:headers["Content-Type"]="application/json"
        req=request.Request(self.base+path,data=body,headers=headers,method=method)
        try:
            with self.opener.open(req,timeout=12) as resp:
                raw=resp.read(MAX_JSON+1)
            if len(raw)>MAX_JSON:raise Failure(502,"upstream-reply-too-large")
            return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            raise Failure(e.code if e.code in (400,401,403,404,409,429,503) else 502,"upstream-http-"+str(e.code)) from None
        except (OSError,ValueError) as e:
            raise Failure(502,"upstream-unavailable") from None

    def catalogue(self,token,fresh=False):
        now=time.monotonic()
        with self.lock:
            cached=self.catalogues.get(token)
            if cached and not fresh and now-cached[0]<10:return cached[1]
        data=self.upstream("/LiveTv/Channels",token)
        rows=data.get("Items") if isinstance(data,dict) else None
        if not isinstance(rows,list) or len(rows)>MAX_CATALOGUE:
            raise Failure(502,"invalid-upstream-catalogue")
        with self.lock:
            self.catalogues[token]=(now,rows)
            self.catalogues.move_to_end(token)
            while len(self.catalogues)>2:self.catalogues.popitem(last=False)
        return rows

    def eligible(self,token,cid):
        # The authoritative gateway filters its legacy catalogue.
        rows=self.catalogue(token,fresh=True)
        if not any(isinstance(r,dict) and r.get("Id")==cid for r in rows):
            raise Failure(409,"channel-not-eligible")

    def resolve(self,token,cid,session="",auto=True):
        self.eligible(token,cid)
        if not auto:
            import uuid
            return uuid.uuid4().hex,""
        now=time.monotonic()
        if session:
            with self.lock:
                record=self.sessions.pop((token,cid,session),None)
            if record and now-record[0]<45:return session,record[1]
        data=self.upstream("/Items/"+cid+"/PlaybackInfo",token,"POST",b"{}")
        try:
            sid=data["PlaySessionId"]
            if not re.fullmatch(ID,sid):raise ValueError()
            source=hls_url(self.base,data["MediaSources"][0]["TranscodingUrl"],token)
        except (KeyError,TypeError,IndexError,ValueError):
            raise Failure(502,"invalid-upstream-playback-info") from None
        return sid,source

    def remember(self,token,cid,sid,source):
        if not source:return
        with self.lock:
            self.sessions[(token,cid,sid)]=(time.monotonic(),source)
            self.sessions.move_to_end((token,cid,sid))
            while len(self.sessions)>16:self.sessions.popitem(last=False)

    def claim_stream(self,token,cid,requested,sock):
        if not self.transcode.acquire(blocking=False):
            raise Failure(503,"transcode-capacity")
        control=ActiveStream(token,cid,requested,sock)
        with self.lock:self.active=control
        return control

    def release_stream(self,control):
        with self.lock:
            if self.active is control:self.active=None
        self.transcode.release()
        control.done.set()

    def stop_stream(self,token,sid):
        if not re.fullmatch(ID,sid):raise Failure(400,"invalid-session")
        with self.lock:
            for key in list(self.sessions):
                if key[0]==token and key[2]==sid:self.sessions.pop(key)
            current=self.active
            if not current or current.token!=token or sid not in (current.sid,current.requested):
                return {}
        current.cancel()
        if not current.done.wait(timeout=5):
            raise Failure(503,"transcode-stop-pending")
        return {}

    def stream_started(self,token,cid,sid):
        with self.lock:
            key=(token,cid,sid)
            self.evidence[key]={"active":True,"opened":time.monotonic(),"samples":0,
                                "sustained":False,"last":None,"run_seconds":0.0}
            self.evidence.move_to_end(key)
            while len(self.evidence)>24:self.evidence.popitem(last=False)

    def stream_finished(self,token,cid,sid,reason):
        with self.lock:
            row=self.evidence.get((token,cid,sid))
            if row:row.update(active=False,outcome=reason)

    def report_evidence(self,token,data):
        if not isinstance(data,dict):return
        e=data.get("JellopEvidence")
        cid,sid=data.get("ItemId"),data.get("PlaySessionId")
        if not isinstance(cid,str) or not isinstance(sid,str) or not re.fullmatch(ID,cid) or not re.fullmatch(ID,sid):
            return
        if not isinstance(e,dict) or e.get("Version")!=1:return
        fields=("Frames","DecodedMs","Stalls","FreeKiB","RingPackets","RingCapacity")
        if any(type(e.get(k)) is not int or not 0<=e[k]<=0xffffffff for k in fields):return
        if e["RingPackets"]>e["RingCapacity"] or e["RingCapacity"]>40000:return
        if type(data.get("IsPaused")) is not bool:return
        now=time.monotonic()
        sample={k:e[k] for k in fields}
        sample["paused"]=data["IsPaused"];sample["at"]=now
        with self.lock:
            row=self.evidence.get((token,cid,sid))
            if not row or not row["active"]:return
            # This is evidence of displayed frame progress, not merely
            # downloaded bytes. A delayed/duplicated/reset sample is not
            # credited. Local decode stalls do not mutate global policy.
            last=row["last"]
            if last:
                dt=now-last["at"]
                frames=sample["Frames"]-last["Frames"]
                decoded=sample["DecodedMs"]-last["DecodedMs"]
                if dt<2:return
                if (dt<=25 and not sample["paused"] and not last["paused"] and
                    sample["Stalls"]==last["Stalls"] and dt*8<=frames<=dt*65 and
                    dt*500<=decoded<=dt*1200):
                    row["run_seconds"]+=min(dt,decoded/1000)
                else:row["run_seconds"]=0.0
            row["samples"]+=1
            row["last"]=sample
            if row["run_seconds"]>=60:row["sustained"]=True

    def diagnostics(self,token):
        self.catalogue(token,fresh=True)
        with self.lock:
            return {"Sessions":[{"ChannelId":cid,"PlaySessionId":sid,
                    "Active":r["active"],"Samples":r["samples"],"Sustained":r["sustained"],
                    "HealthySeconds":round(r["run_seconds"],2),"Outcome":r.get("outcome","playing"),
                    "Last":{k:v for k,v in (r["last"] or {}).items() if k!="at"}}
                for (owner,cid,sid),r in self.evidence.items() if owner==token],
                "PolicyMutation":False}

    def dispatch(self,method,path,q,headers,body):
        if path=="/System/Info/Public" and method=="GET":
            return self.upstream(path)
        if path=="/QuickConnect/Enabled" and method=="GET":return False
        if path=="/Users/AuthenticateByName" and method=="POST":
            return self.upstream(path,method=method,body=body)
        token=client_token(headers,q)
        if path=="/Videos/ActiveEncodings" and method=="DELETE":
            return self.stop_stream(token,first(q,"PlaySessionId"))
        if path=="/Jellop/Diagnostics" and method=="GET":return self.diagnostics(token)
        if path=="/Jellop/Config" and method=="GET":
            self.catalogue(token,fresh=True)
            return {"JellopConfig":self.config.snapshot(),"Fault":self.config.fault}
        if path=="/LiveTv/Channels" and method=="GET":
            return page_rows(filtered_channels(self.catalogue(token),q),q)
        if re.fullmatch(r"/Users/[^/]+/Views",path) and method=="GET":
            self.catalogue(token)
            return {"Items":[{"Id":LIVE_VIEW,"Name":"Live TV","Type":"CollectionFolder",
                              "CollectionType":"livetv","IsFolder":True}],"TotalRecordCount":1}
        if re.fullmatch(r"/Users/[^/]+/Items",path) and method=="GET":
            rows=self.catalogue(token)
            types=first(q,"IncludeItemTypes").casefold().split(",")
            if ("livetvchannel" in types or "tvchannel" in types or
                    first(q,"ParentId")==LIVE_VIEW or first(q,"Ids") or first(q,"IsFavorite").casefold()=="true"):
                return page_rows(filtered_channels(rows,q),q)
            return {"Items":[],"TotalRecordCount":0}
        m=ITEM.fullmatch(path)
        if m and method=="GET":
            cid=m[2]
            for row in filtered_channels(self.catalogue(token),{"ids":[cid]}):
                row["MediaSources"]=[media_source(cid)]
                return row
            raise Failure(404,"channel-not-found")
        if path in ("/LiveTv/Programs","/LiveTv/Programs/Recommended") and method=="GET":
            selected=first(q,"ChannelIds")
            suffix="?"+url.urlencode({"ChannelIds":selected}) if selected else ""
            data=self.upstream("/LiveTv/Programs"+suffix,token)
            rows=data.get("Items",[])
            # Preserve unknown start/end instead of fabricating a full EPG.
            return page_rows(rows,q)
        if path=="/LiveTv/Recordings" and method=="GET":
            return self.upstream(path,token)
        if re.fullmatch(r"/Users/[^/]+/Items/Resume",path) and method=="GET":
            self.catalogue(token)
            return {"Items":[],"TotalRecordCount":0}
        m=PLAYBACK.fullmatch(path)
        if m and method in ("GET","POST"):
            cid=m[1];auto=first(q,"AutoOpenLiveStream","true").casefold()!="false"
            sid,source=self.resolve(token,cid,auto=auto)
            self.remember(token,cid,sid,source)
            return {"PlaySessionId":sid,"MediaSources":[media_source(cid)],"JellopConfig":self.config.snapshot()}
        if FAVORITE.fullmatch(path) and method in ("POST","DELETE"):
            result=self.upstream(path,token,method,body if method=="POST" else None)
            with self.lock:self.catalogues.pop(token,None)
            return result
        if path in ("/Sessions/Playing","/Sessions/Playing/Progress","/Sessions/Playing/Stopped","/LiveStreams/Close") and method=="POST":
            if path=="/Sessions/Playing/Progress" and body:
                try:
                    data=json.loads(body)
                    if isinstance(data,dict):
                        self.report_evidence(token,data)
                        data.pop("JellopEvidence",None)
                        body=json.dumps(data,separators=(",",":")).encode()
                except (ValueError,TypeError):raise Failure(400,"invalid-progress") from None
            return self.upstream(path,token,method,body or b"{}")
        if path=="/Sessions/Logout" and method=="POST":
            self.catalogue(token,fresh=True)
            with self.lock:
                self.catalogues.pop(token,None)
                for key in list(self.sessions):
                    if key[0]==token:self.sessions.pop(key)
            return {}
        raise Failure(404,"unsupported-route")

def stop_process(proc):
    if proc is None:return
    if proc.poll() is None:
        proc.terminate()
        try:proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill();proc.wait(timeout=3)
    if proc.stdout:proc.stdout.close()

class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version="HTTP/1.0"
    def setup(self):
        self.request.settimeout(15)
        super().setup()
    def log_message(self,*args):pass
    def reply(self,status,payload):
        raw=json.dumps(payload,separators=(",",":"),ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(raw)))
        self.send_header("Cache-Control","no-store")
        self.end_headers()
        self.wfile.write(raw)
    def serve_stream(self,cid,q):
        b=self.server.bridge
        token=client_token(self.headers,q)
        control=b.claim_stream(token,cid,first(q,"PlaySessionId"),self.connection)
        proc=None;started=False;sid="";reason="startup-error"
        try:
            sid,source=b.resolve(token,cid,session=control.requested)
            with b.lock:control.sid=sid
            if control.cancelled.is_set():return
            proc=subprocess.Popen(ffmpeg_args(b.binary,source,q,b.config.snapshot()),stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,bufsize=0)
            if not control.attach(proc):return
            with selectors.DefaultSelector() as sel:
                sel.register(proc.stdout,selectors.EVENT_READ)
                while not control.cancelled.is_set():
                    if not sel.select(timeout=25 if not started else 15):
                        if not started:raise Failure(504,"transcode-startup-timeout")
                        reason="transcode-output-timeout";break
                    if control.cancelled.is_set():break
                    chunk=os.read(proc.stdout.fileno(),STREAM_CHUNK)
                    if not chunk:
                        if not started:raise Failure(502,"transcode-no-output")
                        reason="transcode-ended";break
                    if not started:
                        self.send_response(200)
                        self.send_header("Content-Type","video/mp2t")
                        self.send_header("Cache-Control","no-store")
                        self.send_header("Connection","close")
                        self.end_headers()
                        b.stream_started(token,cid,sid)
                        started=True
                    self.wfile.write(chunk)
        except (BrokenPipeError,ConnectionResetError):
            reason="client-disconnected"
        except TimeoutError:
            reason="client-or-network-timeout"
            if not started:raise Failure(504,"transcode-startup-timeout") from None
        except OSError:
            reason="transport-or-transcoder-error"
            if not started:raise Failure(502,"transcode-unavailable") from None
        finally:
            try:stop_process(proc)
            finally:
                if started:b.stream_finished(token,cid,sid,"client-stop" if control.cancelled.is_set() else reason)
                b.release_stream(control)
    def handle_api(self):
        try:
            p=url.urlsplit(self.path)
            if p.scheme or p.netloc or len(self.path)>4096:raise Failure(400,"invalid-path")
            q={k.casefold():v for k,v in url.parse_qs(p.query,max_num_fields=48).items()}
            if self.command=="GET" and STREAM.fullmatch(p.path):
                self.serve_stream(STREAM.fullmatch(p.path)[1],q);return
            n=int(self.headers.get("Content-Length","0"))
            if n<0 or n>MAX_BODY:raise Failure(413,"request-too-large")
            body=self.rfile.read(n) if n else None
            self.reply(200,self.server.bridge.dispatch(self.command,p.path,q,self.headers,body))
        except Failure as e:
            try:self.reply(e.status,{"Error":e.code})
            except OSError:pass
        except (ValueError,TypeError):
            try:self.reply(400,{"Error":"invalid-request"})
            except OSError:pass
        except OSError:pass
    do_GET=do_POST=do_DELETE=handle_api

class Server(http.server.ThreadingHTTPServer):
    daemon_threads=True
    allow_reuse_address=True
    def __init__(self,address,bridge):
        self.bridge=bridge
        self.slots=threading.BoundedSemaphore(MAX_HANDLERS)
        super().__init__(address,Handler)
    def process_request(self,sock,address):
        if not self.slots.acquire(blocking=False):
            try:sock.sendall(b"HTTP/1.0 503 Service Unavailable\r\nContent-Length: 0\r\n\r\n")
            except OSError:pass
            self.shutdown_request(sock);return
        try:super().process_request(sock,address)
        except BaseException:
            self.slots.release();raise
    def process_request_thread(self,sock,address):
        try:super().process_request_thread(sock,address)
        finally:self.slots.release()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream",required=True)
    parser.add_argument("--bind",default="127.0.0.1")
    parser.add_argument("--port",type=int,default=18800)
    parser.add_argument("--ffmpeg",default="ffmpeg")
    parser.add_argument("--config",help="Optional bounded JSON configuration file")
    args=parser.parse_args()
    with Server((args.bind,args.port),Bridge(args.upstream,args.ffmpeg,args.config)) as server:
        server.serve_forever()
if __name__=="__main__":main()
