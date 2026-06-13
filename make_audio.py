#!/usr/bin/env python3
"""Geracao de audio (voz) isolada, com edge-tts."""

import os
import re
import sys
import json
import asyncio
from pathlib import Path

import edge_tts

OUT_DIR = Path(os.environ.get("OUTPUT_DIR", "/output"))


def slugify(s):
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.strip().lower()).strip("-")
    return s[:60] or "audio"


def srt_time(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    sec = t % 60
    return f"{h:02d}:{m:02d}:{int(sec):02d},{int((sec - int(sec)) * 1000):03d}"


async def synth(text, voice, mp3_path):
    comm = edge_tts.Communicate(text, voice)
    boundaries = []
    with open(mp3_path, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 1e7
                end = (chunk["offset"] + chunk["duration"]) / 1e7
                boundaries.append((start, end, chunk["text"]))
    return boundaries


def write_srt(boundaries, path, wpc=4):
    with open(path, "w", encoding="utf-8") as f:
        idx = 1
        for i in range(0, len(boundaries), wpc):
            g = boundaries[i:i + wpc]
            if not g:
                continue
            f.write(f"{idx}\n{srt_time(g[0][0])} --> {srt_time(g[-1][1])}\n"
                    + " ".join(w for _, _, w in g) + "\n\n")
            idx += 1


def parse_args():
    spec = {}
    args = sys.argv[1:]
    if args and args[0] == "-":
        spec = json.loads(sys.stdin.read())
    elif args and not args[0].startswith("--"):
        spec = json.loads(Path(args[0]).read_text())
    else:
        it = iter(args)
        for a in it:
            if a == "--text":
                spec["text"] = next(it)
            elif a == "--name":
                spec["name"] = next(it)
            elif a == "--voice":
                spec["voice"] = next(it)
            elif a == "--srt":
                spec["srt"] = True
    return spec


def main():
    spec = parse_args()
    text = spec.get("text")
    if not text:
        print(json.dumps({"ok": False, "error": "campo 'text' obrigatorio"}))
        sys.exit(1)

    voice = spec.get("voice", "pt-BR-AntonioNeural")
    name = slugify(spec.get("name") or text)
    want_srt = bool(spec.get("srt", True))
    wpc = int(spec.get("words_per_cue", 4))
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    mp3 = OUT_DIR / f"{name}.mp3"
    boundaries = asyncio.run(synth(text, voice, mp3))
    dur = boundaries[-1][1] if boundaries else 0.0

    result = {"ok": True, "audio": str(mp3), "duration_s": round(dur, 2)}
    if want_srt:
        srt = OUT_DIR / f"{name}.srt"
        write_srt(boundaries, srt, wpc)
        result["srt"] = str(srt)
    print(json.dumps(result))


if __name__ == "__main__":
    main()

