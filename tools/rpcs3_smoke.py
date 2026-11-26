"""Run the actual emulator and assert decoded frame progress across a Surf transition."""
import argparse
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
from rpcs3_fixture import fixture, TOKEN, USER, CHANNELS, EXCLUDED
from surf_acceptance import evaluate, evaluate_controls

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--emulator",required=True)
    ap.add_argument("--root",required=True,type=Path)
    ap.add_argument("--output",required=True,type=Path)
    args=ap.parse_args()
    root=args.root.resolve()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    hdd=root/"dev_hdd0"
    game=hdd/"game"/"JELP30001"/"USRDIR"
    boot=game/"EBOOT.BIN"
    if not boot.is_file():raise RuntimeError("RPCS3 package installation did not produce EBOOT.BIN")
    if not (root/"dev_flash"/"vsh").is_dir():raise RuntimeError("RPCS3 firmware installation incomplete")
    tmp=hdd/"tmp"/"jellop";tmp.mkdir(parents=True,exist_ok=True)
    # Only allow the isolated CI profile; never overwrite a personal profile.
    if not os.environ.get("GITHUB_ACTIONS") or "jellop-rpcs3" not in root.parts:
        raise RuntimeError("This fixture harness requires the dedicated CI profile")
    host=os.environ.get("JELLOP_FIXTURE_HOST","127.0.0.1")
    endpoint="http://"+host+":18096"
    (game/"jellyfin_config.txt").write_text(endpoint+"\nfixture\n"+TOKEN+"\n"+USER+"\n")
    (game/"jellyfin_updatecheck.txt").write_text("0\n")
    (game/"jellyfin_bootanim.txt").write_text("0\n")
    marker=game/"jellop_smoke.txt"
    marker.write_text("fixture-surf-v1\n"+endpoint+"\n")
    state=tmp/"jf_state.log"
    config=out/"rpcs3-config.yml"
    # Match the virtual CPU capabilities, not the physical AMD model.
    flag_sets=[set(line.split(":",1)[1].split()) for line in Path("/proc/cpuinfo").read_text().splitlines() if line.split(":",1)[0].strip()=="flags"]
    if not flag_sets:raise RuntimeError("Host CPU features unavailable")
    flags=set.intersection(*flag_sets)
    full512=set("avx512f avx512cd avx512dq avx512bw avx512vl".split())
    v3=set("avx avx2 bmi1 bmi2 f16c fma movbe xsave".split())
    v2=set("ssse3 sse4_1 sse4_2 popcnt cx16".split())
    if full512<=flags:target=""
    elif v3<=flags and ("abm" in flags or "lzcnt" in flags):target="x86-64-v3"
    elif v2<=flags:target="x86-64-v2"
    else:raise RuntimeError("Unsupported runner CPU")
    print("RPCS3 LLVM target:",target or "auto",flush=True)
    config.write_text("Core:\n  Use LLVM CPU: "+json.dumps(target)+"\nVideo:\n  Renderer: OpenGL\n  Write Color Buffers: true\n  Read Color Buffers: true\nAudio:\n  Renderer: \"Null\"\n  Music Handler: \"Null\"\nInput/Output:\n  Camera: \"Null\"\nNet:\n  Internet enabled: Connected\n  Bind address: 0.0.0.0\n")
    env=dict(os.environ,LIBGL_ALWAYS_SOFTWARE="1",QT_X11_NO_MITSHM="1")
    proc=None
    cache=Path(os.environ.get("XDG_CACHE_HOME",str(root)))/"rpcs3"
    rpcs3_log=cache/"RPCS3.log"
    with fixture() as b, (out/"emulator-stdout.log").open("wb") as log:
        try:
            import urllib.request
            with urllib.request.urlopen(endpoint+"/System/Info/Public",timeout=5) as r:
                assert json.load(r)["ServerName"]=="Jellop CI fixture"
            req=urllib.request.Request(endpoint+"/Users/"+USER+"/Views",headers={"Authorization":'MediaBrowser Client="PS3", Token="fixture-token"'})
            with urllib.request.urlopen(req,timeout=5) as r:
                assert json.load(r)["Items"][0]["CollectionType"]=="livetv"
            print("Host preflight verified fixture discovery and native authorization",flush=True)
            proc=subprocess.Popen([args.emulator,"--no-gui","--config",str(config),str(boot)],
                stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
            deadline=time.monotonic()+480
            guest_started=False
            last_state=""
            config_verified=False
            while time.monotonic()<deadline:
                if rpcs3_log.exists():
                    with rpcs3_log.open("rb") as raw:
                        raw.seek(max(0,rpcs3_log.stat().st_size-262144))
                        recent=raw.read().decode(errors="replace")
                    if not config_verified and "Used configuration:" in recent:
                        used=recent.split("Used configuration:",1)[1]
                        if "\nNet:\n" in used and "Internet enabled:" in used:
                            audio=used.split("\nAudio:\n",1)[1].split("\nInput/Output:",1)[0]
                            for key in ("Renderer","Music Handler"):
                                if not re.search(r"(?m)^  "+key+r': "?Null"?\s*$',audio):
                                    raise RuntimeError("RPCS3 effective Audio "+key+" is not Null")
                            if target and not re.search(r'(?m)^  Use LLVM CPU: "?' + re.escape(target) + r'"?[ \t]*$', used):
                                raise RuntimeError("RPCS3 CPU override not applied")
                            config_verified=True
                            print("RPCS3 effective audio configuration verified",flush=True)
                    if ("Emulation has been frozen!" in recent or
                        "Thread terminated due to fatal error" in recent):
                        raise RuntimeError("RPCS3 reported fatal emulation freeze; see RPCS3.log")
                if proc.poll() is not None:raise RuntimeError("RPCS3 exited before smoke completion: "+str(proc.returncode))
                lines=state.read_text(errors="replace") if state.exists() else ""
                if lines!=last_state:
                    print(lines[len(last_state):] if lines.startswith(last_state) else lines[-4000:],flush=True)
                    last_state=lines
                if not guest_started and "MAIN_MENU_ENTER" in lines:
                    guest_started=True
                    deadline=time.monotonic()+330
                    print("Guest reached menu; starting separate playback watchdog",flush=True)
                if any(x in lines for x in ("JELLOP_SMOKE_MARKER_ABSENT","JELLOP_SMOKE_INVALID_MARKER","JELLOP_SMOKE_CONFIG_MISMATCH")):
                    raise RuntimeError("Guest did not arm the fixture driver")
                with b.lock:attempts=list(b.fixture_attempts)
                events,favourites=b.fixture_favourite_snapshot()
                controls=evaluate_controls(lines,events,favourites,CHANNELS[0])
                if config_verified and "JELLOP_SMOKE_CATALOGUE count=2" in lines:
                    result=evaluate(lines,CHANNELS,attempts)
                    if result and controls:
                        result["controls"]=controls
                        result["excluded_channels"]=EXCLUDED
                        result["public_fixture"]=os.environ.get("JELLOP_PUBLIC_FIXTURE")=="1"
                        (out/"result.json").write_text(json.dumps(result,indent=2))
                        print("Surf acceptance passed:",json.dumps({k:v for k,v in result.items() if k!="sessions"}),flush=True)
                        subprocess.run(["import","-window","root",str(out/"screen.png")],timeout=15,check=False)
                        return
                time.sleep(1)
            raise RuntimeError("Timed out: "+("guest menu reached; missing catalogue or playback evidence" if guest_started else "guest did not reach main menu"))
        finally:
            if not (out/"screen.png").exists():
                try:subprocess.run(["import","-window","root",str(out/"failure-screen.png")],timeout=15,check=False)
                except (OSError,subprocess.TimeoutExpired):pass
            if proc and proc.poll() is None:
                os.killpg(proc.pid,signal.SIGTERM)
                try:proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid,signal.SIGKILL);proc.wait()
            marker.unlink(missing_ok=True)
            for src in (state,tmp/"crash_log.txt",tmp/"player_log.txt",rpcs3_log):
                if src.is_file():
                    with src.open("rb") as f:
                        f.seek(max(0,src.stat().st_size-2*1024*1024))
                        (out/src.name).write_bytes(f.read())

if __name__=="__main__":main()
