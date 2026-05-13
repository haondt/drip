import asyncio
import logging
import random
from datetime import timedelta, datetime
from . import datetime_util as dt

from app.models import FeedPollState
from .state import state
from . import drip
from .config import config

_logger = logging.getLogger(__name__)

def _jitter(interval: timedelta) -> timedelta:
    factor = 1.0 + random.uniform(-config.feed_read_jitter_factor, config.feed_read_jitter_factor)
    return timedelta(seconds=interval.total_seconds() * factor)

def _clamp(interval: timedelta) -> timedelta:
    return max(config.feed_read_min_interval, min(config.feed_read_max_interval, interval))

def _increase_interval_seconds(interval: float) -> float:
    td = timedelta(seconds=interval)
    td *= config.feed_read_backoff_factor
    td = _clamp(td)
    return td.total_seconds()

def _decrease_interval_seconds(interval: float) -> float:
    td = timedelta(seconds=interval)
    td *= config.feed_read_accel_factor
    td = _clamp(td)
    return td.total_seconds()

def record_poll(feed_id: int):
    ps = state.poll_states.get(feed_id)
    if ps is None:
        ps = FeedPollState(poll_interval_seconds=config.feed_read_default_interval.total_seconds())
    
    now = dt.now_datetime()
    interval = timedelta(seconds=ps.poll_interval_seconds)
    ps.last_polled_at = dt.datetime_to_iso(now)
    ps.next_poll = dt.datetime_to_iso(now + interval + _jitter(interval))
    try:
        state.poll_states[feed_id] = ps
    except Exception as e:
        _logger.warning(f"Feed {feed_id}: failed to save poll state: {e}", exc_info=e)

async def _poll_feed(now: datetime, feed_id: int, ps: FeedPollState):
    interval = timedelta(seconds=ps.poll_interval_seconds)
    if ps.next_poll is not None:
        next_poll = dt.iso_to_datetime(ps.next_poll)
        if next_poll > now:
            return

    feed = state.feeds[feed_id]
    before_count = state.feed_entries.count(feed_id)
    ps.last_polled_at = dt.datetime_to_iso(now)
    ps.next_poll = dt.datetime_to_iso(now + interval + _jitter(interval))

    # save now in case db writes fail after sending the request
    state.poll_states[feed_id] = ps

    try:
        await asyncio.to_thread(drip.refresh_feed, feed_id)
    except Exception as e:
        _logger.warning(f"Feed {feed_id} ({feed.name}): poll failed: {e}", exc_info=e)
        # On error, back off but don't accelerate
        ps.poll_interval_seconds = _increase_interval_seconds(ps.poll_interval_seconds)
        state.poll_states[feed_id] = ps
        return

    after_count = state.feed_entries.count(feed_id)
    new_items = after_count - before_count

    if new_items == 0:
        ps.consecutive_empty += 1
        if ps.consecutive_empty >= config.feed_read_empty_backoff_threshold:
            ps.poll_interval_seconds = _increase_interval_seconds(ps.poll_interval_seconds)
            _logger.debug(f"Feed {feed_id}: {ps.consecutive_empty} empty polls, setting backoff to {dt.timedelta_to_str(timedelta(seconds=ps.poll_interval_seconds))}")
    else:
        ps.consecutive_empty = 0
        ps.poll_interval_seconds = _decrease_interval_seconds(ps.poll_interval_seconds)
        _logger.debug(f"Feed {feed_id}: {new_items} new items, accelerating to {dt.timedelta_to_str(timedelta(seconds=ps.poll_interval_seconds))}")

    state.poll_states[feed_id] = ps
    _logger.info(f"Feed {feed_id} ({feed.name}): +{new_items} items, next poll in {dt.timedelta_to_str(timedelta(seconds=ps.poll_interval_seconds))}")


async def scheduler_loop():
    _logger.info("Scheduler started")
    while True:
        now = dt.now_datetime()
        feed_ids = list(state.feeds.all_ids())

        tasks = []
        for feed_id in feed_ids:
            ps = state.poll_states.get(feed_id)
            try:
                if ps is None:
                    ps = FeedPollState(poll_interval_seconds=config.feed_read_default_interval.total_seconds())
                    state.poll_states[feed_id] = ps
            except Exception as e:
                _logger.warning(f"Feed {feed_id}: could not create poll state: {e}", exc_info=e)
                continue
            tasks.append(_poll_feed(now, feed_id, ps))

        if tasks:
            for r in await asyncio.gather(*tasks, return_exceptions=True):
                if isinstance(r, Exception):
                    _logger.error(f"Unhandled exception in poll task: {r}", exc_info=r)

        await asyncio.sleep(config.feed_read_tick_rate.total_seconds())

