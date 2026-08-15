#!/usr/bin/env python3
"""Publish a rendered reel to a Facebook Page (Reels) and Instagram (Reels).
FB accepts a direct file upload. Instagram's API requires a PUBLIC video URL, so we
upload the file to catbox.moe (free, no-auth) and hand Meta that URL."""
import os, time, requests, pathlib

GV = "https://graph.facebook.com/v21.0"

VIRAL = ("#reels #reelsviral #reelsinstagram #trending #trendingreels #viral #viralvideo "
         "#foryou #fyp #explore #instareels #india #indianreels #reelitfeelit")

CAT_TAGS = {
    "facts": "#facts #didyouknow #amazingfacts #rochaktathya #gyan #knowledge #interestingfacts",
    "health": "#health #ayurveda #gharelunuskhe #healthtips #desinuskhe #fitness #healthylifestyle",
    "motivation": "#motivation #motivationalvideo #inspiration #successmindset #hindimotivation #life",
}

def build_caption(bcfg, data):
    parts = [data.get("hook","").strip(), "", data.get("cta_line","").strip(), ""]
    if bcfg.get("disclaimer"):
        parts += [bcfg["disclaimer"], ""]
    tags = CAT_TAGS.get(bcfg["kind"], "") + " " + VIRAL
    parts.append(tags)
    return "\n".join(p for p in parts if p is not None).strip()

def upload_public(path):
    """Upload to catbox.moe -> returns a public URL for Instagram to pull."""
    with open(path, "rb") as f:
        r = requests.post("https://catbox.moe/user/api.php",
                          data={"reqtype": "fileupload"},
                          files={"fileToUpload": f}, timeout=300)
    r.raise_for_status()
    url = r.text.strip()
    if not url.startswith("http"):
        raise RuntimeError(f"catbox upload failed: {url[:120]}")
    return url

def post_facebook(page_id, token, path, caption):
    size = os.path.getsize(path)
    s = requests.post(f"{GV}/{page_id}/video_reels",
                      data={"upload_phase": "start", "access_token": token}, timeout=60).json()
    vid, up = s["video_id"], s["upload_url"]
    with open(path, "rb") as f:
        requests.post(up, headers={"Authorization": f"OAuth {token}",
                                   "offset": "0", "file_size": str(size)},
                      data=f.read(), timeout=600).raise_for_status()
    fin = requests.post(f"{GV}/{page_id}/video_reels",
                        data={"upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED",
                              "description": caption, "access_token": token}, timeout=120).json()
    return {"ok": bool(fin.get("success", True)), "video_id": vid, "resp": fin}

def post_instagram(ig_user_id, token, video_url, caption):
    c = requests.post(f"{GV}/{ig_user_id}/media",
                      data={"media_type": "REELS", "video_url": video_url,
                            "caption": caption, "access_token": token}, timeout=120).json()
    if "id" not in c:
        raise RuntimeError(f"IG container failed: {c}")
    cid = c["id"]
    for _ in range(30):
        st = requests.get(f"{GV}/{cid}", params={"fields": "status_code", "access_token": token},
                          timeout=60).json().get("status_code")
        if st == "FINISHED": break
        if st == "ERROR": raise RuntimeError("IG processing ERROR")
        time.sleep(10)
    pub = requests.post(f"{GV}/{ig_user_id}/media_publish",
                        data={"creation_id": cid, "access_token": token}, timeout=120).json()
    return {"ok": "id" in pub, "resp": pub}

def get_ig_id(page_id, token):
    """Auto-detect the Instagram Business account linked to a Page (no secret needed)."""
    try:
        r = requests.get(f"{GV}/{page_id}",
                         params={"fields": "instagram_business_account", "access_token": token},
                         timeout=60).json()
        return (r.get("instagram_business_account") or {}).get("id")
    except Exception:
        return None

def publish_all(brand, bcfg, path, data):
    token = os.environ["FB_TOKEN"]           # one system-user token works for all 3 pages
    page_id = bcfg["fb_page_id"]
    ig_id = os.environ.get(f"{bcfg.get('secret_prefix','')}_IG_USER_ID") or get_ig_id(page_id, token)
    caption = build_caption(bcfg, data)
    out = {}
    try:
        out["facebook"] = post_facebook(page_id, token, path, caption)
        print("[fb] published", out["facebook"]["video_id"])
    except Exception as e:
        out["facebook"] = {"ok": False, "error": str(e)[:200]}; print("[fb] FAILED", e)
    if ig_id:
        try:
            url = upload_public(path)
            out["instagram"] = post_instagram(ig_id, token, url, caption)
            print("[ig] published", out["instagram"]["resp"])
        except Exception as e:
            out["instagram"] = {"ok": False, "error": str(e)[:200]}; print("[ig] FAILED", e)
    return out
