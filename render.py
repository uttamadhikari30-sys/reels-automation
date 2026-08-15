#!/usr/bin/env python3
"""Render a 1080x1920 vertical reel with ffmpeg (available on GitHub runners).
Background = brand gradient, or a presenter still (dadi) with slow zoom. Overlays the
brand name, the script text (Devanagari), and mixes the voiceover (+ optional music).
Keeps output small enough for Instagram (<~40MB)."""
import subprocess, pathlib, textwrap, os

ROOT = pathlib.Path(__file__).resolve().parent
FONT = str(ROOT / "assets" / "NotoSansDevanagari.ttf")  # workflow downloads this

def _dur(mp3):
    try:
        return max(6.0, min(float(subprocess.check_output([
            "ffprobe","-v","error","-show_entries","format=duration",
            "-of","default=nw=1:nk=1", mp3]).decode().strip()), 90.0))
    except Exception:
        return 45.0

def _wrap(script, width=26):
    lines = []
    for para in script.split("\n"):
        para = para.strip()
        if not para: continue
        lines += textwrap.wrap(para, width=width) or [para]
    return "\n".join(lines)

def render(brand_cfg, data, mp3, out):
    dur = _dur(mp3)
    frames = int(dur*25)+25
    cap = ROOT / "cap.txt"
    cap.write_text(_wrap(data["script"]), encoding="utf-8")
    title = ROOT / "title.txt"; title.write_text(brand_cfg["name"], encoding="utf-8")
    prim = brand_cfg["color_primary"]; acc = brand_cfg["color_accent"]

    presenter = data.get("presenter")
    pres_img = ROOT / "assets" / f"{presenter}.png" if presenter else None
    music = ROOT / "assets" / "music.mp3"

    # --- background input + filter ---
    if pres_img and pres_img.exists():
        vin = ["-loop","1","-framerate","25","-t",f"{dur:.2f}","-i",str(pres_img)]
        bg = (f"scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,"
              f"zoompan=z='min(zoom+0.0003,1.18)':d={frames}:s=1080x1920:fps=25,"
              f"drawbox=x=0:y=1100:w=1080:h=820:color=black@0.55:t=fill,format=yuv420p[bg]")
    else:
        vin = ["-f","lavfi","-t",f"{dur:.2f}","-i",
               f"gradients=s=1080x1920:c0={prim}:c1=black:x0=0:y0=0:x1=1080:y1=1920:d={dur:.2f}"]
        bg = "format=yuv420p[bg]"

    # text overlays: brand name (top) + script (lower)
    draw = (f"[bg]drawtext=fontfile='{FONT}':textfile='{title}':fontcolor=white:fontsize=64:"
            f"borderw=3:bordercolor={acc}:x=(w-tw)/2:y=90[t1];"
            f"[t1]drawtext=fontfile='{FONT}':textfile='{cap}':fontcolor=white:fontsize=46:"
            f"line_spacing=14:borderw=4:bordercolor=black@0.9:x=(w-tw)/2:y=1180[v]")

    cmd = ["ffmpeg","-y", *vin, "-i", mp3]
    fc = f"{bg};{draw}"
    amap = "1:a"
    if music.exists():
        cmd += ["-stream_loop","-1","-i",str(music)]
        fc += ";[2:a]volume=0.12[m];[1:a][m]amix=inputs=2:duration=first:dropout_transition=2[a]"
        amap = "[a]"
    cmd += ["-filter_complex", fc, "-map","[v]","-map", amap,
            "-c:v","libx264","-preset","veryfast","-pix_fmt","yuv420p","-r","25",
            "-c:a","aac","-b:a","128k","-t",f"{dur:.2f}",
            "-maxrate","6M","-bufsize","10M","-movflags","+faststart", str(out)]
    subprocess.run(cmd, check=True)
    print(f"[render] {out} ({dur:.1f}s) presenter={presenter or 'none'}")
    return out
