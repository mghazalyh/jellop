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


def verify_visual_playback(out):
    """Fail closed on black, obscured, frozen or grossly unstable fixture output.

    This checks actual X11 scanout, not guest decoded-frame counters. The public
    fixture is FFmpeg testsrc2, not arbitrary programme material.
    """
    width, height, fps, frames = 160, 90, 10, 36
    frame_bytes = width * height * 3
    display = os.environ.get("DISPLAY")
    if not display:
        raise RuntimeError("Visual acceptance requires the actual X11 display")
    capture = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "x11grab",
         "-draw_mouse", "0", "-framerate", str(fps), "-video_size", "1280x720",
         "-i", display, "-frames:v", str(frames), "-vf", "scale=160:90",
         "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=True,
    )
    if len(capture.stdout) != frames * frame_bytes:
        raise RuntimeError("Incomplete visual capture")
    # Retain an independently viewable clip, including failure evidence.
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "rawvideo", "-pixel_format", "rgb24", "-video_size", "160x90",
         "-framerate", str(fps), "-i", "pipe:0", "-c:v", "libx264",
         "-pix_fmt", "yuv420p", str(out / "visual-proof.mp4")],
        input=capture.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=25, check=True,
    )
    # Exclude transport controls at the bottom, but include the centre where
    # the earlier RPCS3 welcome dialog covered the black playback area.
    regions = [(16, 9, 80, 36), (80, 9, 144, 36),
               (16, 36, 80, 63), (80, 36, 144, 63)]
    offsets = [[(y * width + x) * 3 for y in range(y0, y1)
                for x in range(x0, x1)] for x0,y0,x1,y1 in regions]
    roi = [i for group in offsets for i in group]
    samples = [memoryview(capture.stdout)[i*frame_bytes:(i+1)*frame_bytes]
               for i in range(frames)]
    readings, differences, failures = [], [], []
    for index, frame in enumerate(samples):
        coverage = []
        for group in offsets:
            colourful = sum(max(frame[i:i+3]) >= 75 and
                             max(frame[i:i+3]) - min(frame[i:i+3]) >= 45
                             for i in group)
            coverage.append(colourful / len(group))
        pale = sum(min(frame[i:i+3]) >= 175 and
                   max(frame[i:i+3]) - min(frame[i:i+3]) <= 25
                   for i in roi) / len(roi)
        readings.append({"frame": index, "colour_coverage": coverage,
                         "bright_neutral_fraction": pale})
        if min(coverage) < 0.08 or sum(coverage)/4 < 0.22 or pale > 0.18:
            failures.append({"frame": index, "reason": "missing fixture colour or obscured video"})
        if index:
            prev = samples[index-1]
            delta = sum(abs(frame[i+j]-prev[i+j]) for i in roi
                        for j in range(3)) / (len(roi)*3)
            differences.append(delta)
            if delta > 35:
                failures.append({"frame": index, "reason": "gross full-screen instability"})
    moving = sum(d >= 0.35 for d in differences)
    if moving < len(differences) * 0.65:
        failures.append({"reason": "insufficient visual motion", "moving_pairs": moving})
    proof = {"result": "failed" if failures else "passed", "frames": frames,
             "fps": fps, "samples": readings, "mean_absolute_differences": differences,
             "failures": failures,
             "limitations": "Synthetic X11 scanout check; not physical RSX/HDMI acceptance or subtle jitter proof."}
    (out/"visual-acceptance.json").write_text(json.dumps(proof, indent=2))
    if failures:
        raise RuntimeError("Visual playback rejected: " + json.dumps(failures[:5]))
    print("Visual playback acceptance passed:", frames, "frames;", moving,
          "moving adjacent pairs", flush=True)
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "x11grab", "-draw_mouse", "0", "-video_size", "1280x720",
         "-i", display, "-frames:v", "1", "-threads", "1",
         str(out / "video-playing.png")],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15, check=True,
    )
    return {"frames": frames, "fps": fps, "moving_pairs": moving,
            "screenshot": "video-playing.png", "clip": "visual-proof.mp4"}

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
    # Use the exact GUI settings keys from the pinned RPCS3 source. The prior
    # passing run had the first-run dialog in front of the game window.
    # This is only the disposable GitHub Actions emulator profile.
    gui = root / "GuiConfigs"
    gui.mkdir(parents=True, exist_ok=True)
    (gui / "CurrentSettings.ini").write_text(
        "[main_window]\ninfoBoxEnabledWelcome=false\n"
        "[GSFrame]\nresize=true\nresizeManual=true\nwidth=1280\nheight=720\n"
    )
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
                        subprocess.run(["import","-window","root",str(out/"screen.png")],timeout=15,check=True)
                        result["visual"] = verify_visual_playback(out)
                        (out/"result.json").write_text(json.dumps(result,indent=2))
                        print("Surf and visual acceptance passed:",json.dumps({k:v for k,v in result.items() if k!="sessions"}),flush=True)
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
