"""Validated, request-driven configuration with a last-known-good snapshot."""
import json
import threading

DEFAULT={"schemaVersion":1,"revision":1,"surfDwellSeconds":60,"liveRingMiB":6,
         "maxVideoBitrate":4000000,"maxWidth":1280,"maxHeight":720}
BOUNDS={"schemaVersion":(1,1),"revision":(1,2147483647),
        "surfDwellSeconds":(15,600),"liveRingMiB":(2,6),
        "maxVideoBitrate":(500000,4000000),"maxWidth":(320,1280),"maxHeight":(180,720)}
MAX_CONFIG=4096

def validate(data):
    if type(data) is not dict or set(data)!=set(DEFAULT):raise ValueError("schema")
    for k,(low,high) in BOUNDS.items():
        if type(data[k]) is not int or not low<=data[k]<=high:raise ValueError("bounds")
    if data["maxWidth"]%2 or data["maxHeight"]%2:raise ValueError("dimensions")
    return dict(data)

def unique_pairs(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError("duplicate-key")
        result[key]=value
    return result

class Config:
    def __init__(self,path=None):
        self.path=path
        self.lock=threading.Lock()
        self.good=dict(DEFAULT)
        self.fault=""
        self.loaded=False

    def snapshot(self):
        with self.lock:
            if self.path:
                try:
                    with open(self.path,"rb") as f:raw=f.read(MAX_CONFIG+1)
                    if len(raw)>MAX_CONFIG:raise ValueError("size")
                    cfg=validate(json.loads(raw,object_pairs_hook=unique_pairs))
                    if self.loaded and (cfg["revision"]<self.good["revision"] or
                        (cfg["revision"]==self.good["revision"] and cfg!=self.good)):
                        raise ValueError("revision")
                    self.good=cfg;self.loaded=True;self.fault=""
                except (OSError,ValueError,TypeError,UnicodeError):
                    self.fault="invalid-or-unavailable-config"
            return dict(self.good)
