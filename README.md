# Huey Pop Up Video

Turn a YouTube music video into a VH1 *Pop Up Video*–style episode: AI-written
factoid bubbles burned into the video, a blue intro card, and a corner tag.
Finished files land in the HueyTV Tunarr library for the Pop-Up Video channel.

```
YouTube URL → yt-dlp (≤1080p) → Claude factoids → ASS subtitles → ffmpeg (VAAPI/QSV) → .mp4
```

## Requirements

- Linux with an Intel GPU: encoding uses `h264_vaapi` on `/dev/dri/renderD128`,
  falling back to `h264_qsv`. (There is no libx264 software path.)
- `ffmpeg` built with libass, VAAPI, and QSV
- [`yt-dlp`](https://github.com/yt-dlp/yt-dlp). The path is set by `YTDLP` in `downloader.py`.
- Python 3.10+
- An Anthropic API key

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env          # then set ANTHROPIC_API_KEY
```

**YouTube cookies (optional, but usually needed).** If YouTube asks the server
to "confirm you're not a bot," export Netscape-format cookies from a logged-in
browser to `cookies.txt` in this folder. Then run `chmod 600 cookies.txt`.
`downloader.py` uses the file automatically when it exists. Keep the file
writable, because yt-dlp saves refreshed cookies back to it. Both `cookies.txt`
and `.env` are gitignored.

## Usage

```bash
python3 popupvideo.py -u "https://www.youtube.com/watch?v=..."
```

| Flag          | Effect                                                   |
|---------------|----------------------------------------------------------|
| `--dry-run`   | Download and print the factoids, but skip the encode     |
| `--no-rescan` | Don't ask Tunarr to rescan the library afterwards        |

The output is saved as `<Artist> - <Song> (Huey Pop Up Video).mp4`. If that name
is taken, the tool adds ` (2)`, ` (3)`, and so on, so it never overwrites a file.

### Getting it on the channel

Tunarr's scan only re-syncs what Plex already knows about. So after a render:

1. In Plex, run **Scan Library Files** on the Music Videos library, so Plex indexes the new file.
2. Let the tool's Tunarr scan run, or trigger it again.
3. Run `python3 customs.py` from `../cable-build/` to add the file to the Pop-Up Video channel.

## Configuration

These values are currently constants in the code:

| Setting            | Where            | Default                                       |
|--------------------|------------------|-----------------------------------------------|
| Output folder      | `popupvideo.py`  | `/media/HueyRaid1/TV/Music Videos/Pop Up Video` |
| Tunarr scan URL    | `popupvideo.py`  | `http://127.0.0.1:8010/api/media-sources/…/scan` |
| yt-dlp binary      | `downloader.py`  | `/DATA/bin/yt-dlp`                            |
| VAAPI device       | `encoder.py`     | `/dev/dri/renderD128`                         |
| Claude model       | `factoids.py`    | `claude-opus-5-5`                             |

## Layout

| File            | Role                                                                   |
|-----------------|------------------------------------------------------------------------|
| `popupvideo.py` | The CLI, which runs the 5 stages                                        |
| `downloader.py` | yt-dlp download (cookies, `web_safari` client for HD) and artist/title parsing |
| `factoids.py`   | Claude prompt that returns 8–10 `{text, category}` factoids             |
| `subtitles.py`  | Bubble timing and ASS generation: 5 zones, category icons, pop-in, intro card, corner tag |
| `encoder.py`    | ffmpeg burn-in that tries VAAPI first, then QSV, and deletes partial output on failure |
| `fonts/`        | Bundled fonts for libass (OFL-licensed Google Fonts)                    |
| `design/`       | Approved VH1 mockups (`mock.py`, `.ass` samples, `index.html`)          |
| `tests/`        | pytest suite                                                            |

## Tests

```bash
python3 -m pytest -q
```

The tests mock the network, the API, and ffmpeg. The end-to-end `--dry-run`
test is skipped by default. To run it, which really downloads a video and calls
Claude:

```bash
INTEGRATION=1 TEST_URL="https://www.youtube.com/watch?v=..." python3 -m pytest tests/test_integration.py
```
