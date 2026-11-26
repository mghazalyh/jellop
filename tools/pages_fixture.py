"""Fetch the public Jealouswin synthetic test fixture on GitHub-hosted runners."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

BASE="https://jealouswin.pages.dev/jellop-test/v1/"
RELEASE="ea578eee370198da46abc02b617027ea544696b2"
def get(name,limit,release=RELEASE):
    if name not in ("manifest.json","fixture.m3u8") and not re.fullmatch(r"seg\d{3}\.ts",name):
        raise RuntimeError("Invalid fixture asset name")
    if not re.fullmatch(r"[a-f0-9]{40}",release):raise RuntimeError("Invalid fixture revision")
    # Same Node fetch stack and release query as Jealouswin's verified deployment.
    helper=Path(__file__).with_name("fetch_pages_asset.mjs")
    result=subprocess.run(["node",str(helper),BASE+name+"?release="+release+"&verify=0",str(limit)],capture_output=True,timeout=40)
    if result.returncode:
        raise RuntimeError("Public fixture fetch failed: "+result.stderr.decode(errors="replace")[-500:])
    if len(result.stdout)>limit:raise RuntimeError("Fixture asset exceeds limit")
    return result.stdout

def download(root,rid):
    data=json.loads(get("manifest.json",32768))
    if data.get("schemaVersion")!=1 or data.get("synthetic") is not True or not re.fullmatch(r"[a-f0-9]{40}",data.get("release","")):
        raise RuntimeError("Unexpected deployed fixture schema")
    assets=data.get("assets")
    if not isinstance(assets,dict) or not 2<=len(assets)<=40 or "fixture.m3u8" not in assets:
        raise RuntimeError("Unexpected fixture assets")
    total=0
    for name,entry in assets.items():
        if name!="fixture.m3u8" and not re.fullmatch(r"seg\d{3}\.ts",name):raise RuntimeError("Invalid asset name")
        n=entry.get("bytes")
        if type(n) is not int or not 0<n<4*1024*1024:raise RuntimeError("Invalid asset size")
        total+=n
        if total>32*1024*1024:raise RuntimeError("Fixture too large")
        raw=get(name,n,data["release"])
        if len(raw)!=n or hashlib.sha256(raw).hexdigest()!=entry.get("sha256"):raise RuntimeError("Fixture digest mismatch")
        (root/(rid+".m3u8" if name=="fixture.m3u8" else name)).write_bytes(raw)
    playlist=(root/(rid+".m3u8")).read_text()
    names=[line.strip() for line in playlist.splitlines() if line.strip() and not line.startswith("#")]
    if not names or any(not re.fullmatch(r"seg\d{3}\.ts",n) or n not in assets for n in names):
        raise RuntimeError("Invalid deployed playlist references")
    print("Verified Jealouswin HTTPS fixture",data["release"],len(assets),"assets",total,"bytes",flush=True)
