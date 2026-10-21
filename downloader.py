import re
import json
import subprocess
from pathlib import Path

YTDLP = "/DATA/bin/yt-dlp"
# Netscape-format YouTube cookies; used when present to get past "confirm you're not a bot"
COOKIES_FILE = str(Path(__file__).parent / "cookies.txt")

_SUFFIX_RE = re.compile(
    r'\s*\((?:Official[^)]*|Lyrics?\s+Video|Audio|HD|4K|Remaster(?:ed)?|'
    r'Visualizer|Lyric\s+Video|feat\.[^)]*)\)',
    re.IGNORECASE,
)


def parse_title(title: str, uploader: str) -> tuple[str, str]:
    """Parse artist and song title from a YouTube video title string."""
    # Heuristic 1: "Artist - Title ..."
    if " - " in title:
        parts = title.split(" - ", 1)
        artist = parts[0].strip()
        song = _SUFFIX_RE.sub("", parts[1]).strip()
        return artist, song

    # Heuristic 2: "Title by Artist"
    by_match = re.search(r'\bby\s+(.+)$', title, re.IGNORECASE)
    if by_match:
        artist = by_match.group(1).strip()
        return artist, title

    # Fallback: uploader as artist, full title as song
    return uploader, title


def download(url: str, tmp_dir: str) -> dict:
    """Download a YouTube video and return metadata + local path."""
    cmd = [
        YTDLP,
        "--format", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best",
        "--merge-output-format", "mp4",
        "--output", f"{tmp_dir}/%(id)s.%(ext)s",
        "--print-json",
        "--no-playlist",
        # the default client went SABR-only (360p max) once cookies were in use; web_safari still lists HD
        "--extractor-args", "youtube:player_client=web_safari,default",
    ]
    if Path(COOKIES_FILE).is_file():
        cmd += ["--cookies", COOKIES_FILE]
    result = subprocess.run(
        cmd + [url],
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {result.stderr.decode()[-800:]}")

    info = json.loads(result.stdout)
    youtube_id = info["id"]
    video_path = str(Path(tmp_dir) / f"{youtube_id}.mp4")
    artist, song_title = parse_title(info.get("title", ""), info.get("uploader", ""))
    return {
        "video_path": video_path,
        "artist": artist,
        "song_title": song_title,
        "duration_seconds": float(info.get("duration", 0)),
        "width": info.get("width") or 1920,
        "height": info.get("height") or 1080,
        "youtube_id": youtube_id,
    }
