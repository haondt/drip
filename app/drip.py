import json
import math
from string.templatelib import convert
import feedparser
from .state import state
from .models import *
from .config import config
from feedgen.feed import FeedGenerator
from . import datetime_util as dt 
import uuid
import requests

def refresh_feed(feed_id: int):
    feed = state.feeds[feed_id]
    resp = requests.get(feed.url, timeout=config.feed_read_timeout.total_seconds())
    resp.raise_for_status()
    d = feedparser.parse(resp.content)

    parsed_feed = d.get('feed')
    if parsed_feed:
        # for reference: https://datatracker.ietf.org/doc/html/rfc4287
        feed.metadata = FeedMetadata(
            title=parsed_feed.get('title'),
            updated=dt.normalize_datetime(parsed_feed.get('updated_parsed')) if parsed_feed.get('updated_parsed') else None,
            subtitle=parsed_feed.get('subtitle'),
            links = [
                FeedLink(
                    href=parsed_link.get('href'),
                    rel=parsed_link.get('rel'),
                    type=parsed_link.get('type'),
                )
                for parsed_link in parsed_feed.get('links', [])
            ],
            id=parsed_feed.get('id'),
            icon=parsed_feed.get('icon'),
            logo=parsed_feed.get('logo'),
        )
        state.feeds[feed_id] = feed

    for parsed_entry in d.get('entries', []):
        entry = FeedEntry(
            id=parsed_entry.get('id'),
            title=parsed_entry.get('title'),
            summary=parsed_entry.get('summary'),
            published="",
            authors=[
                FeedPerson(
                    name=a.get('name'),
                    url=a.get('url', a.get('uri')),
                    email=a.get('email'),
                )
                for a in parsed_entry.get('authors', [])
            ],
            contributors=[
                FeedPerson(
                    name=c.get('name'),
                    url=c.get('url', c.get('uri')),
                    email=c.get('email'),
                )
                for c in parsed_entry.get('contributors', [])
            ],
            links=[
                FeedLink(
                    href=l.get('href'),
                    rel=l.get('rel'),
                    type=l.get('type'),
                )
                for l in parsed_entry.get('links', [])
            ],
            contents=[
                FeedEntryContent(
                    type=c.get('type'),
                    value=c.get('value'),
                    src=c.get('src'),
                )
                for c in parsed_entry.get('content', [])
            ],
        )

                
        published = parsed_entry.get('published_parsed')
        if published:
            entry.published = dt.datetime_to_iso(dt.tuple9_to_datetime(published))
        else:
            # we have to save the computed id into the entry
            # otherwise next time we compute the id it will change 
            # according to the newly-set published value
            if not entry.id:
                entry.id = entry.compute_id()
            existing_entry = state.feed_entries.get((feed_id, entry.id))
            if existing_entry:
                entry.published = existing_entry.published
            else:
                entry.published = dt.now_iso()

        state.feed_entries[feed_id, entry.compute_id()] = entry

def build_digest_html(feed: Feed, entries: list[FeedEntry]):
    items = []

    for i, entry in enumerate(entries):
        entry_link = None

        if entry.links:
            for link in entry.links:
                if link.rel == "alternate":
                    entry_link = link.href
                    break
            if entry_link is None:
                entry_link = entry.links[0].href

        entry_content = entry.summary or (
            entry.contents[0].value if entry.contents else None
        )

        entry_title = (
            entry.title
            or entry_link
            or entry.id
            or feed.metadata.title
            or feed.name
        )

        entry_id = f"entry-{i}"

        items.append({
            "id": entry_id,
            "link": entry_link,
            "content": entry_content,
            "title": entry_title,
        })

    html = []

    html.append(f"<h3>Contents ({len(items)})</h3>")
    html.append("<ul>")

    for item in items:
        html.append(
            f'<li><a href="#{item["id"]}">{item["title"]}</a></li>'
        )

    html.append("</ul>")

    for item in items:
        html.append(f'<h1 id="{item["id"]}"><hr/></h1>')

        if item["link"]:
            html.append(
                f'<h3><a href="{item["link"]}">{item["title"]}</a></h3>'
            )
        else:
            html.append(f'<h3>{item["title"]}</h3>')

        if item["content"]:
            html.append(item["content"])

        html.append('<p><a href="#top">Back to table of contents</a></p>')

    return "".join(html)

def get_drop_html(feed_id: int, index: str) -> str:
    feed = state.feeds[feed_id]

    if dt.validate_timespan_str(feed.period):
        period_index = int(index)
        created = dt.iso_to_datetime(feed.created)
        period = dt.parse_timespan(feed.period)

        now = dt.now_datetime()

        min_published = created + period_index * period
        max_published = created + (period_index + 1) * period

    else:
         max_published = dt.iso_to_datetime(index)
         seeker = dt.parse_cron_schedule(feed.period, max_published)
         min_published = seeker.prev()
         print(max_published, min_published)

    entries = state.feed_entries.query(
        feed_id,
        dt.datetime_to_iso(min_published),
        dt.datetime_to_iso(max_published),
    )

    content = build_digest_html(feed, entries)
    return f'<!doctype html><html><head></head><body>{content}</body></html>'

def query_feed(feed_id: int) -> FeedGenerator:
    feed = state.feeds[feed_id]
    fg = FeedGenerator()
    fg.id(f'urn:uuid:{uuid.uuid5(config.namespace_uuid, str(feed_id))}')
    fg.title(feed.metadata.title or feed.name)
    fg.description(feed.metadata.subtitle or feed.name)
    if feed.metadata.links:
        for link in feed.metadata.links:
            fg.link(**{ k: v for k, v in link.model_dump().items() if v is not None and k in ['href', 'rel', 'type']})
    if feed.metadata.icon:
        fg.icon(feed.metadata.icon)
    if feed.metadata.logo:
        fg.logo(feed.metadata.logo)
    if feed.metadata.subtitle:
        fg.subtitle(feed.metadata.subtitle)
    if feed.metadata.updated:
        fg.updated(feed.metadata.updated)

    if dt.validate_timespan_str(feed.period):
        period = dt.parse_timespan(feed.period)
        now = dt.now_datetime()
        created = dt.iso_to_datetime(feed.created)
        current_period_index = (now - created) // period
        oldest_period_index = current_period_index - config.max_drops + 1

        # intentionally omitting the current period, as we cant emit it until the period completes
        for period_index in range(oldest_period_index, current_period_index):
            min_published = created + period_index * period
            max_published = created + (period_index + 1) * period
            entries = state.feed_entries.query(
                feed_id,
                dt.datetime_to_iso(min_published),
                dt.datetime_to_iso(max_published),
            )

            if len(entries) == 0:
                continue

            fe = fg.add_entry()
            digest_id = uuid.uuid5(config.namespace_uuid, f'{feed_id}:{period_index}')
            fe.id(f'urn:uuid:{digest_id}')
            fe.title(f'{feed.name} #{period_index + config.max_drops}')
            fe.published(max_published)
            fe.updated(max_published)
            if config.base_url:
                fe.link(link={'href': config.base_url + f'/drops/drop/{feed_id}:{period_index}', 'rel': 'alternate', 'type': 'text/html'})

            content = build_digest_html(feed, entries)
            fe.content(content=content, type='text/html')
    else:
        now = dt.now_datetime(feed.creation_tz)
        seeker = dt.parse_cron_schedule(feed.period, now)
        # intentionally omitting the current (first) period, as we cant emit it until the period completes
        max_published = seeker.prev()
        for _ in range(config.max_drops):
            min_published = seeker.prev()

            entries = state.feed_entries.query(
                feed_id,
                dt.datetime_to_iso(min_published),
                dt.datetime_to_iso(max_published),
            )

            if len(entries) == 0:
                max_published = min_published
                continue

            fe = fg.add_entry()
            digest_raw_id = f'{feed_id}:{dt.datetime_to_iso(max_published, convert_to_utc=False)}'
            digest_id = uuid.uuid5(config.namespace_uuid, digest_raw_id)
            fe.id(f'urn:uuid:{digest_id}')
            fe.title(f'{feed.name} {dt.humanize_datetime(max_published)}')
            fe.published(max_published)
            fe.updated(max_published)
            if config.base_url:
                fe.link(link={'href': config.base_url + f'/drops/drop/{digest_raw_id}', 'rel': 'alternate', 'type': 'text/html'})

            content = build_digest_html(feed, entries)
            fe.content(content=content, type='text/html')

            max_published = min_published

    return fg
