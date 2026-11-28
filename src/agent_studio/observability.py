"""Bounded local evidence for studio operations. State files remain authoritative."""
from contextvars import ContextVar
from datetime import datetime, timezone
from functools import wraps
from contextlib import closing
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import uuid

MAX_EVENTS = 8192
RETENTION_DAYS = 30
BUSY_SECONDS = 0.05
SCHEMA = 1
IDENTIFIER = re.compile(r'[a-f0-9]{32}')
ORIGIN = ContextVar('studio_origin', default='python')
ACTIVE = ContextVar('studio_observation', default=None)
_storage_errors = set()


def _path(root):
    directory = root / '.diagnostics'
    database = directory / 'events.sqlite3'
    if directory.is_symlink() or database.is_symlink():
        raise OSError('Diagnostic store must not be a symlink')
    if directory.exists() and not directory.is_dir():
        raise OSError('Diagnostic store directory is inaccessible')
    return database


def _loss(exc):
    # One notice per exception class per process, on stderr only. Never echo exception
    # text: it may contain paths, URLs, tokens or external command output.
    kind = type(exc).__name__
    if kind not in _storage_errors:
        _storage_errors.add(kind)
        try:
            print(f'STUDIO_DIAGNOSTIC_WRITE_UNAVAILABLE {kind}', file=sys.stderr, flush=True)
        except (OSError, ValueError):
            pass


def _write(root, record):
    try:
        path = _path(root)
        path.parent.mkdir(mode=0o700, exist_ok=True)
        with closing(sqlite3.connect(path, timeout=BUSY_SECONDS)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS events ('
                       'id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL, '
                       'job TEXT, operation TEXT NOT NULL, stage TEXT, body TEXT NOT NULL)')
            db.execute('CREATE INDEX IF NOT EXISTS events_at ON events(at)')
            db.execute('INSERT INTO events(at, job, operation, stage, body) VALUES (?, ?, ?, ?, ?)',
                       (record['at'], record['job_id'], record['operation_id'], record['stage'],
                        json.dumps(record, allow_nan=False, separators=(',', ':'))))
            db.execute('DELETE FROM events WHERE at < ?',
                       (time.time() - RETENTION_DAYS * 86400,))
            db.execute('DELETE FROM events WHERE id <= last_insert_rowid() - ?', (MAX_EVENTS,))
        return True
    except (OSError, sqlite3.Error, ValueError, TypeError) as exc:
        _loss(exc)
        return False


def error_kind(exc):
    if isinstance(exc, subprocess.TimeoutExpired):
        return 'timeout'
    if isinstance(exc, PermissionError):
        return 'permission_denied'
    if isinstance(exc, FileNotFoundError):
        return 'missing_file'
    if isinstance(exc, OSError):
        return 'io_error'
    if isinstance(exc, (ValueError, KeyError)):
        return 'validation_or_data_error'
    if isinstance(exc, KeyboardInterrupt):
        return 'interrupted'
    return 'internal_error'


class Observation:
    def __init__(self, root, name, *, job_id=None, operation_id=None, attempt_id=None, stage=None,
                 origin=None):
        self.root = root
        self.name = name
        self.job_id = job_id
        self.operation_id = operation_id or uuid.uuid4().hex
        self.attempt_id = attempt_id
        self.stage = stage
        self.origin = origin or ORIGIN.get()
        self.started_at = time.time()
        self.started = time.monotonic()
        self.open_recorded = False

    def record(self, event, **details):
        # Details come from enumerated application codes and finite counters at call sites.
        try:
            present = self.root.is_dir()
        except OSError as exc:
            _loss(exc)
            return
        if not present:
            return
        common = {'schema': SCHEMA, 'operation_id': self.operation_id, 'attempt_id': self.attempt_id,
                  'job_id': self.job_id, 'stage': self.stage, 'name': self.name,
                  'origin': self.origin, 'pid': os.getpid()}
        if not self.open_recorded:
            self.open_recorded = _write(self.root, {**common, 'at': self.started_at,
                                                   'event': 'opened', 'elapsed_ms': 0, 'details': {}})
        if event != 'opened':
            _write(self.root, {**common, 'at': time.time(), 'event': event, 'details': details,
                               'elapsed_ms': round((time.monotonic() - self.started) * 1000)})


def tracked(name):
    def decorate(function):
        @wraps(function)
        def observed(root, *args, **kwargs):
            obs = Observation(root, name)
            token = ACTIVE.set(obs)
            try:
                obs.record('opened')
                result = function(root, *args, **kwargs)
                obs.record('returned')
                return result
            except BaseException as exc:
                obs.record('rejected', reason=error_kind(exc))
                raise
            finally:
                ACTIVE.reset(token)
        return observed
    return decorate


def frontend(name):
    def decorate(function):
        @wraps(function)
        def remote(*args, **kwargs):
            token = ORIGIN.set(name)
            try:
                return function(*args, **kwargs)
            finally:
                ORIGIN.reset(token)
        return remote
    return decorate


def mark(event, **details):
    obs = ACTIVE.get()
    if obs is not None:
        obs.record(event, **details)


def attach_job(job):
    obs = ACTIVE.get()
    if obs is not None:
        obs.job_id = job.name


def _timestamp(value):
    if value is None:
        return None
    stamp = datetime.fromisoformat(value)
    if stamp.tzinfo is None:
        raise ValueError('Diagnostic timestamps require an explicit UTC offset')
    return stamp.astimezone(timezone.utc).timestamp()


def history(root, *, since=None, until=None, job_id=None, operation_id=None, after=0, limit=100):
    lo, hi = _timestamp(since), _timestamp(until)
    if lo is not None and hi is not None and lo >= hi:
        raise ValueError('The diagnostic start must precede the end')
    if type(after) is not int or after < 0 or type(limit) is not int or not 1 <= limit <= 500:
        raise ValueError('Use an after cursor >= 0 and a page size from 1 to 500')
    for identifier in (job_id, operation_id):
        if identifier is not None and not IDENTIFIER.fullmatch(identifier):
            raise ValueError('Use a 32-character studio job or operation ID')

    now = time.time()
    cutoff = now - RETENTION_DAYS * 86400
    result = {'schema': SCHEMA, 'output_root': str(root),
              'filter': {'since': since, 'until': until, 'job_id': job_id, 'operation_id': operation_id,
                         'after': after, 'limit': limit}, 'queried_at': now,
              'retention_days': RETENTION_DAYS, 'max_retained_events': MAX_EVENTS,
              'retention_cutoff_at': cutoff,
              'events': [], 'next_after': None}
    try:
        path = _path(root)
        if not path.is_file():
            return {**result, 'source': 'absent', 'coverage': 'unknown'}
        query, args = ['id > ?', 'at >= ?'], [after, max(cutoff, lo) if lo is not None else cutoff]
        for clause, value in (('at < ?', hi), ('job = ?', job_id), ('operation = ?', operation_id)):
            if value is not None:
                query.append(clause)
                args.append(value)
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=BUSY_SECONDS)) as db:
            db.execute('BEGIN')
            first, last, start, end = db.execute(
                'SELECT min(id), max(id), min(at), max(at) FROM events WHERE at >= ?', (cutoff,)).fetchone()
            rows = db.execute('SELECT id, body FROM events WHERE ' + ' AND '.join(query) +
                              ' ORDER BY id LIMIT ?', (*args, limit + 1)).fetchall()
        result.update(source='readable', coverage='retained_best_effort',
                      retained={'first_id': first, 'last_id': last, 'earliest_at': start, 'latest_at': end,
                                'cursor_gap': first is not None and first > after + 1},
                      events=[{'id': identifier, **json.loads(body)} for identifier, body in rows[:limit]],
                      next_after=rows[limit - 1][0] if len(rows) > limit else None)
        return result
    except (OSError, sqlite3.Error, ValueError) as exc:
        return {**result, 'source': 'unavailable', 'coverage': 'unknown', 'error': type(exc).__name__}
