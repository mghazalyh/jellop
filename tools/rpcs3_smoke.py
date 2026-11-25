"""Run the actual emulator and assert decoded frame progress across a Surf transition."""
import argparse
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
from rpcs3_fixture import fixture, TOKEN, USER, CHANNELS

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
    (game/"jellyfin_config.txt").write_text("http://127.0.0.1:18096\nfixture\n"+TOKEN+"\n"+USER+"\n")
    (game/"jellyfin_updatecheck.txt").write_text("0\n")
    (game/"jellyfin_bootanim.txt").write_text("0\n")
    (tmp/"jellop_smoke.txt").write_text("fixture-surf-v1\n")
    state=tmp/"jf_state.log"
    config=out/"rpcs3-config.yml"
    config.write_text("Video:\n  Renderer: OpenGL\n  Write Color Buffers: true\n  Read Color Buffers: true\nAudio:\n  Renderer: Null\nNet:\n  Internet enabled: Connected\n  Bind address: 0.0.0.0\n")
    env=dict(os.environ,LIBGL_ALWAYS_SOFTWARE="1",QT_X11_NO_MITSHM="1")
    proc=None
    with fixture() as b, (out/"emulator-stdout.log").open("wb") as log:
        try:
            proc=subprocess.Popen([args.emulator,"--no-gui","--config",str(config),str(boot)],
                stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
            deadline=time.monotonic()+300
            while time.monotonic()<deadline:
                if proc.poll() is not None:raise RuntimeError("RPCS3 exited before smoke completion: "+str(proc.returncode))
                lines=state.read_text(errors="replace") if state.exists() else ""
                channels=re.findall(r"JELLOP_LIVE_CONFIRMED channel=([a-f0-9]{32}) frame=(\d+)",lines)
                confirmed={cid for cid,n in channels if int(n)>0}
                if "JELLOP_SMOKE_CATALOGUE count=2" in lines and "JELLOP_SURF_DUE " in lines and set(CHANNELS)<=confirmed:
                    after=lines[lines.rfind("JELLOP_LIVE_CONFIRMED"):]
                    frames=[int(x) for x in re.findall(r"AVSYNC .*?frame=(\d+)",after)]
                    if len(frames)>=2 and frames[-1]>frames[0]:
                        (out/"result.json").write_text(json.dumps({"result":"passed","channels":sorted(confirmed),"second_channel_frames":frames},indent=2))
                        subprocess.run(["import","-window","root",str(out/"screen.png")],timeout=15,check=False)
                        return
                time.sleep(1)
            raise RuntimeError("Timed out waiting for catalogue, decoded playback and actual Surf transition")
        finally:
            if proc and proc.poll() is None:
                os.killpg(proc.pid,signal.SIGTERM)
                try:proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid,signal.SIGKILL);proc.wait()
            cache=Path(os.environ.get("XDG_CACHE_HOME",str(root)))/"rpcs3"
            for src in (state,tmp/"crash_log.txt",tmp/"player_log.txt",cache/"RPCS3.log"):
                if src.is_file():
                    with src.open("rb") as f:
                        f.seek(max(0,src.stat().st_size-2*1024*1024))
                        (out/src.name).write_bytes(f.read())

if __name__=="__main__":main()
