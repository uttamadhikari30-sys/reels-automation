# Reels Auto-Post (FactMitra · ArogyaMantra · SparkMind)

Fully automated Hindi reel posting to Facebook + Instagram, running **free on GitHub Actions**
— no server, no PC needed. Each scheduled time: Claude writes a fresh (never-repeating) Hindi
script → edge-TTS Indian voice → ffmpeg builds a vertical reel → posts to FB + IG.

## What runs when (IST)
| Brand | Times |
|---|---|
| SparkMind | 06:00, 09:00, 12:00, 15:00, 18:00 |
| FactMitra | 10:00, 12:00, 14:00, 17:00, 19:00 |
| ArogyaMantra | 11:00, 13:00, 16:00, 20:00 |

## One-time setup

### 1. Put this folder in a GitHub repo
Create a free GitHub account, make a new repo (a **public** repo = unlimited free Actions
minutes; secrets stay hidden either way), and upload everything in this folder.

### 2. Add repository Secrets
Repo → **Settings → Secrets and variables → Actions → New repository secret**. Add:

Only **two** secrets are needed (page IDs are baked into `brands.json`; Instagram IDs auto-detected):

| Secret | Value |
|---|---|
| `ANTHROPIC_API_KEY` | your Claude API key |
| `FB_TOKEN` | the never-expiring system-user token (works for all 3 pages) |

> The `FB_TOKEN` is a never-expiring **System User** token (Meta Business Settings → System users
> → sparkmind-poster → Generate token → app "spark mind" → Never) with
> `pages_manage_posts`, `pages_read_engagement`, `pages_show_list`,
> `instagram_content_publish`, `instagram_basic`.

### 3. (Optional) presenter images & music
Drop `assets/dadi.png`, `assets/diet.png` (portrait photos) and `assets/music.mp3`.
If absent, reels use a clean branded gradient background automatically.

## Test it
Repo → **Actions → Reels Auto-Post → Run workflow** → pick a brand + slot.
Use `no_post = true` first to render without posting (check the produced `reel.mp4` artifact),
then run again with `no_post = false` to post live.

## How never-repeat works
After each successful post, the topic is appended to `state/used_<brand>.json` and committed
back to the repo. The next run passes recent topics to Claude and asks for a brand-new one.

## Files
- `gen.py` — Claude script generation (stdlib only)
- `pipeline.py` — orchestrator (`python pipeline.py --brand arogyamantra --slot 11:00`)
- `render.py` — ffmpeg vertical-reel renderer
- `publish.py` — Facebook Reels + Instagram Reels publishing
- `brands.json` — per-brand config & schedule
- `.github/workflows/reels.yml` — the scheduler
