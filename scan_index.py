#!/usr/bin/env python3
"""
scan_index.py — Phone Management (فون مینجمنٹ) کے RAW فولڈر کو اسکین کر کے
manifest.json بناتا ہے اور دیکھنے کے لیے HTML گیلری (gallery_pageN.html) بناتا ہے۔

استعمال:
    python3 scan_index.py /path/to/فون\\ مینجمنٹ/RAW

ضروریات (ایک بار انسٹال کریں):
    sudo apt install ffmpeg
    pip install pillow imagehash --break-system-packages
"""

import os
import sys
import json
import hashlib
import subprocess
from pathlib import Path

try:
    from PIL import Image, ExifTags
    import imagehash
except ImportError:
    print("خرابی: 'pip install pillow imagehash --break-system-packages' چلائیں")
    sys.exit(1)

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".gif", ".bmp", ".tiff"}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".3gp", ".webm", ".m4v"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".ogg", ".aac", ".opus", ".flac", ".wma"}

THUMB_SIZE = (220, 220)
PAGE_SIZE = 250  # ہر گیلری صفحے پر زیادہ سے زیادہ کتنے آئٹم دکھیں


def guess_source(path_str):
    p = path_str.lower()
    if "whatsapp" in p:
        return "WhatsApp"
    if "telegram" in p:
        return "Telegram"
    if "instagram" in p:
        return "Instagram"
    if "download" in p:
        return "Downloaded"
    if "camera" in p or "dcim" in p:
        return "Camera"
    if "screenshot" in p:
        return "Screenshot"
    if "edit" in p or "export" in p or "capcut" in p or "vn_" in p or "inshot" in p:
        return "Edited/Export"
    return "Unknown"


def ffprobe_info(path):
    """ffprobe سے duration اور encoder/software ٹیگ نکالتا ہے"""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", "-show_streams", str(path)],
            capture_output=True, text=True, timeout=30
        )
        data = json.loads(out.stdout or "{}")
        fmt = data.get("format", {})
        duration = float(fmt.get("duration", 0) or 0)
        tags = fmt.get("tags", {}) or {}
        encoder = (tags.get("encoder") or tags.get("com.android.version") or
                   tags.get("software") or "")
        width = height = None
        for s in data.get("streams", []):
            if s.get("codec_type") == "video":
                width, height = s.get("width"), s.get("height")
                break
        return duration, encoder, width, height
    except Exception:
        return 0.0, "", None, None


def image_phash(path):
    try:
        with Image.open(path) as im:
            im = im.convert("RGB")
            return str(imagehash.phash(im)), im.size
    except Exception:
        return None, (None, None)


def make_thumb(src, dst):
    if dst.exists():
        return True
    try:
        with Image.open(src) as im:
            im = im.convert("RGB")
            im.thumbnail(THUMB_SIZE)
            dst.parent.mkdir(parents=True, exist_ok=True)
            im.save(dst, "JPEG", quality=70)
            return True
    except Exception:
        return False


def video_thumb(src, dst):
    if dst.exists():
        return True
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["ffmpeg", "-y", "-ss", "1", "-i", str(src), "-frames:v", "1",
             "-vf", "scale=220:-1", str(dst)],
            capture_output=True, timeout=30
        )
        return dst.exists()
    except Exception:
        return False


def cluster_by_phash(items, threshold=6):
    """قریب المثل تصویروں کو ایک کلسٹر آئی ڈی دیتا ہے (union-find، تیز ورژن)"""
    idxs = [i for i, it in enumerate(items) if it.get("phash")]
    n = len(idxs)
    if n == 0:
        return
    print(f"مماثل تصویریں ڈھونڈی جا رہی ہیں ({n} تصویریں)...")

    parent = {i: i for i in idxs}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    # ہیش کو انٹیجر میں تبدیل کریں تاکہ موازنہ بہت تیز ہو (XOR + bit_count)
    hash_int = {i: int(items[i]["phash"], 16) for i in idxs}

    # پہلے 16 بٹس کے پریفکس سے بکٹ بنائیں — صرف قریبی امیدواروں کا آپس میں
    # موازنہ ہو، پورے سیٹ سے پورے سیٹ کا نہ ہو (O(n^2) کا بوجھ کم کرنے کے لیے)
    from collections import defaultdict
    buckets = defaultdict(list)
    for i in idxs:
        prefix = hash_int[i] >> 48
        buckets[prefix].append(i)

    total_buckets = len(buckets)
    for bi, members in enumerate(buckets.values(), 1):
        m = len(members)
        for a in range(m):
            ia = members[a]
            ha = hash_int[ia]
            for b in range(a + 1, m):
                ib = members[b]
                if (ha ^ hash_int[ib]).bit_count() <= threshold:
                    union(ia, ib)
        if bi % 500 == 0:
            print(f"...{bi}/{total_buckets} گروپ چیک ہو چکے")

    cluster_of = {}
    for i in idxs:
        cluster_of[i] = find(i)
    # count members per cluster root
    counts = {}
    for i in idxs:
        r = cluster_of[i]
        counts[r] = counts.get(r, 0) + 1
    for i, it in enumerate(items):
        if i in cluster_of:
            root = cluster_of[i]
            it["cluster"] = f"c{root}"
            it["cluster_size"] = counts[root]
        else:
            it["cluster"] = None
            it["cluster_size"] = 1


def scan(raw_root):
    raw_root = Path(raw_root).resolve()
    out_root = raw_root.parent  # فون مینجمنٹ/
    thumb_dir = out_root / "_thumbs"
    items = []
    total = 0

    for dirpath, dirnames, filenames in os.walk(raw_root):
        # فون/گیلری ایپ کے خودکار cache فولڈرز میں نہ جائیں (اصل مواد نہیں)
        dirnames[:] = [d for d in dirnames if d.lower() != ".thumbnails"]
        for fn in filenames:
            full = Path(dirpath) / fn
            ext = full.suffix.lower()
            rel = str(full.relative_to(raw_root))
            total += 1
            item = {
                "path": rel,
                "abs_path": str(full),
                "ext": ext,
                "size_bytes": full.stat().st_size,
                "source_guess": guess_source(str(full)),
            }

            if ext in IMAGE_EXT:
                item["category"] = "image"
                ph, size = image_phash(full)
                item["phash"] = ph
                item["width"], item["height"] = size
                tid = hashlib.md5(rel.encode()).hexdigest()
                thumb_path = thumb_dir / "img" / f"{tid}.jpg"
                if make_thumb(full, thumb_path):
                    item["thumb"] = str(thumb_path.relative_to(out_root))

            elif ext in VIDEO_EXT:
                item["category"] = "video"
                dur, encoder, w, h = ffprobe_info(full)
                item["duration_sec"] = round(dur, 1)
                item["encoder_tag"] = encoder
                item["width"], item["height"] = w, h
                if encoder:
                    item["source_guess"] = f"Edited (tag: {encoder})"
                tid = hashlib.md5(rel.encode()).hexdigest()
                thumb_path = thumb_dir / "vid" / f"{tid}.jpg"
                if video_thumb(full, thumb_path):
                    item["thumb"] = str(thumb_path.relative_to(out_root))

            elif ext in AUDIO_EXT:
                item["category"] = "audio"
                dur, encoder, _, _ = ffprobe_info(full)
                item["duration_sec"] = round(dur, 1)
                item["is_short_effect"] = dur > 0 and dur < 5

            else:
                item["category"] = "other"

            items.append(item)
            if total % 200 == 0:
                print(f"...{total} فائلیں اسکین ہو چکیں")

    images = [it for it in items if it["category"] == "image"]
    cluster_by_phash(images)

    manifest_path = out_root / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=1)

    print(f"\nمکمل: {total} فائلیں اسکین ہوئیں۔")
    print(f"Manifest: {manifest_path}")
    return items, out_root


def build_gallery(items, out_root):
    """ہر کیٹگری کے لیے صفحہ وار HTML گیلری بناتا ہے"""
    from collections import defaultdict
    by_cat = defaultdict(list)
    for it in items:
        by_cat[it["category"]].append(it)

    gallery_dir = out_root / "_gallery"
    gallery_dir.mkdir(exist_ok=True)

    for cat, cat_items in by_cat.items():
        if cat == "other":
            continue
        pages = [cat_items[i:i + PAGE_SIZE] for i in range(0, len(cat_items), PAGE_SIZE)]
        for pi, page_items in enumerate(pages, 1):
            html_path = gallery_dir / f"{cat}_page{pi}.html"
            write_gallery_page(html_path, cat, pi, len(pages), page_items, out_root)

    print(f"گیلری فولڈر: {gallery_dir}")
    print("براؤزر میں ہر HTML فائل کھولیں، تصویریں/ویڈیوز دیکھیں، نشان لگائیں،")
    print("پھر 'Export Selections' بٹن دبائیں — ایک .json فائل ڈاؤن لوڈ ہوگی۔")
    print("وہ تمام selections_*.json فائلیں گیلری فولڈر میں رکھ دیں، پھر organize.py چلائیں۔")


def write_gallery_page(html_path, cat, page_num, total_pages, page_items, out_root):
    cards = []
    for it in page_items:
        thumb_rel = it.get("thumb")
        thumb_src = f"../{thumb_rel}" if thumb_rel else ""
        label_bits = [it["source_guess"]]
        if it.get("cluster_size", 1) > 1:
            label_bits.append(f"مماثل گروپ: {it['cluster']} ({it['cluster_size']} تصویریں)")
        if it.get("duration_sec"):
            label_bits.append(f"{it['duration_sec']}s")
        label = " | ".join(label_bits)
        img_tag = (f'<img src="{thumb_src}" loading="lazy">' if thumb_src
                   else '<div class="noimg">🎵</div>')
        cards.append(f'''
        <div class="card" data-path="{it['path']}">
          {img_tag}
          <div class="meta">{label}</div>
          <div class="filename">{Path(it['path']).name}</div>
          <label><input type="checkbox" class="keep" checked> رکھیں (Keep)</label>
        </div>''')

    html = f'''<!DOCTYPE html>
<html lang="ur"><head><meta charset="UTF-8">
<title>{cat} - صفحہ {page_num}/{total_pages}</title>
<style>
body {{ font-family: sans-serif; background:#111; color:#eee; margin:0; padding:10px; }}
h2 {{ text-align:center; }}
.grid {{ display:grid; grid-template-columns: repeat(auto-fill, minmax(180px,1fr)); gap:12px; }}
.card {{ background:#222; border-radius:8px; padding:8px; text-align:center; }}
.card img {{ max-width:100%; border-radius:6px; }}
.noimg {{ font-size:40px; padding:30px; }}
.meta {{ font-size:11px; color:#aaa; margin-top:4px; word-break:break-word; }}
.filename {{ font-size:10px; color:#777; word-break:break-all; }}
#bar {{ position:sticky; top:0; background:#000; padding:10px; text-align:center; z-index:10; }}
button {{ padding:10px 18px; margin:4px; border-radius:6px; border:none; background:#3a7; color:#fff; font-size:15px; }}
</style></head>
<body>
<div id="bar">
  <b>{cat.upper()} — صفحہ {page_num}/{total_pages} — کل {len(page_items)} آئٹم</b><br>
  <button onclick="selectAll(true)">سب رکھیں</button>
  <button onclick="selectAll(false)">سب ہٹائیں</button>
  <button onclick="exportSel()">Export Selections (JSON ڈاؤن لوڈ)</button>
</div>
<div class="grid">
{"".join(cards)}
</div>
<script>
function selectAll(v) {{
  document.querySelectorAll('.keep').forEach(cb => cb.checked = v);
}}
function exportSel() {{
  const result = [];
  document.querySelectorAll('.card').forEach(card => {{
    const path = card.getAttribute('data-path');
    const keep = card.querySelector('.keep').checked;
    result.push({{path: path, keep: keep}});
  }});
  const blob = new Blob([JSON.stringify(result, null, 1)], {{type:'application/json'}});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'selections_{cat}_page{page_num}.json';
  a.click();
}}
</script>
</body></html>'''
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("استعمال: python3 scan_index.py /path/to/فون\\ مینجمنٹ/RAW")
        sys.exit(1)
    items, out_root = scan(sys.argv[1])
    build_gallery(items, out_root)
