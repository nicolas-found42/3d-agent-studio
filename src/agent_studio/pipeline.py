"""Local job contract shared by the CLI, MCP, and the render worker."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

from .formats import DEFAULT_ORIENTATION, MASTER_SIZES, stage_size

HERE = Path(__file__).resolve().parent
TEMPLATES = ('gravity-conveyor', 'orbit-bloom')
DEFAULTS = dict(title='Studio Studies', template='gravity-conveyor', orientation=DEFAULT_ORIENTATION, seconds=6,
                primary='#C9D9F3', accent='#39EAC2', seed=11)
FIELDS = {
    'title': {'type': 'string', 'minLength': 1, 'maxLength': 24, 'description': 'Visible title; printable ASCII.'},
    'template': {'type': 'string', 'enum': list(TEMPLATES), 'default': DEFAULTS['template']},
    'orientation': {'type': 'string', 'enum': list(MASTER_SIZES), 'default': DEFAULT_ORIENTATION},
    'seconds': {'type': 'integer', 'minimum': 2, 'maximum': 8, 'default': 6},
    'primary': {'type': 'string', 'pattern': '^#[0-9A-Fa-f]{6}$', 'default': DEFAULTS['primary']},
    'accent': {'type': 'string', 'pattern': '^#[0-9A-Fa-f]{6}$', 'default': DEFAULTS['accent']},
    'seed': {'type': 'integer', 'minimum': 0, 'maximum': 999999, 'default': 11},
}
JOB = re.compile('[a-f0-9]{32}')
EVIDENCE = ('timeline.jpg', 'angles.jpg', 'sections.jpg', 'seam.jpg', 'reel.mp4',
            'two-cycles.mp4', 'cover.png', 'qc.json')
REVIEW_BOARDS = EVIDENCE[:4]
RUNTIME_OVERRIDES = {name: 'STUDIO_' + name.upper() for name in ('blender', 'ffmpeg', 'ffprobe')}


def output_root(value):
    return Path(value or os.environ.get('STUDIO_OUTPUT_ROOT') or
                Path.home() / '3d-agent-studio-jobs').expanduser().resolve()


def validate_brief(raw):
    if not isinstance(raw, dict):
        raise ValueError('Brief must be an object')
    if set(raw) - set(FIELDS):
        raise ValueError('Unsupported brief fields: ' + ', '.join(sorted(set(raw) - set(FIELDS))))
    spec = {**DEFAULTS, **raw}
    title = spec['title']
    if not isinstance(title, str) or not re.fullmatch(r'[ -~]{1,24}', title) or not title.strip():
        raise ValueError('Title must be 1–24 printable ASCII characters, not blank')
    spec['title'] = title.strip()
    if spec['template'] not in TEMPLATES:
        raise ValueError('Unknown template: choose ' + ' or '.join(TEMPLATES))
    orientation = spec['orientation']
    if not isinstance(orientation, str) or orientation not in MASTER_SIZES:
        raise ValueError('Invalid orientation: choose vertical (9:16) or horizontal (16:9)')
    for name in ('seconds', 'seed'):
        n = spec[name]
        if type(n) is not int or not FIELDS[name]['minimum'] <= n <= FIELDS[name]['maximum']:
            raise ValueError(f'{name} must be an integer in the documented range')
    for name in ('primary', 'accent'):
        value = spec[name]
        if not isinstance(value, str) or not re.fullmatch(r'#[0-9A-Fa-f]{6}', value):
            raise ValueError(f'{name} must be a hex color (#RRGGBB)')
        spec[name] = value.upper()
    return spec


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    temp = path.with_name('.' + path.name + '.' + uuid.uuid4().hex)
    try:
        temp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def executables():
    binaries = {}
    missing = []
    for name, variable in RUNTIME_OVERRIDES.items():
        explicit = os.environ.get(variable)
        if explicit and not Path(explicit).is_absolute():
            raise ValueError(f'{variable} must be an absolute executable path')
        binary = shutil.which(explicit or name)
        if not binary and not explicit and name == 'blender' and sys.platform == 'darwin':
            binary = shutil.which('/Applications/Blender.app/Contents/MacOS/Blender')
        if binary:
            binaries[name] = str(Path(binary).resolve())
        else:
            missing.append(f'{name} ({variable})')
    if missing:
        raise ValueError('Missing local runtime: ' + ', '.join(missing))
    return binaries


def doctor(root):
    bins = executables()

    def probe(name, *flags):
        return subprocess.run([bins[name], *flags], check=True, capture_output=True,
                              text=True, timeout=15, env=render_env()).stdout

    versions = {name: probe(name, '--version' if name == 'blender' else '-version').splitlines()[0]
                for name in bins}
    if not re.search(r'^\s*V\S*\s+libx264\s', probe('ffmpeg', '-hide_banner', '-encoders'), re.M):
        raise ValueError('FFmpeg must include the libx264 encoder')
    sizes = {name: {stage: dict(zip(('width', 'height'), stage_size(name, stage)))
                    for stage in ('preview', 'master')} for name in MASTER_SIZES}
    return {'output_root': str(root), 'runtime': {n: {'path': bins[n], 'version': versions[n]} for n in bins},
            'orientations': sizes,
            'libx264': True, 'brief_schema': {'type': 'object', 'additionalProperties': False, 'properties': FIELDS},
            'defaults': DEFAULTS}


def code_identity():
    return {f: digest(HERE / f) for f in ('pipeline.py', 'worker.py', 'scene.py', 'formats.py')}


def job_path(root, job_id):
    if not isinstance(job_id, str) or not JOB.fullmatch(job_id):
        raise ValueError('Invalid job ID; use the 32-character job ID returned by draft')
    path = root / job_id
    if path.is_symlink() or not path.is_dir():
        raise ValueError('Unknown job ID in this output root')
    return path


def artifacts(stage, manifest):
    if stage.is_symlink():
        raise ValueError('Unexpected symlink in job')
    out = {}
    for name, checksum in manifest.items():
        if name not in EVIDENCE:
            raise ValueError('Invalid artifact manifest')
        path = stage / name
        if not path.is_file() or path.is_symlink() or digest(path) != checksum:
            raise ValueError(f'{stage.name} artifact changed: {name}; start a new draft')
        out[name] = str(path)
    if set(out) != set(EVIDENCE):
        raise ValueError('Incomplete review evidence')
    return out


def checked_preview(job, *, require_current_code=True):
    stage = job / 'preview'
    state_path = stage / 'state.json'
    if not state_path.is_file() or stage.is_symlink():
        raise ValueError('A completed preview is required')
    s = read(state_path)
    if s.get('state') != 'ready':
        raise ValueError('A completed preview is required')
    paths = artifacts(stage, s['sha256'])
    manifest = read(job / 'job.json')
    if digest(job / 'job.json') != s.get('job_sha256'):
        raise ValueError('Preview brief manifest changed; start a new draft')
    blend = job / 'scene.blend'
    if not blend.is_file() or blend.is_symlink() or digest(blend) != s['scene_sha256']:
        raise ValueError('Preview scene changed; start a new draft')
    if require_current_code and manifest.get('code') != code_identity():
        raise ValueError('Plugin render code changed since draft; start a new draft')
    return s, paths


def render_env():
    # Keep subprocesses local and do not inherit provider credentials or Python hooks.
    keys = ('PATH', 'HOME', 'USER', 'LOGNAME', 'TMPDIR', 'TEMP', 'TMP', 'LANG', 'LC_ALL',
            'SYSTEMROOT', 'WINDIR', 'SystemDrive', *RUNTIME_OVERRIDES.values())
    return {k: os.environ[k] for k in keys if k in os.environ}


def launch(job, kind, **extra):
    stage = job / kind
    stage.mkdir(exist_ok=False, mode=0o700)  # An immutable stage; races cannot overwrite or reuse plates.
    initial = {'state': 'queued', 'updated_at': time.time(), **extra}
    write(stage / 'state.json', initial)
    try:
        with (stage / 'run.log').open('ab') as log:
            flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS if os.name == 'nt' else 0
            subprocess.Popen([sys.executable, '-m', 'agent_studio.worker', str(job), kind],
                             stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                             cwd=HERE, env=render_env(), creationflags=flags,
                             start_new_session=os.name != 'nt')
    except OSError as exc:
        write(stage / 'state.json', {**initial, 'state': 'failed', 'error': str(exc)})
        raise
    return {'job_id': job.name, 'stage': kind, 'state': 'queued', 'directory': str(stage)}


def start_draft(root, raw):
    brief = validate_brief(raw)
    binaries = executables()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    job = root / uuid.uuid4().hex
    job.mkdir(mode=0o700)
    write(job / 'job.json', {'format': 1, 'brief': brief, 'code': code_identity(), 'binaries': binaries})
    return launch(job, 'preview')


def finalize(root, job_id, review):
    job = job_path(root, job_id)
    s, _ = checked_preview(job)
    names = REVIEW_BOARDS
    if not isinstance(review, dict) or set(review) != {'hashes', 'notes'}:
        raise ValueError('Review must provide hashes and notes for the current preview')
    hashes, notes = review['hashes'], review['notes']
    expected = {n: s['sha256'][n] for n in names}
    if hashes != expected or not isinstance(notes, str) or not 12 <= len(notes.strip()) <= 1800:
        raise ValueError('Use all four exact current screenshot hashes and 12–1800 characters of review notes')
    try:
        return launch(job, 'master', preview_review={'hashes': hashes, 'notes': notes.strip()})
    except FileExistsError as exc:
        raise ValueError('Master already started for this job; use status, or create a fresh draft') from exc


def stage_info(path):
    status = path / 'state.json'
    if not path.exists():
        return None
    if path.is_symlink():
        raise ValueError('Unexpected symlink in job')
    if not status.exists():
        return {'state': 'unknown', 'directory': str(path)}
    value = read(status)
    info = {'state': value['state'], 'directory': str(path), 'log': str(path / 'run.log')}
    if value['state'] in {'queued', 'running'}:
        files = path / 'frames'
        info['rendered_frames'] = sum(1 for f in files.glob('frame-*.png') if f.is_file() and f.stat().st_size)
        info['step'] = value.get('step', 'launch')
        if time.time() - value['updated_at'] > 1800:
            info.update(state='stalled', error='No stage update in 30 minutes; inspect the log and start a new draft if needed')
    elif value['state'] == 'ready':
        info['artifacts'] = artifacts(path, value['sha256'])
        info['qc'] = read(path / 'qc.json')
        if path.name == 'preview':
            info['review_hashes'] = {n: value['sha256'][n] for n in REVIEW_BOARDS}
    elif value['state'] == 'failed':
        info['error'] = value.get('error', 'Worker failed')
    return info


def status(root, job_id):
    job = job_path(root, job_id)
    info = {'job_id': job_id, 'brief': read(job / 'job.json')['brief'], 'editable_blend': None}
    info.update((kind, stage_info(job / kind)) for kind in ('preview', 'master'))
    if info['preview'] and info['preview']['state'] == 'ready':
        checked_preview(job, require_current_code=False)
        info['editable_blend'] = str(job / 'scene.blend')
    return info


def compare(root, before, after):
    a, b = [job_path(root, j) for j in (before, after)]
    if a == b:
        raise ValueError('Provide two different draft job IDs')
    s1, x = checked_preview(a, require_current_code=False)
    s2, y = checked_preview(b, require_current_code=False)
    ba, bb = [read(p / 'job.json')['brief'] for p in (a, b)]
    if ba['template'] != bb['template'] or ba['seconds'] != bb['seconds']:
        raise ValueError('Matched comparisons require the same template and duration')
    if ba.get('orientation', DEFAULT_ORIENTATION) != bb.get('orientation', DEFAULT_ORIENTATION):
        raise ValueError('Matched comparisons require the same orientation')
    bins = executables()
    target = root / 'comparisons' / uuid.uuid4().hex
    target.mkdir(parents=True, mode=0o700)
    paths = {}
    for name in REVIEW_BOARDS:
        out = target / name
        r = subprocess.run([bins['ffmpeg'], '-nostdin', '-loglevel', 'error', '-i', x[name], '-i', y[name],
                            '-filter_complex', '[0:v][1:v]vstack=inputs=2', '-frames:v', '1', '-update', '1',
                            str(out)], capture_output=True, text=True, timeout=25, env=render_env())
        if r.returncode or not out.is_file() or not out.stat().st_size:
            raise RuntimeError(f'Comparison failed for {name}: {r.stderr[-500:]}')
        paths[name] = str(out)
    write(target / 'comparison.json', {'before': before, 'after': after, 'top': ba, 'bottom': bb,
                                       'source_hashes': [s1['sha256'], s2['sha256']]})
    return {'before_top': before, 'after_bottom': after, 'artifacts': paths, 'directory': str(target)}
