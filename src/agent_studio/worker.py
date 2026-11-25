"""Bounded local renderer, encoder, and media verifier. Run only through pipeline/CLI."""
from fractions import Fraction
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time

from . import pipeline as p
from .formats import stage_size

BG = '0x141920'


def run(argv, *, capture=False, timeout=120):
    print('RUN', list(map(str, argv)), flush=True)
    r = subprocess.run(list(map(str, argv)), stdin=subprocess.DEVNULL, check=False,
                       capture_output=capture, text=capture, timeout=timeout, env=p.render_env())
    if r.returncode:
        suffix = ': ' + r.stderr[-850:].strip() if capture else '; see run.log'
        raise RuntimeError(f'{Path(argv[0]).name} exited {r.returncode}' + suffix)
    return r.stdout if capture else None


def ff(bins, *args, capture=False, timeout=600):
    return run([bins['ffmpeg'], '-nostdin', '-hide_banner', '-v', 'error', '-xerror', *args], capture=capture,
               timeout=timeout)


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


def verify_video(bins, mp4, count, size, fps):
    cmd = [bins['ffprobe'], '-v', 'error', '-show_streams', '-show_frames', '-show_entries',
           'stream=codec_type,codec_name,profile,width,height,pix_fmt,avg_frame_rate,r_frame_rate,duration_ts,time_base,sample_aspect_ratio,color_range,color_space,color_transfer,color_primaries:stream_side_data=rotation:frame=best_effort_timestamp',
           '-of', 'json', mp4]
    data = json.loads(run(cmd, capture=True, timeout=300))
    streams = data['streams']
    if len(streams) != 1 or streams[0]['codec_type'] != 'video':
        raise ValueError('Expected one silent video stream')
    s = streams[0]
    expected = dict(codec_name='h264', profile='High', width=size[0], height=size[1], pix_fmt='yuv420p',
                    avg_frame_rate=f'{fps}/1', sample_aspect_ratio='1:1', color_range='tv', color_space='bt709',
                    color_transfer='bt709', color_primaries='bt709')
    for k, v in expected.items():
        if s.get(k) != v:
            raise ValueError(f'Unexpected video {k}: {s.get(k)!r} != {v!r}')
    step = Fraction(1, fps) / Fraction(s['time_base'])
    timestamps = [int(f['best_effort_timestamp']) for f in data['frames']]
    if step.denominator != 1 or timestamps != [i * int(step) for i in range(count)]:
        raise ValueError('Unexpected frame count or cadence')
    duration = int(s['duration_ts']) * Fraction(s['time_base'])
    if duration != Fraction(count, fps) or not fast_start(mp4) or any(d.get('rotation', 0) for d in s.get('side_data_list', [])):
        raise ValueError('Video timing, orientation or fast-start check failed')
    return {'frames': count, 'duration_seconds': float(duration), 'fps': fps, 'width': size[0], 'height': size[1],
            'codec': 'h264', 'profile': 'High', 'color': 'bt709/tv', 'pixel_format': 'yuv420p', 'fast_start': True,
            'silent': True, 'size_bytes': mp4.stat().st_size}


def frame_paths(stage, count, size):
    files = stage / 'frames'
    expect = [files / f'frame-{f:04d}.png' for f in range(1, count + 1)]
    if set(files.glob('*.png')) != set(expect):
        raise ValueError('Numbered PNG sequence is incomplete or contains unexpected plates')
    for path in expect:
        with path.open('rb') as f:
            header = f.read(24)
        if len(header) != 24 or header[:16] != b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR' or struct.unpack('>II', header[16:24]) != size:
            raise ValueError(f'Not a PNG plate of the required size: {path.name}')
    return expect


THUMB = "scale='if(gte(iw,ih),400,-2)':'if(gte(iw,ih),-2,400)'"
# Boards stay within 280-1568 px per side so vision judges (e.g. Jev) accept them as they are.
FIT = "scale='min(iw,1560)':'min(ih,1560)':force_original_aspect_ratio=decrease,pad='max(iw,280)':'max(ih,280)':(ow-iw)/2:(oh-ih)/2:color=" + BG


def strip(bins, paths, target, height=360):
    """Side-by-side images scaled to one height."""
    flags = [token for path in paths for token in ('-i', path)]
    chain = ''.join(f'[{i}:v]scale=-2:{height},setsar=1[t{i}];' for i in range(len(paths)))
    chain += ''.join(f'[t{i}]' for i in range(len(paths))) + f'hstack=inputs={len(paths)},{FIT}' if len(paths) > 1 else \
        f'[0:v]scale=-2:{height},setsar=1,{FIT}'
    ff(bins, *flags, '-filter_complex_threads', '1', '-filter_complex', chain, '-frames:v', '1', '-update', '1', target)


def reference_board(bins, pairs, target, rows=8):
    """Each reference (left) beside the render frame that looks most like it (right), two pairs per row."""
    limit = rows * 2
    if len(pairs) > limit:
        pairs = [pairs[round(i * (len(pairs) - 1) / (limit - 1))] for i in range(limit)]
    flags, chain = [], ''
    box = 'scale=300:168:force_original_aspect_ratio=decrease,pad=300:168:(ow-iw)/2:(oh-ih)/2:color=' + BG + ',setsar=1'
    for i, pair in enumerate(pairs):
        flags += ['-i', pair['reference_path'], '-i', pair['frame_path']]
        chain += f'[{2 * i}:v]{box}[r{i}];[{2 * i + 1}:v]{box}[f{i}];[r{i}][f{i}]hstack=inputs=2,pad=iw+24:ih+12:12:6:color={BG}[p{i}];'
    cols = 1 if len(pairs) == 1 else 2
    if len(pairs) == 1:
        chain += f'[p0]{FIT}'
    else:
        layout = '|'.join(f'{(i % cols) * 624}_{(i // cols) * 180}' for i in range(len(pairs)))
        chain += ''.join(f'[p{i}]' for i in range(len(pairs))) + f'xstack=inputs={len(pairs)}:layout={layout}:fill={BG},{FIT}'
    ff(bins, *flags, '-filter_complex_threads', '1', '-filter_complex', chain, '-frames:v', '1', '-update', '1', target)


def encode(bins, stage, count, fps, size, target):
    part = stage / ('.encoding-' + target.name)
    ff(bins, '-framerate', str(fps), '-start_number', '1', '-i', stage / 'frames' / 'frame-%04d.png',
       '-frames:v', str(count), '-map', '0:v:0', '-an', '-fps_mode', 'cfr',
       '-vf', 'scale=in_range=pc:out_range=tv:out_color_matrix=bt709,format=yuv420p,setsar=1,setparams=colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=tv',
       '-c:v', 'libx264', '-profile:v', 'high', '-preset', 'medium', '-crf', '17', '-g', str(fps * 2),
       '-movflags', '+faststart', part, timeout=3600)
    info = verify_video(bins, part, count, size, fps)
    part.replace(target)
    return info


def export(bins, stage, brief, kind):
    fps = brief['fps']
    count = fps * brief['seconds']
    size = stage_size(brief['orientation'], kind)
    frame_paths(stage, count + (1 if brief['loop'] else 0), size)
    clip = stage / 'reel.mp4'
    info = encode(bins, stage, count, fps, size, clip)
    single = hashes(bins, clip)
    if len(single) != count:
        raise ValueError('Clip did not fully decode')
    warnings = []
    if len(set(single)) < len(single) * .5:
        warnings.append(f'Only {len(set(single))} of {count} decoded frames are distinct; motion may be missing or held')
    qc = {'passed': True, 'stage': kind, 'orientation': brief['orientation'], 'video': info}
    if brief['loop']:
        repeat = stage / 'two-cycles.mp4'
        ff(bins, '-stream_loop', '1', '-i', clip, '-c:v', 'copy', '-an', '-movflags', '+faststart', repeat)
        qc['two_cycles'] = verify_video(bins, repeat, 2 * count, size, fps)
        if hashes(bins, repeat) != single * 2:
            raise ValueError('Two-cycle file pixels differ from two copies of the sequence')
        ff(bins, '-i', repeat, '-vf', f'select=between(n\\,{count - 2}\\,{count + 1}),{THUMB},tile=4x1:padding=8:margin=8:color={BG},{FIT}',
           '-frames:v', '1', '-update', '1', stage / 'seam.jpg')
        qc['seam_frames'] = [count - 1, count, 1, 2]
    ids = [0, count // 5, 2 * count // 5, 3 * count // 5, 4 * count // 5, count - 1]
    selected = '+'.join(f'eq(n\\,{n})' for n in ids)
    ff(bins, '-i', clip, '-vf', f'select={selected},{THUMB},tile=3x2:padding=8:margin=8:color={BG},{FIT}',
       '-frames:v', '1', '-update', '1', stage / 'timeline.jpg')
    cover_idx = count // 3
    ff(bins, '-i', clip, '-vf', f'select=eq(n\\,{cover_idx})', '-frames:v', '1', '-update', '1', stage / 'cover.png')
    proofs = sorted((stage / 'proofs').glob('angle-*.png'))
    if len(proofs) != 3:
        raise ValueError('Missing angle proofs')
    strip(bins, proofs, stage / 'angles.jpg')
    pairs = json.loads((stage / 'pairs.json').read_text())
    if pairs:
        reference_board(bins, pairs, stage / 'references.jpg')
    stats = json.loads((stage / 'render-stats.json').read_text())
    warnings += frame_warnings(stats['frame_stats'])
    seam = stats.get('loop_seam')
    if seam and seam['typical_sampled_change'] is not None and \
            seam['first_vs_extra_frame'] > max(0.01, 3 * seam['typical_sampled_change']):
        warnings.append('Loop seam: the frame after the last differs from frame 1 more than typical motion; '
                        'the loop will visibly jump')
    if kind == 'master' and 'prores' in brief['extras']:
        ff(bins, '-framerate', str(fps), '-start_number', '1', '-i', stage / 'frames' / 'frame-%04d.png',
           '-frames:v', str(count), '-c:v', 'prores_ks', '-profile:v', '4444', '-pix_fmt', 'yuva444p10le',
           '-an', stage / 'master.mov', timeout=3600)
    qc.update(timeline_frames=[i + 1 for i in ids], cover_frame=cover_idx + 1, proof_frame=1 + (count - 1) // 3,
              angle_order=['wide (same camera, half focal length)', 'three-quarter set view', 'top-down overview with camera path'],
              reference_pairs=[{k: v for k, v in pr.items() if k not in ('reference_path', 'frame_path')} | {
                  'frame': Path(pr['frame_path']).name} for pr in pairs],
              render=stats, loop_seam=seam, warnings=warnings,
              notes='Machine checks verify files, timing and coarse pixel statistics only. They are not a visual review.')
    p.write(stage / 'qc.json', qc)


def frame_warnings(stats):
    out = []
    dark = [s['file'] for s in stats if s['mean_luminance'] < 0.012]
    if dark:
        out.append(f'{len(dark)} sampled frames are nearly black (e.g. {dark[0]})')
    blown = [s['file'] for s in stats if s['clipped_fraction'] > 0.3]
    if blown:
        out.append(f'{len(blown)} sampled frames have over 30% clipped pixels (e.g. {blown[0]})')
    changes = [s['change_from_previous'] for s in stats if 'change_from_previous' in s]
    if changes and max(changes) < 0.0015:
        out.append('Sampled frames barely change; the animation may be missing')
    return out


def probe_outputs(bins, job, stage, brief):
    timing = json.loads((stage / 'timing.json').read_text())
    mp = timing['width'] * timing['height'] / 1e6
    hi = sum(timing['seconds_high']) / len(timing['seconds_high'])
    lo = timing['seconds_low']
    k = max(1e-4, (hi - lo) / ((timing['samples_high'] - timing['samples_low']) * mp))
    overhead = max(0.02, lo - k * mp * timing['samples_low'])
    blend_mb = (job / 'scene.blend').stat().st_size / 1e6
    estimate = {'device': timing['device'], 'engine': timing['engine'],
                'seconds_per_megapixel_sample': round(k, 6), 'overhead_seconds': round(overhead, 3),
                'scene_load_seconds': round(5 + 0.08 * blend_mb + 0.2 * timing['build_seconds'], 1),
                'measured': {k2: timing[k2] for k2 in ('width', 'height', 'samples_high', 'samples_low', 'seconds_high', 'seconds_low', 'build_seconds')}}
    frames = brief['fps'] * brief['seconds'] + (1 if brief['loop'] else 0)
    pw, ph = stage_size(brief['orientation'], 'preview')
    preview_samples = brief['samples'].get('preview', p.DEFAULT_SAMPLES['preview'])
    draft = p.predict(estimate, pw * ph, preview_samples, frames) + 60  # proofs and encoding
    estimate['draft'] = {'samples': preview_samples, 'frames': frames, 'predicted_minutes': round(draft / 60, 1),
                         'budget_minutes': brief['budget_minutes']['draft'],
                         'fits': draft <= brief['budget_minutes']['draft'] * 60}
    mw, mh = stage_size(brief['orientation'], 'master')
    ms = brief['samples'].get('master', p.DEFAULT_SAMPLES['master'])
    master = p.predict(estimate, mw * mh, ms, frames)
    estimate['master'] = {'samples': ms, 'predicted_minutes': round(master / 60, 1),
                          'budget_minutes': brief['budget_minutes']['master'],
                          'fits': master <= brief['budget_minutes']['master'] * 60 * .9}
    p.write(stage / 'estimate.json', estimate)
    raw = json.loads((stage / 'checks-raw.json').read_text())
    scene = raw['scene']
    warnings = frame_warnings(raw['stills'])
    if not scene['lights'] and not scene['emissive_materials'] and not scene['sky_or_hdri']:
        warnings.append('No lights, emissive materials, sky or HDRI: the scene is lit only by the flat world color')
    if scene.get('toon_materials') and scene['engine'] == 'CYCLES':
        warnings.append('kit.toon materials need EEVEE (kit.render(engine="EEVEE")); Cycles renders them as plain diffuse')
    if not scene['animated']:
        warnings.append('Nothing in the scene is keyframed; the video will be a still image')
    if not estimate['draft']['fits']:
        warnings.append('Draft is predicted to exceed its budget; simplify, lower samples.preview or raise budget_minutes.draft')
    p.write(stage / 'checks.json', {**raw, 'warnings': warnings})
    stills = sorted((stage / 'stills').glob('still-*.png'))
    strip(bins, stills, stage / 'probe.jpg')
    pairs = json.loads((stage / 'pairs.json').read_text())
    if pairs:
        reference_board(bins, pairs, stage / 'references.jpg')


def work(job, kind):
    if kind not in ('probe', 'preview', 'master'):
        raise ValueError('Invalid stage')
    stage = job / kind
    root = job.parent
    state_file = stage / 'state.json'
    original = p.read(state_file)
    if original['state'] != 'queued' or (stage / 'frames').exists():
        raise ValueError('Refusing to resume or render over preexisting output')

    def state(value, **extra):
        p.write(state_file, {**original, **extra, 'state': value, 'updated_at': time.time()})

    try:
        manifest_path = job / 'job.json'
        identity = p.digest(manifest_path)
        manifest = p.read(manifest_path)
        if manifest['code'] != p.code_identity():
            raise ValueError('Studio code changed since the job was created; start a new job')
        if p.digest(job / 'scene.py') != manifest['script_sha256']:
            raise ValueError('scene.py changed since the job was created; start a new job')
        brief = p.validate_brief(manifest['brief'])
        bins = manifest['binaries']
        if bins != p.executables():
            raise ValueError('Runtime executable paths changed since the job was created; start a new job')
        b = bins['blender']
        version = run([b, '--version'], capture=True, timeout=30).splitlines()[0]
        if p.blender_version(version) < p.MIN_BLENDER:
            raise ValueError('Blender {}.{} or newer is required'.format(*p.MIN_BLENDER))
        runner = ['--python-exit-code', '1', '--python', p.HERE / 'runner.py', '--']
        budget_key = 'draft' if kind == 'preview' else kind
        budget = brief['budget_minutes'][budget_key] * 60
        if kind == 'probe':
            cmd = [b, '-b', '--factory-startup', '--disable-autoexec', *runner, 'probe', job]
        else:
            probe_state, _ = p.checked_stage(job, 'probe')
            estimate = p.read(job / 'probe' / 'estimate.json')
            if kind == 'preview':
                samples = brief['samples'].get('preview', p.DEFAULT_SAMPLES['preview'])
                if not estimate['draft']['fits']:
                    raise ValueError('Draft predicted to take {predicted_minutes} min, over its {budget_minutes} min budget. '
                                     'Raise budget_minutes.draft, lower samples.preview, shorten the shot or simplify the scene.'
                                     .format(**estimate['draft']))
            else:
                approved, _ = p.checked_stage(job, 'preview')
                if original['preview_review']['hashes'] != {k: approved['sha256'][k] for k in original['preview_review']['hashes']}:
                    raise ValueError('Approved preview no longer matches')
                if approved['blender_version'] != version:
                    raise ValueError('Blender version changed since the draft; start a new job')
                samples = original['plan']['samples']
                budget = original['plan']['budget_minutes'] * 60
            (stage / 'frames').mkdir()
            cmd = [b, '-b', job / 'scene.blend', '--disable-autoexec', *runner, 'render', job, kind, samples]
        state('running', step='waiting for the GPU lock')
        with p.GpuLock(root):
            state('running', step='running scene script and probe renders' if kind == 'probe' else 'rendering frames and proofs')
            try:
                run(cmd, timeout=budget + 60)
            except subprocess.TimeoutExpired as exc:
                raise ValueError(f'{kind} exceeded its {budget / 60:g} min budget; raise budget_minutes or simplify') from exc
            except RuntimeError as exc:
                err = stage / 'script-error.txt'
                if err.is_file():
                    raise ValueError('Scene script failed:\n' + err.read_text()[-2500:]) from exc
                raise
        state('running', step='assembling review evidence')
        if kind == 'probe':
            probe_outputs(bins, job, stage, brief)
        else:
            export(bins, stage, brief, kind)
            if kind == 'master' and 'png' not in brief['extras']:
                shutil.rmtree(stage / 'frames')
        scene_hash = p.digest(job / 'scene.blend')
        if identity != p.digest(manifest_path) or manifest['code'] != p.code_identity():
            raise ValueError('Manifest or studio code changed during the render')
        if kind != 'probe' and scene_hash != p.read(job / 'probe' / 'state.json')['scene_sha256']:
            raise ValueError('Saved scene changed during the render')
        names = p.evidence(kind, brief, p.has_image_refs(job))
        checksums = {name: p.digest(stage / name) for name in names}
        state('ready', sha256=checksums, scene_sha256=scene_hash, job_sha256=identity, blender_version=version)
        print('STAGE_READY', kind, job.name, flush=True)
        if kind == 'probe' and original.get('then') == 'preview':
            p.launch(job, 'preview')
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.TimeoutExpired) as e:
        state('failed', error=str(e))
        raise


if __name__ == '__main__':
    work(Path(sys.argv[1]), sys.argv[2])
