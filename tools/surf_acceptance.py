"""Strict chronological evidence for repeated native Surf cycles."""
import re

CONFIRM=re.compile(r"JELLOP_LIVE_CONFIRMED channel=([a-f0-9]{32}) frame=(\d+)")
DUE=re.compile(r"JELLOP_SURF_DUE from=([a-f0-9]{32}) to=([a-f0-9]{32}) cycle=(\d+)")
SAMPLE=re.compile(r"JELLOP_LIVE_SAMPLE channel=([a-f0-9]{32}) frames=(\d+) decoded_ms=(\d+) stalls=(\d+) free_kib=(\d+) programme=(.*)$")

def evaluate(lines,channels,attempts,transitions=4):
    expected=set(channels)
    if len(expected)!=2:raise ValueError("Expected two-channel fixture")
    if any(cid not in expected or status!=200 for cid,status in attempts):
        raise RuntimeError("Unexpected or unsuccessful fixture playback request")
    sessions=[];switches=[];pending=None
    for line in lines.splitlines():
        m=CONFIRM.search(line)
        if m:
            cid,frame=m.groups()
            if cid not in expected or int(frame)<=0:raise RuntimeError("Invalid decoded confirmation")
            if sessions and (pending is None or pending[1]!=cid):raise RuntimeError("Unrequested channel confirmation")
            sessions.append({"channel":cid,"first_frame":int(frame),"samples":[]})
            pending=None
            continue
        m=DUE.search(line)
        if m:
            a,b,cycle=m.groups();cycle=int(cycle)
            if pending or not sessions or sessions[-1]["channel"]!=a or b not in expected or b==a:
                raise RuntimeError("Invalid automatic transition")
            if cycle!=1+(len(switches)+1)//2:raise RuntimeError("Unexpected Surf cycle sequence")
            pending=(a,b,cycle);switches.append(pending)
            continue
        m=SAMPLE.search(line)
        if m and sessions and not pending:
            cid,frames,ms,stalls,free,title=m.groups()
            if cid!=sessions[-1]["channel"]:raise RuntimeError("Sample identity mismatch")
            sessions[-1]["samples"].append({"frames":int(frames),"decoded_ms":int(ms),"stalls":int(stalls),"free_kib":int(free),"programme":title.strip()})
    if len(switches)<transitions or len(sessions)<transitions+1:return None
    for i,session in enumerate(sessions[:transitions+1]):
        samples=session["samples"]
        # Require actual decoded dwell before the four transitions, then
        # additional progress on the final channel after cycle rollover.
        min_ms=12000 if i<transitions else 3000
        if len(samples)<3 or samples[-1]["decoded_ms"]<min_ms:return None
        if samples[-1]["frames"]<=samples[0]["frames"]:return None
        if any(x["stalls"] for x in samples):raise RuntimeError("Decoded playback stalled")
        title="Fixture Film "+str(channels.index(session["channel"])+1)+" (2020)"
        if not any(x["programme"]==title for x in samples):raise RuntimeError("Current programme title missing or wrong")
        if any(a["frames"]>b["frames"] or a["decoded_ms"]>b["decoded_ms"] for a,b in zip(samples,samples[1:])):
            raise RuntimeError("Nonmonotonic native evidence")
    if [x[0] for x in attempts]!=[s["channel"] for s in sessions]:return None
    samples=[x for s in sessions for x in s["samples"]]
    return {"result":"passed","sessions":sessions,"transitions":switches,
        "minimum_free_kib":min(x["free_kib"] for x in samples),
        "maximum_free_kib":max(x["free_kib"] for x in samples),
        "decoded_stalls":sum(x["stalls"] for x in samples)}


def evaluate_controls(lines,events,favourites,first_channel):
    """Require native policy view and successful shared favourite round trip."""
    if "JELLOP_SMOKE_CONTROL_FAIL" in lines:
        raise RuntimeError("Native fixture control failed")
    expected=[(first_channel,True),(first_channel,False)]
    if len(events)>2 or events!=expected[:len(events)]:
        raise RuntimeError("Unexpected favourite mutation sequence")
    if len(events)!=2:return None
    if favourites:raise RuntimeError("Favourite removal was not persisted")
    policy="JELLOP_SMOKE_POLICY banned=1 hiatus=1 playable=0"
    values=re.findall(r"JELLOP_SMOKE_FAVOURITE value=([01])",lines)
    if len(values)>2 or values!=["1","0"][:len(values)]:
        raise RuntimeError("Native favourite confirmation sequence invalid")
    if policy not in lines or len(values)!=2:return None
    if not lines.index(policy)<lines.index("JELLOP_SMOKE_FAVOURITE value=1"):
        raise RuntimeError("Policy browser was not tested before playback")
    return {"policy_banned":1,"policy_hiatus":1,"policy_playable":0,"favourite_round_trip":True}
