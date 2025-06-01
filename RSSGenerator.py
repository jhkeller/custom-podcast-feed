import json, hashlib, html
from datetime import datetime

import feedparser
import PyRSS2Gen


def first_audio_url(entry):
    """
    Return the first URL in an entry that looks like playable audio.
    Priority:
        1. links[] / enclosures[] whose 'type' starts with 'audio/'
        2. links / enclosures with common audio extensions
    """
    audio_exts = (".mp3", ".m4a", ".aac", ".ogg", ".opus", ".wav")
    # feedparser flattens <enclosure> into both .links and .enclosures
    for link in entry.get("enclosures", []) + entry.get("links", []):
        url = link.get("href") or link.get("url")
        if not url:
            continue
        mime = (link.get("type") or "").lower()
        if mime.startswith("audio/"):
            return url
        if url.lower().split("?", 1)[0].endswith(audio_exts):
            return url
    return None


# ---------- load feed list ----------
with open("feeds.json", "r", encoding="utf-8") as f:
    feeds_cfg = json.load(f)

latest_items = []

for feed in feeds_cfg.get("feeds", []):
    name = feed.get("name", "Unnamed Feed")
    url  = feed.get("url")
    if not url:
        print(f"⚠️  Skipping '{name}' – no URL.")
        continue

    parsed = feedparser.parse(url)
    if parsed.bozo:
        print(f"⚠️  Problem parsing '{name}': {parsed.bozo_exception}")
        continue

    # loop through entries until we find one with playable audio
    for entry in parsed.entries:
        audio_url = first_audio_url(entry)
        if not audio_url:
            print(f"  ↪︎ '{name}': entry '{entry.get('title','untitled')}' has no audio, skipping.")
            continue

        # ----- basic meta -----
        title_raw = entry.get("title", "No Title")
        title     = html.escape(title_raw)
        desc      = html.escape(entry.get("summary", entry.get("description", "")))
        link      = entry.get("link", entry.get("id", url))
        tm        = entry.get("published_parsed") or entry.get("updated_parsed")
        pub_date  = datetime(*tm[:6]) if tm else datetime.utcnow()

        guid_text = f"{url}_{title_raw}_{pub_date.isoformat()}"
        guid      = hashlib.sha256(guid_text.encode()).hexdigest()

        latest_items.append(
            PyRSS2Gen.RSSItem(
                title      = f"{name}: {title}",
                link       = link,
                description= desc,
                pubDate    = pub_date,
                guid       = PyRSS2Gen.Guid(guid),
                enclosure  = PyRSS2Gen.Enclosure(
                                url    = audio_url,
                                length = "0",
                                type   = "audio/mpeg"   # safest default; players ignore length
                             ),
            )
        )
        break  # only want the first *valid* episode for this feed

# ---------- sort & build combined feed ----------
latest_items.sort(key=lambda i: i.pubDate, reverse=True)

rss = PyRSS2Gen.RSS2(
    title       = "Latest‑Episode Combo Feed",
    link        = "http://localhost:8000/customfeed.xml",
    description = "The newest episode from each of my favourite shows",
    lastBuildDate = datetime.utcnow(),
    items       = latest_items,
)

# add podcast‑friendly channel tags
xml = rss.to_xml(encoding="utf-8").replace(
    "<channel>",
    "<channel>\n    <language>en-us</language>\n    <itunes:author>CustomFeed</itunes:author>\n    <itunes:explicit>no</itunes:explicit>"
)

with open("customfeed.xml", "w", encoding="utf-8") as f:
    f.write(xml)

print(f"✅ Wrote customfeed.xml with {len(latest_items)} shows.")
