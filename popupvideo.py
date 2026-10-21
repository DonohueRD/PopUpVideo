#!/usr/bin/env python3
import argparse
import os
import shutil
import sys
import tempfile
import time
import urllib.request
import urllib.error

from dotenv import load_dotenv

load_dotenv()

import downloader
import factoids
import subtitles
import encoder

OUTPUT_DIR = "/media/HueyRaid1/TV/Music Videos/Pop Up Video"
TUNARR_SCAN_URL = (
    "http://127.0.0.1:8010/api"
    "/media-sources/033d7ac8-2ae4-43c1-b13e-d2cd53064333"
    "/libraries/7d815220-a57b-48ed-b2ae-fdc786f587a4/scan"
)


def resolve_output_path(artist: str, song_title: str, output_dir: str) -> str:
    """Return a non-existing output path, appending (2), (3)... to avoid overwrites."""
    base = f"{artist} - {song_title} (Huey Pop Up Video)"
    candidate = os.path.join(output_dir, f"{base}.mp4")
    if not os.path.exists(candidate):
        return candidate
    n = 2
    while True:
        candidate = os.path.join(output_dir, f"{base} ({n}).mp4")
        if not os.path.exists(candidate):
            return candidate
        n += 1


def trigger_tunarr_scan() -> bool:
    """POST to Tunarr to trigger a Plex library scan. Returns True on success."""
    try:
        req = urllib.request.Request(
            TUNARR_SCAN_URL,
            method="POST",
            data=b"{}",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status < 400
    except Exception as e:
        print(f"  Warning: Tunarr scan trigger failed: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Huey Pop Up Video — VH1-style music video generator")
    parser.add_argument("-u", "--url", required=True, help="YouTube URL of the music video")
    parser.add_argument("--dry-run", action="store_true", help="Generate factoids but skip encoding")
    parser.add_argument("--no-rescan", action="store_true", help="Skip Tunarr library rescan")
    args = parser.parse_args()

    tmp_dir = tempfile.mkdtemp(prefix="popup-")
    try:
        # Step 1: Download
        t0 = time.time()
        print("[1/5] Downloading video...")
        meta = downloader.download(args.url, tmp_dir)
        artist = meta["artist"]
        song_title = meta["song_title"]
        duration = meta["duration_seconds"]
        print(f"      {artist} — {song_title} ({duration:.0f}s)")

        # Step 2: Generate factoids
        print(f"[2/5] Generating factoids for {artist} - {song_title}...")
        facts = factoids.generate_factoids(artist, song_title)
        print(f"      {len(facts)} factoids generated")
        for i, f in enumerate(facts, 1):
            print(f"      [{i:2d}] [{f['category']}] {f['text']}")

        if args.dry_run:
            print("\n[dry-run] Skipping encode. Done.")
            return

        # Step 3: Build subtitles
        print(f"[3/5] Building subtitles ({len(facts)} factoids)...")
        timed = subtitles.build_timing(facts, duration)
        ass_path = os.path.join(tmp_dir, "popupvideo.ass")
        subtitles.build_ass(timed, ass_path, width=meta["width"], height=meta["height"],
                            artist=artist, song=song_title, duration_seconds=duration)
        print(f"      {len(timed)} bubbles timed (of {len(facts)} factoids)")

        # Step 4: Encode
        dst = resolve_output_path(artist, song_title, OUTPUT_DIR)
        print(f"[4/5] Encoding → {os.path.basename(dst)}...")
        encoder.encode(meta["video_path"], ass_path, dst)

        # Step 5: Done
        size_mb = os.path.getsize(dst) / (1024 * 1024)
        elapsed = time.time() - t0
        print(f"[5/5] Done in {elapsed:.0f}s — {size_mb:.1f} MB")
        print(f"      Saved: {dst}")

        # Tunarr rescan
        if not args.no_rescan:
            print("      Triggering Tunarr Plex library scan...", end=" ")
            ok = trigger_tunarr_scan()
            print("OK" if ok else "FAILED (non-fatal)")
            print(
                "      Run: python3 customs.py  "
                "(from /DATA/docker/tunarr/cable-build/) "
                "once Plex finishes indexing (~2 min)"
            )

    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
