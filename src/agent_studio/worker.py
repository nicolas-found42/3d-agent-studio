"""Bounded local renderer, encoder, and media verifier. Run only through pipeline/CLI."""
from fractions import Fraction
import json
from pathlib import Path
import struct
import subprocess
import sys
import time

from . import pipeline as p
from .formats import stage_size


def run(argv, *, capture=False, timeout=120):
    print('RUN', list(map(str, argv)), flush=True)
    r = subprocess.run(list(map(str, argv)), stdin=subprocess.DEVNULL, check=False,
                       capture_output=capture, text=capture, timeout=timeout, env=p.render_env())
    if r.returncode:
        suffix = ': ' + r.stderr[-850:].strip() if capture else '; see run.log'
        raise RuntimeError(f'{Path(argv[0]).name} exited {r.returncode}' + suffix)
    return r.stdout if capture else None


def ff(bins, *args, capture=False):
    return run([bins['ffmpeg'], '-nostdin', '-hide_banner', '-v', 'error', '-xerror', *args], capture=capture)


def hashes(bins, clip):
    lines = ff(bins, '-i', clip, '-map', '0:v:0', '-threads', '1', '-f', 'framemd5', '-', capture=True).splitlines()
    return [line.rsplit(',', 1)[1].strip() for line in lines if line and not line.startswith('#')]


def fast_start(path):
    total = path.stat().st_size
    found = []
    with path.open('rb') as f:
        pos = 0
        while pos < total:
            f.seek(pos)
            header = f.read(8)
            if len(header) != 8:
                return False
            size, kind = struct.unpack('>I4s', header)
            minimum = 8
            if size == 1:
                buf = f.read(8)
                if len(buf) != 8:
                    return False
                size, minimum = struct.unpack('>Q', buf)[0], 16
            if size == 0:
                size = total - pos
            if size < minimum or pos + size > total:
                return False
            found.append(kind)
            pos += size
    return b'moov' in found and b'mdat' in found and found.index(b'moov') < found.index(b'mdat')


def verify_video(bins, mp4, count, size):
    cmd = [bins['ffprobe'], '-v', 'error', '-show_streams', '-show_frames', '-show_entries',
           'stream=codec_type,codec_name,profile,width,height,pix_fmt,avg_frame_rate,r_frame_rate,duration_ts,time_base,sample_aspect_ratio,color_range,color_space,color_transfer,color_primaries:stream_side_data=rotation:frame=best_effort_timestamp',
           '-of', 'json', mp4]
    data = json.loads(run(cmd, capture=True))
    streams = data['streams']
    if len(streams) != 1 or streams[0]['codec_type'] != 'video':
        raise ValueError('Expected one silent video stream')
    s = streams[0]
    expected = dict(codec_name='h264', profile='High', width=size[0], height=size[1], pix_fmt='yuv420p',
                    avg_frame_rate='30/1', sample_aspect_ratio='1:1', color_range='tv', color_space='bt709',
                    color_transfer='bt709', color_primaries='bt709')
    for k, v in expected.items():
        if s.get(k) != v:
            raise ValueError(f'Unexpected video {k}: {s.get(k)!r} != {v!r}')
    step = Fraction(1, 30) / Fraction(s['time_base'])
    timestamps = [int(f['best_effort_timestamp']) for f in data['frames']]
    if step.denominator != 1 or timestamps != [i * int(step) for i in range(count)]:
        raise ValueError('Unexpected frame count or cadence')
    duration = int(s['duration_ts']) * Fraction(s['time_base'])
    if duration != Fraction(count, 30) or not fast_start(mp4) or any(d.get('rotation', 0) for d in s.get('side_data_list', [])):
        raise ValueError('Video timing, orientation or fast-start check failed')
    return {'frames': count, 'duration_seconds': float(duration), 'fps': 30, 'width': size[0], 'height': size[1], 'codec': 'h264',
            'profile': 'High', 'color': 'bt709/tv', 'pixel_format': 'yuv420p', 'fast_start': True,
            'silent': True, 'size_bytes': mp4.stat().st_size}


def frame_paths(stage, count, size):
    files = stage / 'frames'
    expect = [files / f'frame-{f:04d}.png' for f in range(1, count+1)]
    if set(files.glob('*.png')) != set(expect):
        raise ValueError('Numbered PNG sequence is incomplete or contains unexpected plates')
    for path in expect:
        with path.open('rb') as f:
            header = f.read(24)
        if len(header) != 24 or header[:16] != b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR' or struct.unpack('>II', header[16:24]) != size:
            raise ValueError(f'Not a PNG plate of the required size: {path.name}')
    return expect


def stack(bins, paths, target, width, height):
    flags = [token for path in paths for token in ('-i', path)]
    labels = ''.join(f'[{i}:v]scale={width}:{height},setsar=1[t{i}];' for i in range(len(paths)))
    chain = labels + ''.join(f'[t{i}]' for i in range(len(paths))) + f'hstack=inputs={len(paths)}'
    ff(bins, *flags, '-filter_complex_threads', '1', '-filter_complex', chain,
       '-frames:v', '1', '-update', '1', target)


def export(bins, stage, frames, size, orientation):
    clip = stage / 'reel.mp4'
    part = stage / '.encoding.mp4'
    ff(bins, '-framerate', '30', '-start_number', '1', '-i', stage/'frames'/'frame-%04d.png',
       '-frames:v', str(len(frames)), '-map', '0:v:0', '-an', '-fps_mode', 'cfr',
       '-vf', 'scale=in_range=pc:out_range=tv:out_color_matrix=bt709,format=yuv420p,setsar=1,setparams=colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=tv',
       '-c:v', 'libx264', '-profile:v', 'high', '-preset', 'fast', '-crf', '18', '-g', '60',
       '-movflags', '+faststart', part)
    info = verify_video(bins, part, len(frames), size)
    single = hashes(bins, part)
    if len(single) != len(frames) or len(set(single)) < len(single)*.8:
        raise ValueError('Clip did not fully decode or has too many repeated frames')
    repeat = stage / 'two-cycles.mp4'
    ff(bins, '-stream_loop', '1', '-i', part, '-c:v', 'copy', '-an', '-movflags', '+faststart', repeat)
    second = verify_video(bins, repeat, 2*len(frames), size)
    if hashes(bins, repeat) != single*2:
        raise ValueError('Two-cycle file pixels differ from two copies of the master sequence')
    part.replace(clip)
    count = len(frames)
    ids = [0, count//6, count//3, count//2, count*2//3, count-1]
    thumb = '320:180' if orientation == 'horizontal' else '216:384'
    seam_grid = '2x2' if orientation == 'horizontal' else '4x1'
    # Contact sheet and seam are decoded from the encoded video, rather than the input PNGs.
    selected = '+'.join(f'eq(n\\,{n})' for n in ids)
    ff(bins, '-i', clip, '-vf', f'select={selected},scale={thumb},tile=3x2:padding=8:margin=8:color=0x141920',
       '-frames:v', '1', '-update', '1', stage/'timeline.jpg')
    ff(bins, '-i', repeat, '-vf', f'select=between(n\\,{count-2}\\,{count+1}),scale={thumb},tile={seam_grid}:padding=8:margin=8:color=0x141920',
       '-frames:v', '1', '-update', '1', stage/'seam.jpg')
    cover_idx = count//3
    ff(bins, '-i', clip, '-vf', f'select=eq(n\\,{cover_idx})', '-frames:v', '1', '-update', '1', stage/'cover.png')
    for group, n in [('angle', 3), ('section', 2)]:
        proofs = sorted((stage/'proofs').glob(f'{group}-*.png'))
        if len(proofs) != n:
            raise ValueError(f'Missing {group} proofs')
        stack(bins, proofs, stage/('angles.jpg' if group == 'angle' else 'sections.jpg'), 270,360)
    p.write(stage/'qc.json', {'passed': True, 'orientation': orientation, 'video': info,
                            'two_cycles': second, 'ordered_repeat_hashes': True,
                            'timeline_frames': [i+1 for i in ids], 'seam_frames': [count-1,count,1,2],
                            'seam_layout': seam_grid,
                            'cover_frame': cover_idx+1, 'proof_frame': 1+(count-1)//3,
                            'angle_order': ['front','side','reverse'], 'section_order': ['x=0', 'y=0'],
                            'notes': 'Section proofs are orthographic clip-plane views, not watertight geometry. File verification is not visual review or a native platform test.'})


def work(job, kind):
    if kind not in ('preview','master'):
        raise ValueError('Invalid stage')
    stage = job / kind
    state_file = stage / 'state.json'
    original = p.read(state_file)
    if original['state'] != 'queued' or (stage/'frames').exists() or (stage/'proofs').exists():
        raise ValueError('Refusing to resume or render over preexisting output')
    (stage/'frames').mkdir()
    (stage/'proofs').mkdir()

    def state(value, **extra):
        p.write(state_file, {**original, **extra, 'state': value, 'updated_at': time.time()})

    try:
        manifest_path = job/'job.json'
        identity = p.digest(manifest_path)
        manifest = p.read(manifest_path)
        if manifest['code'] != p.code_identity():
            raise ValueError('Plugin renderer changed since job was queued; start a new draft')
        brief = p.validate_brief(manifest['brief'])
        bins = manifest['binaries']
        if bins != p.executables():
            raise ValueError('Runtime executable paths changed since draft; start a new draft')
        b = bins['blender']
        version = run([b, '--version'], capture=True, timeout=15).splitlines()[0]
        start = [b, '-b', '--factory-startup', '--disable-autoexec']
        script = ['--python-exit-code', '1', '--python', p.HERE/'scene.py', '--']
        scene = job/'scene.blend'
        size = stage_size(brief['orientation'], kind)
        if kind == 'preview':
            state('running', step='building editable scene')
            run([*start,*script,'build',job], timeout=120)
        else:
            approved, _ = p.checked_preview(job)
            if original['preview_review']['hashes'] != {k: approved['sha256'][k] for k in original['preview_review']['hashes']}:
                raise ValueError('Approved preview no longer matches')
            if approved['blender_version'] != version:
                raise ValueError('Blender version changed since preview; start a new draft')
        scene_hash = p.digest(scene)
        state('running', step='rendering frames and section proofs')
        run([*start,scene,*script,'render',stage,kind], timeout=1200)
        state('running', step='encoding and verifying delivered pixels')
        frames = frame_paths(stage, 30*brief['seconds'], size)
        export(bins, stage, frames, size, brief['orientation'])
        if scene_hash != p.digest(scene) or identity != p.digest(manifest_path) or manifest['code'] != p.code_identity():
            raise ValueError('Scene, manifest or worker code changed during render')
        checksums = {name: p.digest(stage/name) for name in p.EVIDENCE}
        state('ready', sha256=checksums, scene_sha256=scene_hash, job_sha256=identity, blender_version=version)
        print('REEL_READY', kind, job.name, flush=True)
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.TimeoutExpired) as e:
        state('failed', error=str(e))
        raise


if __name__ == '__main__':
    work(Path(sys.argv[1]), sys.argv[2])
