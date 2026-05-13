from __future__ import annotations
import sqlite3, threading, asyncio

from .models import *
from .config import config


class State:
    def __init__(self):
        self.db_path = config.db_path
        self._lock = threading.Lock()
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=(not config.is_development))
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS feeds  (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data TEXT NOT NULL
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS feed_entries  (
                    feed_id INTEGER NOT NULL,
                    entry_id TEXT NOT NULL,
                    published REAL NOT NULL,
                    data TEXT NOT NULL,
                    PRIMARY KEY (feed_id, entry_id),
                    FOREIGN KEY (feed_id) REFERENCES feeds(id)
                        ON DELETE CASCADE
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS feed_poll_states  (
                    feed_id INTEGER PRIMARY KEY,
                    data TEXT NOT NULL,
                    FOREIGN KEY (feed_id) REFERENCES feeds(id)
                        ON DELETE CASCADE
                )
            ''')
            conn.commit()


    class FeedDict:
        def __init__(self, state: State):
            self.state = state

        def add(self, feed: Feed) -> int:
            with self.state._lock, self.state._get_conn() as conn:
                c = conn.cursor()
                c.execute('INSERT into feeds (data) VALUES (?)', (feed.model_dump_json(),))
            assert c.lastrowid is not None
            return c.lastrowid

        def __setitem__(self, feed_id: int, feed: Feed) -> None:
            with self.state._lock, self.state._get_conn() as conn:
                c = conn.cursor()
                c.execute(
                    '''
                    INSERT INTO feeds (id, data) VALUES (?, ?)
                    ON CONFLICT(id) DO UPDATE SET data = excluded.data
                    ''',
                    (feed_id, feed.model_dump_json())
                )

        def __delitem__(self, feed_id: int) -> None:
            with self.state._lock, self.state._get_conn() as conn:
                c = conn.cursor()
                c.execute('DELETE FROM feeds WHERE id = ?', (feed_id,))
            
        def get(self, id) -> Feed | None:
            with self.state._lock, self.state._get_conn() as conn:
                c = conn.cursor()
                c.execute('SELECT data FROM feeds WHERE id = ?', (id,))
                row = c.fetchone()

                if row:
                    return Feed.model_validate_json(row[0])
            return None

        def __getitem__(self, id) -> Feed:
            feed = self.get(id)
            if not feed:
                raise ValueError(f'Feed {id} not found.')
            return feed

        def all(self) -> dict[int, Feed]:
            with self.state._lock, self.state._get_conn() as conn:
                c = conn.cursor()
                c.execute('SELECT id, data FROM feeds')

                return {
                    row[0]: Feed.model_validate_json(row[1])
                    for row in c.fetchall()
                }

        def all_ids(self) -> list[int]:
            with self.state._lock, self.state._get_conn() as conn:
                c = conn.cursor()
                c.execute('SELECT id FROM feeds')
                return [row[0] for row in c.fetchall()]

    @property
    def feeds(self) -> State.FeedDict:
        return self.FeedDict(self)

    class FeedEntryDict:
        def __init__(self, state: State):
            self.state = state

        def __setitem__(self, composite_key: tuple[int, str], entry: FeedEntry):
            feed_id, entry_id = composite_key
            with self.state._lock, self.state._get_conn() as conn:
                c = conn.cursor()
                c.execute('REPLACE into feed_entries (feed_id, entry_id, published, data) VALUES (?, ?, ?, ?)', (feed_id, entry_id, entry.published, entry.model_dump_json()))


        def get(self, composite_key: tuple[int, str]) -> FeedEntry | None:
            feed_id, entry_id = composite_key
            with self.state._lock, self.state._get_conn() as conn:
                c = conn.cursor()
                c.execute('SELECT data FROM feed_entries WHERE feed_id = ? AND entry_id = ?', (feed_id, entry_id))
                row = c.fetchone()
                if row:
                    return FeedEntry.model_validate_json(row[0])
            return None

        def __getitem__(self, composite_key: tuple[int, str]) -> FeedEntry:
            feed_entry = self.get(composite_key)
            if not feed_entry:
                raise ValueError(f'FeedEntry {composite_key[0]},{composite_key[1]} not found.')
            return feed_entry

        def count(self, feed_id: int):
            with self.state._lock, self.state._get_conn() as conn:
                c = conn.cursor()
                c.execute('SELECT COUNT(*) FROM feed_entries WHERE feed_id = ?', (feed_id,))
                return c.fetchone()[0]


        def query(self, feed_id: int, min_published: str | None = None, max_published: str | None = None) -> list[FeedEntry]:
            conditions = ['feed_id = ?']
            params: list = [feed_id]

            if min_published:
                conditions.append('published > ?')
                params.append(min_published)
            if max_published:
                conditions.append('published <= ?')
                params.append(max_published)

            sql = f"SELECT data FROM feed_entries WHERE {' AND '.join(conditions)} ORDER BY published"

            with self.state._lock, self.state._get_conn() as conn:
                c = conn.cursor()
                c.execute(sql, params)
                return [FeedEntry.model_validate_json(row[0]) for row in c.fetchall()]

    @property
    def feed_entries(self) -> State.FeedEntryDict:
        return self.FeedEntryDict(self)

    class FeedPollStateDict:
        def __init__(self, state: State):
            self.state = state

        def get(self, feed_id: int) -> FeedPollState | None:
            with self.state._lock, self.state._get_conn() as conn:
                c = conn.cursor()
                c.execute(
                    'SELECT data FROM feed_poll_states WHERE feed_id = ?',
                    (feed_id,)
                )
                row = c.fetchone()
                if row:
                    return FeedPollState.model_validate_json(row[0])
            return None

        def __setitem__(self, feed_id: int, poll_state: FeedPollState):
            with self.state._lock, self.state._get_conn() as conn:
                c = conn.cursor()
                c.execute(
                    '''
                    INSERT INTO feed_poll_states (feed_id, data) VALUES (?, ?)
                    ON CONFLICT(feed_id) DO UPDATE SET data = excluded.data
                    ''',
                    (feed_id, poll_state.model_dump_json())
                )

        def all(self) -> dict[int, FeedPollState]:
            with self.state._lock, self.state._get_conn() as conn:
                c = conn.cursor()
                c.execute('SELECT feed_id, data FROM feed_poll_states')

                return {
                    row[0]: FeedPollState.model_validate_json(row[1])
                    for row in c.fetchall()
                }

    @property
    def poll_states(self) -> State.FeedPollStateDict:
        return self.FeedPollStateDict(self)



state = State()
