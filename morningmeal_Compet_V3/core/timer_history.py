"""Local daily aggregates, independent of resettable display counters."""
from datetime import date, datetime, time, timedelta
from pathlib import Path
import sqlite3
import time as clock


def statistics_day(timestamp=None, tz=None):
    moment = datetime.fromtimestamp(clock.time() if timestamp is None else timestamp, tz)
    return moment.date() - timedelta(days=moment.hour < 6)


def period_bounds(day, period):
    if period == 'week':
        start = day - timedelta(days=day.weekday())
        return start, start + timedelta(days=7)
    if period == 'month':
        start = day.replace(day=1)
        end = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        return start, end
    return day, day + timedelta(days=1)


def split_interval(end, seconds, tz=None):
    """Partition an elapsed interval at local 06:00 boundaries, including DST."""
    cursor = end - seconds
    while cursor < end - 1e-9:
        day = statistics_day(cursor, tz)
        boundary = datetime.combine(day + timedelta(days=1), time(6), tzinfo=tz).timestamp()
        stop = min(end, boundary)
        if stop <= cursor:
            raise ValueError('Non-increasing local day boundary')
        yield day.isoformat(), round((stop - cursor) * 1_000_000)
        cursor = stop


class HistoryStore:
    def __init__(self, path, timers=(), now=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=5)
        self.path.chmod(0o600)
        self.last_error = None
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS timers (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, deleted INTEGER NOT NULL,
                total_us INTEGER NOT NULL, baseline_us INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS daily (
                day TEXT NOT NULL, timer_id TEXT NOT NULL, duration_us INTEGER NOT NULL,
                PRIMARY KEY(day,timer_id));
        ''')
        self.db.execute('INSERT OR IGNORE INTO metadata VALUES (?,?)',
                        ('started_at',str(clock.time() if now is None else now)))
        self.db.commit()
        self.catalog = {row[0]: dict(name=row[1], deleted=bool(row[2]), total=row[3], baseline=row[4])
                        for row in self.db.execute('SELECT * FROM timers')}
        self.pending = {}
        self.dirty = False
        self.sync_timers(timers)
        self.flush()

    def sync_timers(self, timers):
        active = {timer['id'] for timer in timers}
        for ident, item in self.catalog.items():
            deleted = ident not in active
            if item['deleted'] != deleted:
                item['deleted'] = deleted
                self.dirty = True
        for timer in timers:
            ident, name = timer['id'], timer.get('name','')
            if ident not in self.catalog:
                # Existing undated display totals are retained, never backfilled.
                self.catalog[ident] = dict(name=name, deleted=False,
                    total=max(0,int(timer.get('elapsed_seconds',0))) * 1_000_000, baseline=0)
                self.dirty = True
            elif self.catalog[ident]['name'] != name:
                self.catalog[ident]['name'] = name
                self.dirty = True

    def record(self, credits, wall_end, tz=None):
        for ident, seconds in credits.items():
            if ident not in self.catalog or seconds <= 0:
                continue
            for day, micros in split_interval(wall_end, seconds, tz):
                key = (day,ident)
                self.pending[key] = self.pending.get(key,0) + micros
                self.catalog[ident]['total'] += micros
                self.dirty = True

    def display_seconds(self, ident):
        item = self.catalog[ident]
        return max(0,(item['total'] - item['baseline']) // 1_000_000)

    def reset_display(self, ids):
        for ident in ids:
            if ident in self.catalog:
                self.catalog[ident]['baseline'] = self.catalog[ident]['total']
                self.dirty = True
        self.try_flush()

    def try_flush(self):
        try:
            self.flush()
            self.last_error = None
            return True
        except (sqlite3.Error, OSError) as error:
            self.last_error = type(error).__name__
            return False

    def flush(self):
        if not self.dirty:
            return
        # One transaction keeps history and display baselines consistent on restart.
        with self.db:
            for ident,item in self.catalog.items():
                self.db.execute('INSERT INTO timers VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET '
                    'name=excluded.name,deleted=excluded.deleted,total_us=excluded.total_us,baseline_us=excluded.baseline_us',
                    (ident,item['name'],int(item['deleted']),item['total'],item['baseline']))
            for (day,ident),micros in self.pending.items():
                self.db.execute('INSERT INTO daily VALUES (?,?,?) ON CONFLICT(day,timer_id) DO UPDATE SET '
                    'duration_us=duration_us+excluded.duration_us',(day,ident,micros))
        self.pending.clear()
        self.dirty = False

    def distribution(self, day, period):
        start,end = period_bounds(day,period)
        totals = dict(self.db.execute('SELECT timer_id,SUM(duration_us) FROM daily '
            'WHERE day>=? AND day<? GROUP BY timer_id',(start.isoformat(),end.isoformat())))
        for (stamp,ident),micros in self.pending.items():
            if start.isoformat() <= stamp < end.isoformat():
                totals[ident] = totals.get(ident,0) + micros
        rows = [dict(id=ident,name=item['name'],deleted=item['deleted'],seconds=totals.get(ident,0)//1_000_000)
                for ident,item in self.catalog.items() if not item['deleted'] or totals.get(ident,0)]
        total = sum(row['seconds'] for row in rows)
        for row in rows:
            row['share'] = row['seconds']/total if total else 0
        return rows,total

    def close(self):
        self.flush()
        self.db.close()


_store = None


def get_history_store():
    global _store
    from core.config_manager import USER_DATA_DIR, config_mgr
    if _store is None:
        _store = HistoryStore(Path(USER_DATA_DIR)/'timer-history.sqlite3', config_mgr.config.get('timers',[]))
    return _store
