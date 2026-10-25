#!/usr/bin/env python3
"""Render a 1080x1920 vertical reel with ffmpeg.
- Hindi text via libass (ASS subtitles) so Devanagari shapes correctly.
- Background: presenter still (dadi, Ken Burns) if assets/<presenter>.png exists;
  else real Pexels footage (if PEXELS_API_KEY set); else a brand gradient.
- Mixes voiceover (+ optional assets/music.mp3). Output 1080p, crf 20."""
import subprocess, pathlib, textwrap, os, json, random, unicodedata, urllib.request, urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent
FONT_FAMILY = "Mukta"

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

def _vis_len(s):
    # visual width: Devanagari nonspacing matras (ि ी े ं …) add no width, so a phrase
    # isn't counted as "too long" just because it has many combining marks.
    return sum(0 if unicodedata.category(c) == "Mn" else 1 for c in s)

def _wrap(script, width=24):
    # word-aware wrap by VISUAL width — never breaks a word, and merges a lonely
    # trailing word up so sentences don't orphan a single word on its own line.
    out = []
    for para in script.split("\n"):
        para = para.strip()
        if not para:
            continue
        lines, line = [], ""
        for w in para.split():
            cand = (line + " " + w).strip()
            if not line or _vis_len(cand) <= width:
                line = cand
            else:
                lines.append(line); line = w
        if line:
            lines.append(line)
        # pull a 1-word orphan back onto the previous line
        if len(lines) >= 2 and len(lines[-1].split()) == 1:
            lines[-2] = lines[-2] + " " + lines[-1]; lines.pop()
        out += lines
    return "\\N".join(out)

def _ass_color(hexstr):
    """'0xRRGGBB' -> ASS '&H00BBGGRR'."""
    h = str(hexstr).lower().replace("0x", "").zfill(6)
    return f"&H00{h[4:6]}{h[2:4]}{h[0:2]}"

def _build_ass(brand_name, script, dur, items=None, accent="0xF2B705", presenter=False, presenter_name="",
               series="", episode=0, trust=""):
    end = _t(dur); body = _wrap(script); title = brand_name.replace("\n", " ")
    acol = _ass_color(accent)
    # presenter mode: dadi stays in the upper frame, remedy text drops to a darkened
    # lower band (Alignment 2 = bottom-center). Otherwise text is vertically centered.
    b_align, b_mv, b_size = (2, 120, 52) if presenter else (5, 0, 62)
    # NOTE: Spacing MUST stay 0 for every Devanagari style — any letter-spacing
    # breaks libass cluster shaping and detaches matras (tofu on dotted circles).
    ass = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Title,{FONT_FAMILY},76,&H00FFFFFF,&H00FFFFFF,&H00202020,&H64000000,-1,0,0,0,100,100,0,0,1,5,2,8,50,50,80,1
Style: Body,{FONT_FAMILY},{b_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,0,0,0,0,100,100,0,0,1,6,3,{b_align},90,90,{b_mv},1
Style: Chips,{FONT_FAMILY},50,{acol},&H00FFFFFF,&H00202020,&H82000000,-1,0,0,0,100,100,0,0,1,4,2,2,60,60,70,1
Style: Follow,{FONT_FAMILY},46,&H0000FFFF,&H00FFFFFF,&H00151515,&H50000000,-1,0,0,0,100,100,0,0,3,10,0,8,50,50,170,1
Style: Name,{FONT_FAMILY},50,&H00FFFFFF,&H00FFFFFF,{acol},&H00000000,-1,0,0,0,100,100,0,0,3,14,0,5,0,0,0,1
Style: Series,{FONT_FAMILY},40,{acol},&H00FFFFFF,&H00101010,&H64000000,-1,0,0,0,100,100,0,0,1,3,1,9,0,0,0,1
Style: Trust,{FONT_FAMILY},36,&H0080E080,&H00FFFFFF,&H00101010,&H64000000,-1,0,0,0,100,100,0,0,1,3,1,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,{end},Title,,0,0,0,,{title}
Dialogue: 0,0:00:00.00,{end},Follow,,0,0,0,,  Follow करें +
Dialogue: 0,0:00:00.00,{end},Body,,0,0,0,,{body}
"""
    chips = [str(i).strip() for i in (items or []) if str(i).strip()]
    if chips:
        line = "सामग्री:  " + "    •    ".join(chips[:4])
        ass += f"Dialogue: 0,0:00:00.00,{end},Chips,,0,0,0,,{line}\n"
    # recurring character name badge, sat as a lower-third on the presenter's face
    if presenter and str(presenter_name).strip():
        ass += f"Dialogue: 0,0:00:00.00,{end},Name,,0,0,0,,{{\\pos(540,1095)}}{presenter_name.strip()}\n"
    # series episode badge (top-right) — makes it a bingeable, followable series
    if str(series).strip() and episode:
        ass += f"Dialogue: 0,0:00:00.00,{end},Series,,0,0,0,,{{\\pos(1040,50)}}{str(series).strip()}  #{episode}\n"
    # trust badge (top-left) — the credibility cue that drives saves/shares in the health niche
    if str(trust).strip():
        ass += f"Dialogue: 0,0:00:00.00,{end},Trust,,0,0,0,,{{\\pos(40,50)}}{str(trust).strip()}\n"
    (ROOT / "sub.ass").write_text(ass, encoding="utf-8")

# ---- background sources ----------------------------------------------------
PEXELS_Q = {
    "Gharelu Nuskhe": "indian spices kitchen herbs",
    "Ayurveda": "ayurveda herbs herbal",
    "Yoga": "yoga meditation calm",
    "Diet & Fitness": "healthy food fitness",
    "Space & Science Facts": "galaxy space stars",
    "India & History Facts": "india heritage monument",
    "Nature & Animal Facts": "wildlife nature",
    "Technology & Space Facts": "technology futuristic",
    "World & Culture Facts": "world travel culture",
    "God Motivation": "sunrise temple sky",
    "Success Mindset": "mountain sunrise clouds",
    "Business Motivation": "city skyline timelapse",
    "Self Improvement": "calm nature forest",
    "Life Lessons": "ocean sunset horizon",
}

# real-human-grandmother footage for "presenter" slots (no AI face) — several queries,
# tried in order, so we get an actual elderly woman / home-remedy scene when possible.
PRESENTER_Q = {
    "dadi": ["indian grandmother cooking", "old indian woman kitchen", "elderly indian woman",
             "indian spices kitchen herbs"],
    "nani": ["elderly indian woman home", "old indian woman portrait", "indian grandmother",
             "ayurveda herbs herbal"],
}

def fetch_pexels_bg(category, out, query_override=None):
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return None
    # query_override may be a single query or a list of fallbacks to try in order
    queries = query_override if isinstance(query_override, list) else (
        [query_override] if query_override else [PEXELS_Q.get(category, category)])
    UA = "Mozilla/5.0 (reels-bot)"   # Pexels is Cloudflare-fronted: 403 without a User-Agent
    for q in queries:
        try:
            url = ("https://api.pexels.com/videos/search?orientation=portrait&size=large&per_page=20&query="
                   + urllib.parse.quote(q))
            req = urllib.request.Request(url, headers={"Authorization": key, "User-Agent": UA})
            data = json.loads(urllib.request.urlopen(req, timeout=60).read())
            vids = data.get("videos") or []
            if not vids:
                print("[pexels] no videos for", q); continue
            # prefer clips that actually have a high-res (UHD/4K) portrait source
            vids = [vv for vv in vids if any((f.get("height") or 0) >= 1920 for f in vv.get("video_files", []))] or vids
            v = random.choice(vids[:12])
            portrait = [f for f in v.get("video_files", []) if (f.get("width") or 0) < (f.get("height") or 1)]
            pool = portrait or v.get("video_files", [])
            # highest-resolution source (4K vertical → crisp 1080 downscale), capped ~3840 to keep file sane
            pool.sort(key=lambda f: (f.get("height") or 0), reverse=True)
            best = next((f for f in pool if (f.get("height") or 0) <= 3840), pool[0])
            link = best["link"]
            print(f"[pexels] source {best.get('width')}x{best.get('height')} for", q)
            vreq = urllib.request.Request(link, headers={"User-Agent": UA})
            with urllib.request.urlopen(vreq, timeout=120) as r, open(out, "wb") as fo:
                fo.write(r.read())
            print("[pexels] downloaded bg for", q)
            return out
        except Exception as e:
            print("[pexels] failed:", type(e).__name__, str(e)[:100], "| q=", q)
    return None

def _pick_music():
    """Pick a random royalty-free track for variety: any mp3 in assets/music/, else
    assets/music.mp3. Returns a path string or None (no music). Keeps audio legal/free."""
    mdir = ROOT / "assets" / "music"
    tracks = list(mdir.glob("*.mp3")) if mdir.exists() else []
    single = ROOT / "assets" / "music.mp3"
    if single.exists():
        tracks.append(single)
    return str(random.choice(tracks)) if tracks else None

# ---- main render -----------------------------------------------------------
def render(brand_cfg, data, mp3, out):
    dur = _dur(mp3); frames = int(dur * 25) + 25
    prim = brand_cfg["color_primary"]
    presenter = data.get("presenter")
    music = _pick_music()
    # presenter slots now use REAL human footage (elderly woman / kitchen), not an AI face.
    # Text stays vertically centered over the darkened footage (no special face layout).
    _build_ass(brand_cfg["name"], data["script"], dur,
               data.get("items"), brand_cfg.get("color_accent", "0xF2B705"), False,
               data.get("presenter_name", ""), data.get("series", ""), data.get("episode", 0),
               brand_cfg.get("trust_badge", ""))
    subs = "subtitles=filename=sub.ass:fontsdir=assets"

    # for presenter slots pull real-grandmother footage; otherwise the category footage
    q_over = PRESENTER_Q.get(presenter) if presenter else None
    bg_video = fetch_pexels_bg(data.get("category", ""), str(ROOT / "bg.mp4"), q_over)

    if bg_video:
        vin = ["-stream_loop", "-1", "-i", bg_video]
        vchain = (f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,"
                  f"drawbox=x=0:y=0:w=1080:h=1920:color=black@0.28:t=fill,{subs}")
    else:
        vin = ["-f", "lavfi", "-t", f"{dur:.2f}", "-i",
               f"gradients=s=1080x1920:c0={prim}:c1=black:x0=0:y0=0:x1=1080:y1=1920:d={dur:.2f}"]
        vchain = subs

    cmd = ["ffmpeg", "-y", *vin, "-i", mp3]
    fc = f"[0:v]{vchain}[v]"
    amap = "1:a"
    if music:
        cmd += ["-stream_loop", "-1", "-i", str(music)]
        fc += ";[2:a]volume=0.12[m];[1:a][m]amix=inputs=2:duration=first:dropout_transition=2[a]"
        amap = "[a]"
    cmd += ["-filter_complex", fc, "-map", "[v]", "-map", amap,
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "25",
            "-c:a", "aac", "-b:a", "160k", "-t", f"{dur:.2f}", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True, cwd=str(ROOT))
    src = ("pexels-presenter" if (presenter and bg_video) else
           ("pexels" if bg_video else "gradient"))
    print(f"[render] {out} ({dur:.1f}s) 1080x1920 bg={src} (libass Hindi)")
    return out
