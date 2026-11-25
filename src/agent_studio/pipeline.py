"""Local job contract shared by the CLI, MCP, and the render worker.

A job is a prompt-driven brief plus an agent-written scene script, the ingested references and
resolved assets it uses, and three immutable render stages: probe, preview (draft) and master.
"""
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

from .formats import DEFAULT_ORIENTATION, FPS_CHOICES, MASTER_SIZES, ASPECT_LABELS, stage_size

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE / 'examples'
MIN_BLENDER = (5, 2)
DEFAULT_BUDGET = {'probe': 5, 'draft': 10, 'master': 10}
DEFAULT_SAMPLES = {'probe': 16, 'preview': 16, 'master': 128}
STANDARD_FLOOR, FAST_FLOOR = 64, 16
EXTRAS = ('prores', 'png')
FIELDS = {
    'prompt': {'type': 'string', 'minLength': 1, 'maxLength': 8000,
               'description': 'What the scene and its animation should show. Required.'},
    'references': {'type': 'array', 'maxItems': 200, 'default': [],
                   'items': {'type': ['string', 'object'], 'description': 'Reference ID from ingest, or {id, role, note}'}},
    'assets': {'type': 'array', 'maxItems': 64, 'default': [], 'items': {'type': 'string'},
               'description': 'Open asset IDs such as polyhaven:sandstone_blocks_05 (see doctor.asset_sources)'},
    'orientation': {'type': 'string', 'enum': list(MASTER_SIZES), 'default': DEFAULT_ORIENTATION},
    'seconds': {'type': 'integer', 'minimum': 2, 'maximum': 30, 'default': 6},
    'loop': {'type': 'boolean', 'default': False},
    'fps': {'type': 'integer', 'enum': list(FPS_CHOICES), 'default': 24},
    'seed': {'type': 'integer', 'minimum': 0, 'maximum': 999999, 'default': 11},
    'title': {'type': 'string', 'maxLength': 48, 'default': '', 'description': 'Printable ASCII; drawn only if show_title'},
    'show_title': {'type': 'boolean', 'default': False},
    'quality': {'type': 'string', 'enum': ['standard', 'fast'], 'default': 'standard',
                'description': 'fast lowers master samples (floor 16) to fit the budget; standard refuses instead'},
    'budget_minutes': {'type': 'object', 'default': dict(DEFAULT_BUDGET),
                       'description': 'Wall-clock cap per stage: probe, draft, master (1-1440)'},
    'samples': {'type': 'object', 'default': {},
                'description': 'Optional Cycles samples per stage: preview, master (1-4096)'},
    'extras': {'type': 'array', 'items': {'type': 'string', 'enum': list(EXTRAS)}, 'default': [],
               'description': 'Extra master outputs: prores (ProRes 4444 .mov), png (keep the PNG frames)'},
    'parent': {'type': ['string', 'null'], 'default': None, 'description': 'Job ID this revises'},
    'max_references': {'type': 'integer', 'minimum': 1, 'maximum': 500, 'default': 40},
}
DEFAULTS = {k: v['default'] for k, v in FIELDS.items() if 'default' in v}
JOB = re.compile('[a-f0-9]{32}')
RUNTIME_OVERRIDES = {name: 'STUDIO_' + name.upper() for name in ('blender', 'ffmpeg', 'ffprobe')}
CODE_FILES = ('pipeline.py', 'worker.py', 'runner.py', 'kit.py', 'formats.py', 'scriptcheck.py')


def output_root(value):
    return Path(value or os.environ.get('STUDIO_OUTPUT_ROOT') or
                Path.home() / '3d-agent-studio-jobs').expanduser().resolve()


def _int(spec, name, lo, hi):
    n = spec[name]
    if type(n) is not int or not lo <= n <= hi:
        raise ValueError(f'{name} must be an integer from {lo} to {hi}')


def validate_brief(raw):
    if not isinstance(raw, dict):
        raise ValueError('Brief must be an object')
    unknown = set(raw) - set(FIELDS)
    if unknown:
        raise ValueError('Unsupported brief fields: ' + ', '.join(sorted(unknown)))
    if 'prompt' not in raw:
        raise ValueError('Brief needs a prompt describing the scene and its motion')
    spec = {**json.loads(json.dumps(DEFAULTS)), **raw}
    prompt = spec['prompt']
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 8000:
        raise ValueError('prompt must be 1-8000 characters')
    spec['prompt'] = prompt.strip()
    title = spec['title']
    if not isinstance(title, str) or not re.fullmatch(r'[ -~]{0,48}', title):
        raise ValueError('title must be at most 48 printable ASCII characters')
    spec['title'] = title.strip()
    for name in ('loop', 'show_title'):
        if type(spec[name]) is not bool:
            raise ValueError(f'{name} must be true or false')
    if spec['show_title'] and not spec['title']:
        raise ValueError('show_title needs a title')
    if not isinstance(spec['orientation'], str) or spec['orientation'] not in MASTER_SIZES:
        raise ValueError('Invalid orientation: choose ' + ', '.join(f'{k} ({v})' for k, v in ASPECT_LABELS.items()))
    _int(spec, 'seconds', 2, 30)
    _int(spec, 'seed', 0, 999999)
    _int(spec, 'max_references', 1, 500)
    if type(spec['fps']) is not int or spec['fps'] not in FPS_CHOICES:
        raise ValueError('fps must be one of ' + ', '.join(map(str, FPS_CHOICES)))
    if spec['quality'] not in ('standard', 'fast'):
        raise ValueError('quality must be standard or fast')
    budget = spec['budget_minutes']
    if not isinstance(budget, dict) or set(budget) - set(DEFAULT_BUDGET):
        raise ValueError('budget_minutes accepts probe, draft and master')
    for k, v in budget.items():
        if type(v) is not int or not 1 <= v <= 1440:
            raise ValueError('budget_minutes values must be integers from 1 to 1440')
    spec['budget_minutes'] = {**DEFAULT_BUDGET, **budget}
    samples = spec['samples']
    if not isinstance(samples, dict) or set(samples) - {'preview', 'master'} or \
            any(type(v) is not int or not 1 <= v <= 4096 for v in samples.values()):
        raise ValueError('samples accepts preview and master as integers from 1 to 4096')
    extras = spec['extras']
    if not isinstance(extras, list) or any(e not in EXTRAS for e in extras):
        raise ValueError('extras may contain prores and png')
    spec['extras'] = sorted(set(extras))
    if spec['parent'] is not None and (not isinstance(spec['parent'], str) or not JOB.fullmatch(spec['parent'])):
        raise ValueError('parent must be a 32-character job ID')
    refs = []
    if not isinstance(spec['references'], list):
        raise ValueError('references must be a list')
    for ref in spec['references']:
        ref = {'id': ref} if isinstance(ref, str) else ref
        if not isinstance(ref, dict) or set(ref) - {'id', 'role', 'note'} or not isinstance(ref.get('id'), str):
            raise ValueError('Each reference is an ingest ID or {id, role, note}')
        if not isinstance(ref.get('note', ''), str) or len(ref.get('note', '')) > 1000:
            raise ValueError('Reference notes must be text up to 1000 characters')
        refs.append(ref)
    if len({r['id'] for r in refs}) != len(refs):
        raise ValueError('Each reference may appear once')
    spec['references'] = refs
    from . import assets
    if not isinstance(spec['assets'], list) or len(set(spec['assets'])) != len(spec['assets']):
        raise ValueError('assets must be a list of distinct asset IDs')
    for asset_id in spec['assets']:
        assets.parse(asset_id)
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


def blender_version(line):
    m = re.search(r'Blender (\d+)\.(\d+)', line)
    return (int(m[1]), int(m[2])) if m else (0, 0)


def doctor(root):
    from . import assets, ingest
    bins = executables()

    def probe(name, *flags):
        return subprocess.run([bins[name], *flags], check=True, capture_output=True,
                              text=True, timeout=30, env=render_env()).stdout

    versions = {name: probe(name, '--version' if name == 'blender' else '-version').splitlines()[0]
                for name in bins}
    if blender_version(versions['blender']) < MIN_BLENDER:
        raise ValueError('Blender {}.{} or newer is required; found: {}'.format(*MIN_BLENDER, versions['blender']))
    if not re.search(r'^\s*V\S*\s+libx264\s', probe('ffmpeg', '-hide_banner', '-encoders'), re.M):
        raise ValueError('FFmpeg must include the libx264 encoder')
    sizes = {name: {'aspect': ASPECT_LABELS[name], **{stage: dict(zip(('width', 'height'), stage_size(name, stage)))
                    for stage in ('preview', 'master')}} for name in MASTER_SIZES}
    return {'output_root': str(root), 'runtime': {n: {'path': bins[n], 'version': versions[n]} for n in bins},
            'orientations': sizes, 'fps': list(FPS_CHOICES), 'libx264': True,
            'brief_schema': {'type': 'object', 'required': ['prompt'], 'additionalProperties': False, 'properties': FIELDS},
            'defaults': DEFAULTS, 'samples': DEFAULT_SAMPLES,
            'reference_kinds': {k: {'extensions': list(v), 'roles': list(ingest.ROLES[k])} for k, v in ingest.KINDS.items()},
            'gif_handling': 'Animated GIFs are videos and use the scene-frame cap. Single-frame GIFs are images.',
            'asset_sources': assets.SOURCES, 'examples': len(example_index()),
            'script_contract': 'Python defining build(kit); see the skill and studio_examples.'}


def code_identity():
    return {f: digest(HERE / f) for f in CODE_FILES}


def job_path(root, job_id):
    if not isinstance(job_id, str) or not JOB.fullmatch(job_id):
        raise ValueError('Invalid job ID; use the 32-character job ID returned by probe or draft')
    path = root / job_id
    if path.is_symlink() or not path.is_dir():
        raise ValueError('Unknown job ID in this output root')
    return path


def has_image_refs(job):
    manifest = job / 'inputs' / 'manifest.json'
    return manifest.is_file() and any(r['kind'] in ('image', 'video') for r in read(manifest))


def evidence(kind, brief, image_refs):
    """Files each stage must produce; the review boards are the ones finalize binds to."""
    if kind == 'probe':
        return ['probe.jpg', 'estimate.json', 'checks.json'] + (['references.jpg'] if image_refs else [])
    boards = review_boards(brief, image_refs)
    return boards + ['reel.mp4', 'cover.png', 'qc.json'] + (['two-cycles.mp4'] if brief['loop'] else []) + \
        (['master.mov'] if kind == 'master' and 'prores' in brief['extras'] else [])


def review_boards(brief, image_refs):
    return ['timeline.jpg', 'angles.jpg'] + (['references.jpg'] if image_refs else []) + \
        (['seam.jpg'] if brief['loop'] else [])


def artifacts(stage, manifest, expected):
    if stage.is_symlink():
        raise ValueError('Unexpected symlink in job')
    out = {}
    for name, checksum in manifest.items():
        if name not in expected:
            raise ValueError('Invalid artifact manifest')
        path = stage / name
        if not path.is_file() or path.is_symlink() or digest(path) != checksum:
            raise ValueError(f'{stage.name} artifact changed: {name}; start a new draft')
        out[name] = str(path)
    if set(out) != set(expected):
        raise ValueError('Incomplete review evidence')
    return out


def job_manifest(job):
    return read(job / 'job.json')


def checked_stage(job, kind, *, require_current_code=True):
    stage = job / kind
    state_path = stage / 'state.json'
    if not state_path.is_file() or stage.is_symlink():
        raise ValueError(f'A completed {kind} is required')
    s = read(state_path)
    if s.get('state') != 'ready':
        raise ValueError(f'A completed {kind} is required')
    manifest = job_manifest(job)
    paths = artifacts(stage, s['sha256'], evidence(kind, manifest['brief'], has_image_refs(job)))
    if digest(job / 'job.json') != s.get('job_sha256'):
        raise ValueError('Job manifest changed; start a new draft')
    script = job / 'scene.py'
    if not script.is_file() or script.is_symlink() or digest(script) != manifest['script_sha256']:
        raise ValueError('Scene script changed; start a new draft')
    blend = job / 'scene.blend'
    if not blend.is_file() or blend.is_symlink() or digest(blend) != s['scene_sha256']:
        raise ValueError('Saved scene changed; start a new draft')
    if require_current_code and manifest.get('code') != code_identity():
        raise ValueError('Studio render code changed since this job started; start a new draft')
    return s, paths


def render_env():
    # Keep subprocesses local and do not inherit provider credentials or Python hooks.
    keys = ('PATH', 'HOME', 'USER', 'LOGNAME', 'TMPDIR', 'TEMP', 'TMP', 'LANG', 'LC_ALL',
            'SYSTEMROOT', 'WINDIR', 'SystemDrive', *RUNTIME_OVERRIDES.values())
    return {k: os.environ[k] for k in keys if k in os.environ}


class GpuLock:
    """Serialize Blender renders that share one job root (and so, normally, one GPU)."""

    def __init__(self, root):
        self.path = root / '.render.lock'

    def __enter__(self):
        self.handle = self.path.open('a')
        fcntl.flock(self.handle, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        fcntl.flock(self.handle, fcntl.LOCK_UN)
        self.handle.close()


def launch(job, kind, **extra):
    stage = job / kind
    stage.mkdir(exist_ok=False, mode=0o700)  # An immutable stage; races cannot overwrite or reuse plates.
    initial = {'state': 'queued', 'updated_at': time.time(), **extra}
    write(stage / 'state.json', initial)
    try:
        with (stage / 'run.log').open('ab') as log:
            subprocess.Popen([sys.executable, '-m', 'agent_studio.worker', str(job), kind],
                             stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                             cwd=HERE.parent, env={**render_env(), 'PYTHONPATH': str(HERE.parent)},
                             start_new_session=True)
    except OSError as exc:
        write(stage / 'state.json', {**initial, 'state': 'failed', 'error': str(exc)})
        raise
    return {'job_id': job.name, 'stage': kind, 'state': 'queued', 'directory': str(stage)}


def create_job(root, raw, script):
    from . import assets, ingest, scriptcheck
    brief = validate_brief(raw)
    problems = scriptcheck.check(script)
    if problems:
        raise ValueError('Scene script rejected: ' + '; '.join(problems[:12]))
    if brief['parent']:
        job_path(root, brief['parent'])
    binaries = executables()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    job = root / uuid.uuid4().hex
    job.mkdir(mode=0o700)
    try:
        refs = ingest.attach(root, job, brief['references'], brief['max_references'])
        used = assets.attach(root, job, brief['assets'])
        (job / 'scene.py').write_text(script, encoding='utf-8')
        write(job / 'job.json', {'format': 2, 'brief': brief, 'script_sha256': digest(job / 'scene.py'),
                                 'references': [r['id'] for r in refs], 'assets': sorted(used),
                                 'code': code_identity(), 'binaries': binaries, 'created_at': time.time()})
    except BaseException:
        shutil.rmtree(job, ignore_errors=True)
        raise
    return job


def start_probe(root, raw, script):
    return launch(create_job(root, raw, script), 'probe')


def start_draft(root, raw=None, script=None, job_id=None):
    """Draft = probe (if not yet run) followed by the full preview sequence."""
    if job_id:
        if raw is not None or script is not None:
            raise ValueError('Pass either a job_id of a probed job, or a brief and script for a new job')
        job = job_path(root, job_id)
        checked_stage(job, 'probe')
        try:
            return launch(job, 'preview')
        except FileExistsError as exc:
            raise ValueError('Draft already started for this job; use status, or create a new job') from exc
    if raw is None or script is None:
        raise ValueError('A new draft needs a brief and a scene script')
    return launch(create_job(root, raw, script), 'probe', then='preview')


def predict(estimate, pixels, samples, frames, *, loop=False, prores=False):
    """Seconds for rendering and exports, from the probe's two-point fit."""
    mp = pixels / 1e6
    per = estimate['overhead_seconds'] + estimate['seconds_per_megapixel_sample'] * mp * samples
    # Allow for three additional proof cameras and encode/decode of each requested export.
    encoding = mp * frames * (0.10 + 0.04 * loop + 0.08 * prores)
    measured = estimate.get('preview_throughput')
    master = estimate.get('master_calibration')
    if master and master['pixels'] == pixels:
        low, high = master['low'], master['high']
        slope = max(0, (high['per_frame_seconds'] - low['per_frame_seconds']) / (high['samples'] - low['samples']))
        per_frame = max(0.02, low['per_frame_seconds'] + slope * (samples - low['samples']))
        proof_seconds = 3 * measured['per_frame_seconds']
        return frames * per_frame + proof_seconds + estimate['scene_load_seconds'] + encoding
    if measured and measured['pixels'] == pixels and measured['samples'] == samples:
        return frames * measured['per_frame_seconds'] + 3 * per + estimate['scene_load_seconds'] + encoding
    return (frames + 3) * per + estimate['scene_load_seconds'] + encoding


def master_plan(job, budget_minutes=None, quality=None, samples=None):
    manifest = job_manifest(job)
    brief = manifest['brief']
    estimate = read(job / 'probe' / 'estimate.json')
    w, h = stage_size(brief['orientation'], 'master')
    frames = brief['seconds'] * brief['fps'] + (1 if brief['loop'] else 0)
    budget = 60 * (budget_minutes or brief['budget_minutes']['master'])
    quality = quality or brief['quality']
    target = samples or brief['samples'].get('master', DEFAULT_SAMPLES['master'])
    floor = min(target, FAST_FLOOR) if quality == 'fast' else target

    def estimate_seconds(spp):
        return predict(estimate, w * h, spp, frames, loop=brief['loop'], prores='prores' in brief['extras'])

    chosen = None
    s = target
    while s >= floor:
        if estimate_seconds(s) <= budget * .9:
            chosen = s
            break
        s = max(floor, s // 2) if s > floor else floor - 1
    plan = {'width': w, 'height': h, 'frames': frames, 'budget_minutes': budget / 60, 'quality': quality,
            'samples': chosen, 'requested_samples': target,
            'predicted_minutes': round(estimate_seconds(chosen or target) / 60, 2),
            f'predicted_minutes_at_{STANDARD_FLOOR}_spp': round(estimate_seconds(STANDARD_FLOOR) / 60, 2)}
    return plan


def finalize(root, job_id, review, budget_minutes=None, quality=None, samples=None):
    job = job_path(root, job_id)
    s, _ = checked_stage(job, 'preview')
    brief = job_manifest(job)['brief']
    names = review_boards(brief, has_image_refs(job))
    if not isinstance(review, dict) or set(review) != {'hashes', 'notes'}:
        raise ValueError('Review must provide hashes and notes for the current preview')
    hashes, notes = review['hashes'], review['notes']
    expected = {n: s['sha256'][n] for n in names}
    if hashes != expected or not isinstance(notes, str) or not 12 <= len(notes.strip()) <= 4000:
        raise ValueError(f'Use the {len(names)} exact current board hashes ({", ".join(names)}) '
                         'and 12-4000 characters of review notes')
    if budget_minutes is not None and (type(budget_minutes) is not int or not 1 <= budget_minutes <= 1440):
        raise ValueError('budget_minutes must be an integer from 1 to 1440')
    if quality not in (None, 'standard', 'fast'):
        raise ValueError('quality must be standard or fast')
    if samples is not None and (type(samples) is not int or not 1 <= samples <= 4096):
        raise ValueError('samples must be an integer from 1 to 4096')
    plan = master_plan(job, budget_minutes, quality, samples)
    if plan['samples'] is None:
        raise ValueError(
            'Master is predicted to take about {predicted_minutes} min at {requested_samples} spp. The '
            '{budget_minutes:g} min budget reserves 10% for estimation uncertainty. '
            'Pass a larger budget_minutes, fewer samples, or quality "fast".'.format(**plan))
    try:
        return {**launch(job, 'master', preview_review={'hashes': hashes, 'notes': notes.strip()}, plan=plan),
                'plan': plan}
    except FileExistsError as exc:
        raise ValueError('Master already started for this job; use status, or create a new job') from exc


def stage_info(job, kind):
    path = job / kind
    status = path / 'state.json'
    if not path.exists():
        return None
    if path.is_symlink():
        raise ValueError('Unexpected symlink in job')
    if not status.exists():
        return {'state': 'unknown', 'directory': str(path)}
    value = read(status)
    info = {'state': value['state'], 'directory': str(path), 'log': str(path / 'run.log')}
    for key in ('plan', 'then'):
        if key in value:
            info[key] = value[key]
    if value['state'] in {'queued', 'running'}:
        files = path / 'frames'
        info['rendered_frames'] = sum(1 for f in files.glob('frame-*.png') if f.is_file() and f.stat().st_size) \
            if files.is_dir() else 0
        info['step'] = value.get('step', 'launch')
        if time.time() > value.get('deadline_at', value['updated_at'] + 1800) + 30 and \
                value.get('step') != 'waiting for the GPU lock':
            info.update(state='stalled', error='No stage result after its deadline; inspect the log')
    elif value['state'] == 'ready':
        brief = job_manifest(job)['brief']
        info['artifacts'] = artifacts(path, value['sha256'], evidence(kind, brief, has_image_refs(job)))
        if kind == 'probe':
            info['estimate'] = read(path / 'estimate.json')
            info['checks'] = read(path / 'checks.json')
        else:
            info['qc'] = read(path / 'qc.json')
            if (path / 'frames').is_dir():
                info['frames_directory'] = str(path / 'frames')
        if kind == 'preview':
            info['review_hashes'] = {n: value['sha256'][n] for n in review_boards(brief, has_image_refs(job))}
    elif value['state'] == 'failed':
        info['error'] = value.get('error', 'Worker failed')
    return info


def status(root, job_id):
    job = job_path(root, job_id)
    manifest = job_manifest(job)
    info = {'job_id': job_id, 'brief': manifest['brief'], 'parent': manifest['brief'].get('parent'),
            'script': str(job / 'scene.py'),
            'references': manifest['references'], 'assets': manifest['assets'],
            'credits': str(job / 'CREDITS.txt'), 'editable_blend': None}
    info.update((kind, stage_info(job, kind)) for kind in ('probe', 'preview', 'master'))
    if (job / 'scene.blend').is_file():
        info['editable_blend'] = str(job / 'scene.blend')
    return info


def compare(root, before, after):
    a, b = [job_path(root, j) for j in (before, after)]
    if a == b:
        raise ValueError('Provide two different draft job IDs')
    s1, x = checked_stage(a, 'preview', require_current_code=False)
    s2, y = checked_stage(b, 'preview', require_current_code=False)
    ba, bb = [job_manifest(j)['brief'] for j in (a, b)]
    for key in ('orientation', 'seconds', 'fps', 'loop'):
        if ba[key] != bb[key]:
            raise ValueError(f'Matched comparisons require the same {key}')
    bins = executables()
    target = root / 'comparisons' / uuid.uuid4().hex
    target.mkdir(parents=True, mode=0o700)
    paths = {}
    for name in sorted(set(x) & set(y)):
        if not name.endswith('.jpg'):
            continue
        out = target / name
        r = subprocess.run([bins['ffmpeg'], '-nostdin', '-loglevel', 'error', '-i', x[name], '-i', y[name],
                            '-filter_complex', '[0:v]scale=1560:-2,setsar=1[a];[1:v]scale=1560:-2,setsar=1[b];'
                            '[a][b]vstack=inputs=2,scale=1560:1560:force_original_aspect_ratio=decrease,'
                            'pad=max(iw\\,280):max(ih\\,280):(ow-iw)/2:(oh-ih)/2:0x141920',
                            '-frames:v', '1', '-update', '1', str(out)],
                           capture_output=True, text=True, timeout=60, env=render_env())
        if r.returncode or not out.is_file() or not out.stat().st_size:
            raise RuntimeError(f'Comparison failed for {name}: {r.stderr[-500:]}')
        paths[name] = str(out)
    write(target / 'comparison.json', {'before': before, 'after': after, 'top': ba, 'bottom': bb,
                                       'source_hashes': [s1['sha256'], s2['sha256']]})
    return {'before_top': before, 'after_bottom': after, 'artifacts': paths, 'directory': str(target)}


def example_index():
    path = EXAMPLES / 'index.json'
    return read(path) if path.is_file() else []


def examples(query='', tags=None, limit=8, include_script=False):
    """Rank examples by overlap with the query words and tags; never returns more than 12."""
    if not isinstance(query, str) or len(query) > 2000:
        raise ValueError('query must be text up to 2000 characters')
    tags = [t.lower() for t in (tags or [])]
    if type(limit) is not int or not 1 <= limit <= 12:
        raise ValueError('limit must be an integer from 1 to 12')
    words = set(re.findall(r'[a-z0-9]+', query.lower()))
    scored = []
    for entry in example_index():
        hay = ' '.join([entry['slug'], entry['title'], entry['prompt'], entry['category'],
                        ' '.join(entry['tags'].values() if isinstance(entry['tags'], dict) else entry['tags'])]).lower()
        tokens = set(re.findall(r'[a-z0-9]+', hay))
        tag_values = {str(v).lower() for v in (entry['tags'].values() if isinstance(entry['tags'], dict) else entry['tags'])}
        if tags and not all(t in tag_values or t == entry['category'] for t in tags):
            continue
        score = len(words & tokens) + (2 if entry['category'] in words else 0)
        scored.append((score, entry['slug'], entry))
    scored.sort(key=lambda s: (-s[0], s[1]))
    out = []
    for _, slug, entry in scored[:limit]:
        folder = EXAMPLES / slug
        item = {**entry, 'script_path': str(folder / 'scene.py'),
                'poster': str(folder / 'poster.jpg') if (folder / 'poster.jpg').is_file() else None,
                'clip': str(folder / 'clip.mp4') if (folder / 'clip.mp4').is_file() else None}
        if include_script:
            item['script'] = (folder / 'scene.py').read_text(encoding='utf-8')
        out.append(item)
    categories = sorted({e['category'] for e in example_index()})
    return {'results': out, 'categories': categories, 'total': len(example_index())}
