#!/usr/bin/env python3
"""
organize.py — manifest.json اور (اختیاری) selections_*.json کی بنیاد پر
فائلوں کو Image/ Video/ Audio/ NotUseful/ فولڈرز میں کاپی یا منتقل کرتا ہے۔
RAW فولڈر کبھی خالی نہیں کیا جاتا اگر --move استعمال نہ کیا جائے (ڈیفالٹ = کاپی)۔

استعمال:
    # پہلے صرف دیکھیں کیا ہوگا (کچھ تبدیل نہیں ہوگا):
    python3 organize.py /path/to/فون\\ مینجمنٹ/RAW

    # اصل میں کاپی کریں:
    python3 organize.py /path/to/فون\\ مینجمنٹ/RAW --apply

    # کاپی کی بجائے منتقل کریں (RAW سے نکل جائیں گی):
    python3 organize.py /path/to/فون\\ مینجمنٹ/RAW --apply --move
"""

import sys
import json
import shutil
import argparse
from pathlib import Path
from collections import Counter


def load_selections(gallery_dir):
    sel = {}
    if not gallery_dir.exists():
        return sel
    for f in gallery_dir.glob("selections_*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            for row in data:
                sel[row["path"]] = row["keep"]
        except Exception as e:
            print(f"تنبیہ: {f} پڑھنے میں مسئلہ: {e}")
    return sel


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw_path")
    ap.add_argument("--apply", action="store_true", help="اصل میں فائلیں کاپی کریں (ورنہ صرف رپورٹ)")
    ap.add_argument("--move", action="store_true", help="کاپی کی بجائے منتقل کریں")
    args = ap.parse_args()

    raw_root = Path(args.raw_path).resolve()
    out_root = raw_root.parent
    manifest_path = out_root / "manifest.json"
    if not manifest_path.exists():
        print("پہلے scan_index.py چلائیں — manifest.json نہیں ملا۔")
        sys.exit(1)

    items = json.loads(manifest_path.read_text(encoding="utf-8"))
    selections = load_selections(out_root / "_gallery")

    dest_counts = Counter()
    plan = []

    for it in items:
        cat = it["category"]
        rel = it["path"]
        keep = selections.get(rel, True)  # منتخب نہ ہو تو ڈیفالٹ = رکھیں

        # فون/گیلری ایپ کے خودکار cache thumbnails کو نظرانداز کریں — یہ اصل
        # مواد نہیں، خالی جگہ گھیرتی ہیں۔ RAW میں ہی چھوڑ دیں۔
        if ".thumbnails" in rel.lower():
            continue

        if cat == "image":
            if not keep:
                dest = out_root / "NotUseful" / "Image" / rel
            elif it.get("cluster_size", 1) > 1:
                dest = out_root / "Image" / "Duplicates" / it["cluster"] / Path(rel).name
            else:
                dest = out_root / "Image" / rel

        elif cat == "video":
            if not keep:
                dest = out_root / "NotUseful" / "Video" / rel
            else:
                dest = out_root / "Video" / rel

        elif cat == "audio" and it.get("is_short_effect"):
            dest = out_root / "Audio" / rel

        else:
            continue  # RAW میں ہی رہے گی

        plan.append((Path(it["abs_path"]), dest))
        dest_counts[str(dest.parent.relative_to(out_root))] += 1

    print("منصوبہ (کتنی فائلیں کہاں جائیں گی):")
    for folder, n in sorted(dest_counts.items()):
        print(f"  {folder}: {n}")
    print(f"\nکل فائلیں منتقل/کاپی ہوں گی: {len(plan)}")
    print(f"باقی فائلیں RAW میں ہی رہیں گی: {len(items) - len(plan)}")

    if not args.apply:
        print("\n(یہ صرف رپورٹ تھی — کچھ کاپی نہیں ہوا۔ اصل کاپی کے لیے --apply لگائیں)")
        return

    action = shutil.move if args.move else shutil.copy2
    done = 0
    for src, dest in plan:
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            if dest.exists():
                dest = dest.with_name(dest.stem + "_dup" + dest.suffix)
            action(str(src), str(dest))
            done += 1
        except Exception as e:
            print(f"خرابی: {src} -> {dest}: {e}")

    print(f"\nمکمل۔ {done} فائلیں {'منتقل' if args.move else 'کاپی'} ہو گئیں۔")


if __name__ == "__main__":
    main()
