# Phone Media Organizer

Automatically sort thousands of photos, videos, and audio clips from your phone
into clean folders — split by type, with near-duplicate images grouped
together for easy cleanup. Built for content creators / YouTubers who dump
their whole camera roll into one folder and need it organized fast.

**Works on Linux and macOS.** (Windows support not available yet.)

## What it does

1. **Scans** a folder recursively (however deep your subfolders go) and
   catalogs every image, video, and audio file it finds.
2. **Groups near-duplicate photos** (bursts, re-saves, screenshots taken
   twice) using perceptual image hashing — so you review one small cluster
   instead of scrolling through everything.
3. **Generates a browser-based gallery** so you can visually review photos/
   videos and mark what to keep or discard (optional — skip this step and
   everything is kept by default).
4. **Organizes everything** into a clean structure:

```
your-folder/
├── RAW/          ← your original files, never modified or deleted
├── Image/
│   └── Duplicates/   ← near-duplicate photo clusters, grouped for review
├── Video/
├── Audio/        ← short clips only (<5s, e.g. sound effects)
└── NotUseful/    ← anything you marked "discard" in the gallery
```

Files that aren't images/videos/audio (or that you don't act on) are simply
left untouched in `RAW/`.

## Requirements

- Python 3.9+
- ffmpeg / ffprobe (installed automatically by `setup.sh`)
- ~Nothing else — `setup.sh` handles the rest in a self-contained virtual
  environment.

## Installation

```bash
git clone https://github.com/YOUR_USERNAME/phone-media-organizer.git
cd phone-media-organizer
chmod +x setup.sh
./setup.sh
```

This installs `ffmpeg` (via `apt`/`dnf`/`pacman` on Linux, or `brew` on
macOS) and creates a local `venv/` with the required Python packages
(Pillow, imagehash). It does not touch your system Python.

## Usage

Point it at the folder containing your raw phone dump (it can have any
number of subfolders inside — WhatsApp exports, Downloads, DCIM, etc.):

```bash
# 1. Scan and build the catalog + review gallery
./venv/bin/python3 scan_index.py "/path/to/RAW"

# 2. (Optional) Review — open the HTML files in _gallery/ in your browser,
#    uncheck anything you don't want, click "Export Selections", then move
#    the downloaded selections_*.json files into the _gallery/ folder.

# 3. Preview what will happen (nothing is copied yet)
./venv/bin/python3 organize.py "/path/to/RAW"

# 4. Actually organize the files
./venv/bin/python3 organize.py "/path/to/RAW" --apply

# Or move instead of copy (frees up space, empties RAW/ of sorted files):
./venv/bin/python3 organize.py "/path/to/RAW" --apply --move
```

`RAW/` is never deleted or modified unless you pass `--move`. The default
is always a safe copy.

## Notes

- Android/gallery-app cache thumbnails (folders literally named
  `.thumbnails`) are automatically skipped — they aren't real content.
- Re-running `scan_index.py` after an interruption skips thumbnails that
  were already generated, so it resumes quickly instead of starting over.
- Duplicate detection uses a perceptual hash (`imagehash.phash`) with a
  configurable distance threshold (default `6`) — edit the `threshold`
  value in `scan_index.py` if you want stricter/looser grouping.

## Limitations (contributions welcome!)

- No Windows support yet.
- No terminal-free GUI yet — this is a command-line tool.
- Naming is based on folder/type/metadata, not AI-based image content
  recognition (e.g. it won't rename a photo to `boy_red_shirt_mountain.jpg`).
- Basic error handling — corrupted files are logged and skipped, not
  auto-repaired.

## License

MIT — see [LICENSE](LICENSE).
