"""Copy user-supplied reference files into the job root's content-addressed input store.

Ingest is the only route by which a local file enters a job. Each file becomes an immutable
reference ID; videos are reduced to scene-change frames that act as image references.
"""
import json
from pathlib import Path
import re
import shutil
import subprocess
import uuid

from . import pipeline as p

KINDS = {
    'image': ('.png', '.jpg', '.jpeg', '.webp', '.tif', '.tiff', '.bmp', '.gif', '.heic', '.heif', '.exr', '.hdr'),
    'video': ('.mp4', '.mov', '.m4v', '.webm', '.mkv', '.avi'),
    'model': ('.glb', '.gltf', '.obj', '.fbx', '.usd', '.usda', '.usdc', '.usdz', '.blend', '.stl', '.ply'),
    'data': ('.csv', '.tsv', '.json'),
    'vector': ('.svg',),
    'font': ('.ttf', '.otf'),
    'text': ('.txt', '.md'),
}
ROLES = {
    'image': ('subject', 'style', 'composition', 'palette', 'storyboard'),
    'video': ('subject', 'style', 'composition', 'palette', 'storyboard', 'motion'),
    'model': ('asset',),
    'data': ('data',),
    'vector': ('logo', 'asset'),
    'font': ('font',),
    'text': ('shotlist', 'notes'),
}
LIMITS = {'image': 80_000_000, 'video': 4_000_000_000, 'model': 800_000_000, 'data': 50_000_000,
          'vector': 20_000_000, 'font': 30_000_000, 'text': 500_000}
NATIVE_IMAGES = ('.png', '.jpg', '.jpeg', '.webp', '.tif', '.tiff', '.bmp', '.exr', '.hdr')
REF = re.compile(r'ref-[0-9a-f]{16}')
DEFAULT_MAX_FRAMES = 20


def kind_of(path):
    ext = path.suffix.lower()
    for kind, exts in KINDS.items():
        if ext in exts:
            return kind
    allowed = ', '.join(e for exts in KINDS.values() for e in exts)
    raise ValueError(f'Unsupported reference type {ext or "(none)"}; supported: {allowed}')


def store(root):
    return root / 'inputs'


def ref_dir(root, ref_id):
    if not isinstance(ref_id, str) or not REF.fullmatch(ref_id):
        raise ValueError(f'Invalid reference ID {ref_id!r}; use an ID returned by ingest')
    path = store(root) / ref_id
    if path.is_symlink() or not (path / 'input.json').is_file():
        raise ValueError(f'Unknown reference ID {ref_id} in this job root; ingest the file first')
    return path


def ffmpeg(bins, *args, capture=False, timeout=300):
    r = subprocess.run([bins['ffmpeg'], '-nostdin', '-hide_banner', '-v', 'info' if capture else 'error', *map(str, args)],
                       capture_output=True, text=True, timeout=timeout, env=p.render_env())
    if r.returncode:
        raise ValueError('FFmpeg could not read the reference: ' + r.stderr[-400:].strip())
    return r.stderr


def probe_media(bins, path):
    r = subprocess.run([bins['ffprobe'], '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                        'stream=width,height,avg_frame_rate,nb_frames:format=duration', '-of', 'json', str(path)],
                       capture_output=True, text=True, timeout=60, env=p.render_env())
    if r.returncode:
        raise ValueError('Not a readable video: ' + r.stderr[-300:].strip())
    data = json.loads(r.stdout)
    if not data.get('streams'):
        raise ValueError('Video has no picture stream')
    s = data['streams'][0]
    num, _, den = s.get('avg_frame_rate', '0/1').partition('/')
    fps = float(num) / float(den or 1) if float(den or 1) else 0.0
    return {'width': s.get('width'), 'height': s.get('height'), 'fps': round(fps, 3),
            'duration_seconds': round(float(data.get('format', {}).get('duration') or 0), 3)}


def video_frames(bins, source, target, cap):
    """Pick scene-change frames, topped up with evenly spaced samples, at most `cap`."""
    meta = probe_media(bins, source)
    duration = meta['duration_seconds']
    if duration <= 0:
        raise ValueError('Video duration is unknown or zero')
    log = ffmpeg(bins, '-i', source, '-vf', "select='gt(scene,0.28)',showinfo", '-an', '-f', 'null', '-',
                 capture=True, timeout=900)
    cuts = [float(t) for t in re.findall(r'pts_time:([0-9.]+)', log)]
    times = [min(0.05, duration / 2)] + cuts
    want = min(cap, max(6, min(cap, int(duration // 2) + 1)))
    if len(times) < want:
        times += [duration * (i + .5) / want for i in range(want)]
    times = sorted(times)
    kept = []
    for t in times:
        if all(abs(t - k) >= min(.5, duration / (2 * cap)) for k in kept):
            kept.append(t)
    if len(kept) > cap:
        kept = [kept[round(i * (len(kept) - 1) / (cap - 1))] for i in range(cap)] if cap > 1 else kept[:1]
    frames = []
    for i, t in enumerate(kept, 1):
        name = f'frame-{i:02d}-t{t:07.2f}s.png'
        ffmpeg(bins, '-ss', f'{t:.3f}', '-i', source, '-frames:v', '1', '-update', '1', target / name)
        if not (target / name).is_file():
            continue
        frames.append({'file': name, 'time_seconds': round(t, 3), 'scene_cut': t in cuts})
    if not frames:
        raise ValueError('No frames could be extracted from the video')
    return meta, frames


def check_gltf(path):
    doc = json.loads(path.read_text(encoding='utf-8'))
    for group in ('buffers', 'images'):
        for item in doc.get(group, []):
            uri = item.get('uri')
            if uri and not uri.startswith('data:'):
                raise ValueError('glTF with external files is not supported; export a single .glb instead')


def check_data(path, ext):
    text = path.read_text(encoding='utf-8')
    if ext == '.json':
        json.loads(text)
        return {'format': 'json'}
    import csv
    rows = list(csv.reader(text.splitlines(), delimiter='\t' if ext == '.tsv' else ','))
    if not rows:
        raise ValueError('Data file is empty')
    return {'format': ext[1:], 'columns': rows[0], 'rows': len(rows) - 1}


def ingest(root, raw_path, role=None, max_frames=DEFAULT_MAX_FRAMES):
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        raise ValueError('Reference path must be absolute')
    if not path.is_file():
        raise ValueError(f'Reference is not a readable file: {path}')
    kind = kind_of(path)
    size = path.stat().st_size
    if not size or size > LIMITS[kind]:
        raise ValueError(f'{kind} reference must be 1 byte to {LIMITS[kind] // 1_000_000} MB')
    role = role or ROLES[kind][0]
    if role not in ROLES[kind]:
        raise ValueError(f'Role {role!r} does not apply to a {kind}; choose ' + ', '.join(ROLES[kind]))
    if type(max_frames) is not int or not 1 <= max_frames <= 200:
        raise ValueError('max_frames must be an integer from 1 to 200')
    sha = p.digest(path)
    ref_id = 'ref-' + sha[:16]
    base = store(root)
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    final = base / ref_id
    if (final / 'input.json').is_file():
        info = p.read(final / 'input.json')
        # Same bytes: reuse frames already extracted unless a different frame cap was asked for.
        if kind != 'video' or info.get('max_frames') == max_frames:
            return describe(final, info, role)
        shutil.rmtree(final)
    temp = base / ('.ingest-' + uuid.uuid4().hex)
    temp.mkdir(mode=0o700)
    try:
        ext = path.suffix.lower()
        source = temp / ('source' + ext)
        shutil.copyfile(path, source)
        if p.digest(source) != sha:
            raise ValueError('Reference changed while it was being copied')
        info = {'id': ref_id, 'kind': kind, 'default_role': role, 'name': path.name, 'sha256': sha,
                'bytes': size, 'file': source.name}
        bins = p.executables() if kind in ('image', 'video') else None
        if kind == 'image' and ext not in NATIVE_IMAGES:
            ffmpeg(bins, '-i', source, '-frames:v', '1', '-update', '1', temp / 'image.png')
            info['file'] = 'image.png'
        elif kind == 'video':
            meta, frames = video_frames(bins, source, temp, max_frames)
            info.update(video=meta, frames=frames, max_frames=max_frames)
            source.unlink()  # Keep only the frames; the clip itself never reaches Blender.
            info['file'] = None
        elif ext == '.gltf':
            check_gltf(source)
        elif kind == 'data':
            info['data'] = check_data(source, ext)
        elif kind in ('vector', 'text'):
            source.read_text(encoding='utf-8')
        p.write(temp / 'input.json', info)
        temp.rename(final)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        shutil.rmtree(temp, ignore_errors=True)
        raise ValueError(f'Could not parse {path.name}: {exc}') from exc
    except BaseException:
        shutil.rmtree(temp, ignore_errors=True)
        raise
    return describe(final, info, role)


def image_count(info):
    if info['kind'] == 'video':
        return len(info['frames'])
    return 1 if info['kind'] == 'image' else 0


def describe(path, info, role):
    out = {'id': info['id'], 'kind': info['kind'], 'role': role, 'name': info['name'],
           'image_references': image_count(info), 'directory': str(path)}
    if info['kind'] == 'video':
        out['video'] = info['video']
        out['frames'] = [{'time_seconds': f['time_seconds'], 'scene_cut': f['scene_cut'], 'path': str(path / f['file'])}
                         for f in info['frames']]
    elif info.get('file'):
        out['path'] = str(path / info['file'])
    if 'data' in info:
        out['data'] = info['data']
    return out


def attach(root, job, references, max_references):
    """Copy the brief's references into the job and return the manifest the kit reads."""
    target = job / 'inputs'
    target.mkdir(mode=0o700)
    manifest, images = [], 0
    for ref in references:
        src = ref_dir(root, ref['id'])
        info = p.read(src / 'input.json')
        role = ref.get('role') or info['default_role']
        if role not in ROLES[info['kind']]:
            raise ValueError(f'Role {role!r} does not apply to {ref["id"]} ({info["kind"]})')
        images += image_count(info)
        shutil.copytree(src, target / ref['id'])
        manifest.append({**info, 'role': role, 'note': ref.get('note', '')})
    if images > max_references:
        raise ValueError(f'{images} image references exceed max_references={max_references}; '
                         'drop some or raise max_references in the brief')
    p.write(target / 'manifest.json', manifest)
    return manifest
