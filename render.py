#!/usr/bin/env python3
"""Render a 1080x1920 vertical reel with ffmpeg. Hindi text is drawn via libass
(ASS subtitles) — NOT drawtext — because libass shapes Devanagari correctly
(matras/conjuncts). Background = brand gradient, or a presenter still (dadi) with a
slow zoom. Mixes the voiceover (+ optional music)."""
import subprocess, pathlib, textwrap

ROOT = pathlib.Path(__file__).resolve().parent
FONT_FAMILY = "Mukta"   # bundled Devanagari font (assets/); libass shapes it right

def _dur(mp3):
    try:
        return max(6.0, min(float(subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1", mp3]).decode().strip()), 95.0))
    except Exception:
        return 45.0

def _t(t):
    h = int(t // 3600); m = int((t % 3600) // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"

def _wrap(script, width=22):
    out = []
    for para in script.split("\n"):
        para = para.strip()
        if para:
            out += textwrap.wrap(para, width=width) or [para]
    return "\\N".join(out)   # \N = hard line break in ASS

def _build_ass(brand_name, script, dur):
    end = _t(dur)
    body = _wrap(script)
    title = brand_name.replace("\n", " ")
    ass = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Title,{FONT_FAMILY},76,&H00FFFFFF,&H00FFFFFF,&H00202020,&H64000000,-1,0,0,0,100,100,0,0,1,5,2,8,50,50,80,1
Style: Body,{FONT_FAMILY},62,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,0,0,0,0,100,100,1,0,1,6,3,5,90,90,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,{end},Title,,0,0,0,,{title}
Dialogue: 0,0:00:00.00,{end},Body,,0,0,0,,{body}
"""
    p = ROOT / "sub.ass"
    p.write_text(ass, encoding="utf-8")
    return p

def render(brand_cfg, data, mp3, out):
    dur = _dur(mp3); frames = int(dur * 25) + 25
    prim = brand_cfg["color_primary"]
    presenter = data.get("presenter")
    pres_img = ROOT / "assets" / f"{presenter}.png" if presenter else None
    music = ROOT / "assets" / "music.mp3"
    _build_ass(brand_cfg["name"], data["script"], dur)

    subs = "subtitles=filename=sub.ass:fontsdir=assets"
    if pres_img and pres_img.exists():
        vin = ["-loop", "1", "-framerate", "25", "-t", f"{dur:.2f}", "-i", str(pres_img)]
        vchain = (f"scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,"
                  f"zoompan=z='min(zoom+0.0003,1.18)':d={frames}:s=1080x1920:fps=25,"
                  f"drawbox=x=0:y=1140:w=1080:h=780:color=black@0.5:t=fill,{subs}")
    else:
        vin = ["-f", "lavfi", "-t", f"{dur:.2f}", "-i",
               f"gradients=s=1080x1920:c0={prim}:c1=black:x0=0:y0=0:x1=1080:y1=1920:d={dur:.2f}"]
        vchain = subs

    cmd = ["ffmpeg", "-y", *vin, "-i", mp3]
    fc = f"[0:v]{vchain}[v]"
    amap = "1:a"
    if music.exists():
        cmd += ["-stream_loop", "-1", "-i", str(music)]
        fc += ";[2:a]volume=0.12[m];[1:a][m]amix=inputs=2:duration=first:dropout_transition=2[a]"
        amap = "[a]"
    cmd += ["-filter_complex", fc, "-map", "[v]", "-map", amap,
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "25",
            "-c:a", "aac", "-b:a", "160k", "-t", f"{dur:.2f}", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True, cwd=str(ROOT))
    print(f"[render] {out} ({dur:.1f}s) 1080x1920 (libass Hindi) presenter={presenter or 'none'}")
    return out
