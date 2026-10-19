#!/usr/bin/env python3
import os
import re
import json
import argparse
from html import unescape
from urllib.parse import urlparse
from requests import Session

ACTIVITY_URL = "https://www.strava.com/activities/%s"

parser = argparse.ArgumentParser()
parser.add_argument("activity_id", help="The Strava activity id (or activity URL)")
parser.add_argument(
    "--session", default="session.json", help="Path to saved session cookies JSON"
)
parser.add_argument(
    "--outdir", default="photos", help="Directory to download photos into"
)
args = parser.parse_args()


def load_session(s, path):
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return False
    for c in data.get("cookies", []):
        s.cookies.set(
            c["name"],
            c["value"],
            domain=c.get("domain", ".strava.com"),
            path=c.get("path", "/"),
        )
    return True


def valid_session(s):
    try:
        return "Upload and Sync Your Activities" in s.get(
            "https://www.strava.com/upload/select"
        ).text
    except Exception:
        return False


def extract_photos_json(html):
    m = re.search(r"var photosJson = (\[.*?\]);", html, re.S)
    if not m:
        return []
    try:
        return json.loads(unescape(m.group(1)))
    except json.JSONDecodeError:
        print("Failed to parse photosJson")
        return []


def photo_url(photo):
    enhanced = photo.get("enhanced_photo") or {}
    if isinstance(enhanced, str):
        return enhanced
    return enhanced.get("large") or photo.get("large") or photo.get("thumbnail")


def filename_for(url, photo):
    name = os.path.basename(urlparse(url).path)
    if not name:
        name = "%s.jpg" % photo.get("photo_id", photo.get("id", "photo"))
    return name


def download_photos(activity_id, session_path, outdir):
    s = Session()
    s.headers["User-Agent"] = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
    )

    if load_session(s, session_path) and valid_session(s):
        print("Using saved session")
    else:
        print("No valid session found.")
        print("Export a logged-in session to session.json (see README).")
        return

    r = s.get(ACTIVITY_URL % activity_id)
    if not r.ok:
        print("Unable to get activity page: HTTP %s" % r.status_code)
        return

    photos = extract_photos_json(r.text)
    if not photos:
        print("No photosJson found on activity page")
        return

    print("Found %d photo(s)" % len(photos))
    os.makedirs(outdir, exist_ok=True)
    for photo in photos:
        url = photo_url(photo)
        if not url:
            print("No downloadable URL for photo %s" % photo.get("photo_id"))
            continue
        path = os.path.join(outdir, filename_for(url, photo))
        if os.path.exists(path):
            print("Already downloaded: " + path)
            continue
        with s.get(url, stream=True) as resp:
            if not resp.ok:
                print("Failed to download %s: HTTP %s" % (url, resp.status_code))
                continue
            with open(path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1 << 16):
                    f.write(chunk)
        print("Downloaded: " + path)


def main():
    aid = args.activity_id.rstrip("/").split("/")[-1]
    download_photos(aid, args.session, args.outdir)


if __name__ == "__main__":
    main()
