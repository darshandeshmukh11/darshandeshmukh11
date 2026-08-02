#!/usr/bin/env python3
"""
Fetch RSS feed and inject all project items into README.md between markers.
Usage: python3 scripts/update_projects.py --feed <feed_url> --readme README.md
"""
import argparse
import datetime
import re
import sys
from html import unescape
from urllib.request import urlopen, Request
from xml.etree import ElementTree as ET

START_MARKER = "<!-- START_PROJECTS -->"
END_MARKER = "<!-- END_PROJECTS -->"

def fetch_feed(url):
    req = Request(url, headers={"User-Agent": "github-actions-readme-updater/1.0"})
    with urlopen(req, timeout=20) as r:
        return r.read()

def strip_tags(html):
    # crude tag stripper — good enough for short excerpts
    text = re.sub(r"<[^>]+>", "", html)
    return unescape(text).strip()

def parse_items(xml_bytes):
    root = ET.fromstring(xml_bytes)
    channel = root.find('channel')
    if channel is None:
        # try default namespace handling
        ns = {'rss': root.tag.split('}')[0].strip('{')} if '}' in root.tag else {}
        channel = root.find('rss:channel', ns)
    items = []
    for item in channel.findall('item'):
        title_el = item.find('title')
        link_el = item.find('link')
        date_el = item.find('pubDate')
        desc_el = item.find('description')
        title = title_el.text if title_el is not None else 'Untitled'
        link = link_el.text if link_el is not None else ''
        pub = date_el.text if date_el is not None else ''
        desc_html = desc_el.text if desc_el is not None else ''
        desc = strip_tags(desc_html)
        # keep only the first paragraph or 400 chars
        short = desc.split('\n')[0]
        if len(short) > 400:
            short = short[:397] + '...'
        items.append({'title': title.strip(), 'link': link.strip(), 'pub': pub.strip(), 'desc': short.strip()})
    return items

def render_markdown(items, feed_url):
    now = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    md = []
    md.append(f"<!-- Projects generated from {feed_url} on {now} -->\n")
    if not items:
        md.append("*No projects found in the feed.*\n")
        return '\n'.join(md)

    for i, it in enumerate(items, 1):
        md.append(f"### {it['title']}")
        md.append('')
        md.append(f"[View project]({it['link']})  •  Published: {it['pub']}")
        md.append('')
        if it['desc']:
            # indent description as blockquote for readability
            desc_lines = it['desc'].splitlines()
            for line in desc_lines:
                md.append(f"> {line}")
            md.append('')
        md.append('---')
        md.append('')
    return '\n'.join(md)

def replace_between_markers(readme_text, new_md):
    start = readme_text.find(START_MARKER)
    end = readme_text.find(END_MARKER)
    if start == -1 or end == -1 or end < start:
        raise RuntimeError('Markers not found or invalid in README.md')
    before = readme_text[:start + len(START_MARKER)]
    after = readme_text[end:]
    # ensure single blank line separation
    return before + "\n\n" + new_md.strip() + "\n\n" + after

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--feed', required=True, help='RSS feed URL')
    parser.add_argument('--readme', default='README.md', help='Path to README file')
    args = parser.parse_args()

    try:
        xml = fetch_feed(args.feed)
    except Exception as e:
        print('Failed to fetch feed:', e, file=sys.stderr)
        sys.exit(1)

    try:
        items = parse_items(xml)
    except Exception as e:
        print('Failed to parse feed XML:', e, file=sys.stderr)
        sys.exit(1)

    new_md = render_markdown(items, args.feed)

    with open(args.readme, 'r', encoding='utf-8') as f:
        readme = f.read()

    try:
        updated = replace_between_markers(readme, new_md)
    except Exception as e:
        print('Failed to update README markers:', e, file=sys.stderr)
        sys.exit(1)

    if updated == readme:
        print('README already up-to-date')
        return

    with open(args.readme, 'w', encoding='utf-8') as f:
        f.write(updated)

    print('README updated with', len(items), 'projects')

if __name__ == '__main__':
    main()