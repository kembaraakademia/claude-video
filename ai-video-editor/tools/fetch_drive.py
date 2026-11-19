"""Download every video in a Google Drive folder (shared "anyone with the link") into raw_footage/.

usage: python tools/fetch_drive.py <drive-folder-url> [--out raw_footage]
File names are kept (spaces replaced by _). Already-downloaded files are skipped.
"""
import argparse
import pathlib
import subprocess

import gdown

VIDEO_EXT = {".mov", ".mp4", ".m4v", ".mkv", ".avi", ".webm", ".mts"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--out", default=str(pathlib.Path(__file__).resolve().parent.parent / "raw_footage"))
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    files = gdown.download_folder(a.url, skip_download=True, quiet=True)
    for f in files:
        name = pathlib.Path(f.path).name.replace(" ", "_")
        if pathlib.Path(name).suffix.lower() not in VIDEO_EXT:
            print("skip (not video):", f.path)
            continue
        dst = out / name
        if dst.exists() and dst.stat().st_size > 0:
            print("exists:", dst.name)
            continue
        # direct usercontent download works for large files without the HTML confirm page
        url = f"https://drive.usercontent.google.com/download?id={f.id}&export=download&confirm=t"
        subprocess.run(["curl", "-sSL", "-o", str(dst), url], check=True)
        print(f"downloaded: {dst.name} ({dst.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
