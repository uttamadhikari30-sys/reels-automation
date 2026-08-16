#!/usr/bin/env python3
"""One reel, end to end: generate script -> Hindi voiceover -> render -> post to FB+IG
-> record topic (never-repeat). Run: python pipeline.py --brand arogyamantra --slot 11:00"""
import argparse, json, pathlib, subprocess, sys
import gen, render, publish

ROOT = pathlib.Path(__file__).resolve().parent

def voiceover(text, voice, out):
    # edge-tts: free, natural Indian Hindi voices
    # NOTE: use --rate=-4% (equals form) — "--rate -4%" makes argparse treat -4% as a flag
    subprocess.run(["edge-tts", "--voice", voice, "--rate=-4%",
                    "--text", text, "--write-media", str(out)], check=True)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--brand", required=True)
    ap.add_argument("--slot", required=True)
    ap.add_argument("--no-post", action="store_true", help="render only, skip publishing")
    a = ap.parse_args()

    brands = json.loads((ROOT / "brands.json").read_text(encoding="utf-8"))
    bcfg = brands[a.brand]

    print(f"=== {bcfg['name']} {a.slot} ===")
    data = gen.generate(a.brand, bcfg, a.slot)
    print(f"[gen] topic={data['topic']} | category={data['category']} | source=anthropic-api")

    mp3 = ROOT / "reel.mp3"
    voiceover(data["script"], data["voice"], mp3)
    print("[voice]", data["voice"])

    mp4 = ROOT / "reel.mp4"
    render.render(bcfg, data, str(mp3), str(mp4))

    if a.no_post:
        print("[done] rendered only ->", mp4); return

    res = publish.publish_all(a.brand, bcfg, str(mp4), data)
    ok = any(v.get("ok") for v in res.values())
    if ok:
        gen.record(a.brand, data["category"], data["topic"])   # only record if something posted
        print("[state] recorded topic (never-repeat)")
    print("[result]", json.dumps(res, ensure_ascii=False)[:400])
    if not ok:
        sys.exit(1)

if __name__ == "__main__":
    main()
