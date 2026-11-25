"""Resolve open-licensed assets by ID before Blender runs.

Every asset is fetched over HTTPS from a keyless source, checked against the license policy,
cached by ID under the job root, hash-pinned and credited. Scene scripts never touch the network;
they ask the kit for an asset ID that the brief declared.
"""
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile

from . import pipeline as p

USER_AGENT = '3d-agent-studio/0.3 (open asset resolver)'
MAX_BYTES = 1_500_000_000
TIMEOUT = 60
TEXTURE_MAPS = ('color', 'normal_gl', 'roughness', 'displacement', 'ao', 'metalness', 'opacity')
ASSET_ID = re.compile(r'(?P<source>[a-z0-9]+):(?P<name>[^\n\r\t]{1,600})')
SOURCES = {
    'polyhaven': 'Poly Haven HDRIs, PBR textures and models (CC0). ID: polyhaven:<slug>[@1k|2k|4k]',
    'ambientcg': 'ambientCG PBR materials and HDRIs (CC0). ID: ambientcg:<AssetId>[@1K|2K|4K]',
    'fontsource': 'Fontsource fonts (OFL/Apache). ID: fontsource:<font-id>[@weight][:italic]',
    'khronos': 'Khronos glTF Sample Assets, CC0/CC-BY models only. ID: khronos:<ModelName>',
    'wikimedia': 'Wikimedia Commons images, CC0/PD/CC-BY. ID: wikimedia:File:<name>',
    'openverse': 'Openverse images, CC0/PD/CC-BY. ID: openverse:<uuid>',
    'met': 'The Met Open Access public-domain images. ID: met:<objectID>',
    'nasa': 'NASA 3D Resources models and textures. ID: nasa:<path in nasa/NASA-3D-Resources>',
    'blenderkit': 'BlenderKit free CC0 materials and models (.blend). ID: blenderkit:<asset uuid>',
    'url': 'A direct HTTPS file on a CC0 host (' + ', '.join(sorted({'kenney.nl', 'sharetextures.com',
           'cgbookcase.com', '3dtextures.me', 'quaternius.com', 'polyhaven.org', 'ambientcg.com'})) + '). ID: url:<https URL>',
}
CC0_HOSTS = ('kenney.nl', 'sharetextures.com', 'cgbookcase.com', '3dtextures.me', 'quaternius.com',
             'polyhaven.org', 'polyhaven.com', 'ambientcg.com')
ALLOWED_LICENSES = re.compile(r'^(CC0-1\.0|LicenseRef-PublicDomain|LicenseRef-NASA-Media-Guidelines|'
                              r'CC-BY-[1-4]\.0|OFL-1\.1|Apache-2\.0|MIT)$')


class LicenseError(ValueError):
    pass


def spdx(raw):
    """Normalize a source's license label to SPDX, or raise if the policy rejects it."""
    text = (raw or '').strip().lower().replace('_', '-')
    if not text:
        raise LicenseError('License is missing; the studio only uses assets with a known open license')
    if any(t in text for t in ('-nc', ' nc', 'noncommercial', 'non-commercial', '-nd', 'noderiv', '-sa', 'sharealike', 'share-alike', 'gpl')):
        raise LicenseError(f'License {raw!r} is not allowed (no NC, ND, SA or copyleft)')
    if text in ('cc0', 'cc0-1.0', 'cc-zero', 'cc zero', 'cc-0', 'cc0 1.0', 'public domain dedication'):
        return 'CC0-1.0'
    if text in ('pd', 'pdm', 'public domain', 'publicdomain', 'public-domain', 'public domain mark'):
        return 'LicenseRef-PublicDomain'
    m = re.fullmatch(r'(?:cc[- ]?)?by[- ]?([1-4]\.0)?', text.replace('cc by', 'cc-by'))
    if m:
        return f'CC-BY-{m.group(1) or "4.0"}'
    if text in ('ofl', 'ofl-1.1', 'sil open font license 1.1', 'sil open font license'):
        return 'OFL-1.1'
    if text in ('apache-2.0', 'apache 2.0', 'apache license 2.0'):
        return 'Apache-2.0'
    if text == 'mit':
        return 'MIT'
    raise LicenseError(f'License {raw!r} is not on the allowlist (CC0, public domain, CC-BY, OFL, Apache, MIT)')


def http(url, *, max_bytes=MAX_BYTES):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https':
        raise ValueError(f'Only HTTPS downloads are allowed: {url}')
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept': '*/*'})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            final = r.geturl()
            data = r.read(max_bytes + 1)
    except urllib.error.HTTPError as exc:
        raise ValueError(f'Download failed ({exc.code}) for {url}') from exc
    except urllib.error.URLError as exc:
        raise ValueError(f'Download failed for {url}: {exc.reason}') from exc
    if len(data) > max_bytes:
        raise ValueError(f'Asset exceeds {max_bytes // 1_000_000} MB: {url}')
    return data, final


def get_json(url):
    data, _ = http(url, max_bytes=50_000_000)
    return json.loads(data)


def host_ok(url, hosts):
    host = urllib.parse.urlsplit(url).hostname or ''
    return any(host == h or host.endswith('.' + h) for h in hosts)


class Fetch:
    """Accumulates files for one asset in a temp directory."""

    def __init__(self, directory):
        self.dir = directory
        self.files = {}

    def save(self, rel, data):
        path = PurePosixPath(rel)
        if path.is_absolute() or '..' in path.parts or not path.parts:
            raise ValueError(f'Unsafe asset path {rel!r}')
        target = self.dir.joinpath(*path.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        self.files[str(path)] = hashlib.sha256(data).hexdigest()
        return target

    def download(self, rel, url):
        data, _ = http(url)
        return self.save(rel, data)

    def unzip(self, data, keep=lambda name: True, rename=lambda name: name):
        total = 0
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for item in z.infolist():
                if item.is_dir() or not keep(item.filename):
                    continue
                total += item.file_size
                if total > MAX_BYTES:
                    raise ValueError('Archive expands beyond the asset size limit')
                name = rename(item.filename)
                if name:
                    self.save(name, z.read(item))


def texture_name(filename):
    """Map a vendor texture filename to the kit's canonical map names."""
    stem = filename.rsplit('/', 1)[-1].lower()
    for tokens, name in ((('_color', '_diff', 'basecolor', 'albedo', '_col'), 'color'),
                         (('normalgl', 'nor_gl', '_normal'), 'normal_gl'),
                         (('rough',), 'roughness'),
                         (('displacement', '_disp', 'height'), 'displacement'),
                         (('ambientocclusion', '_ao'), 'ao'),
                         (('metal',), 'metalness'),
                         (('opacity', 'alpha'), 'opacity')):
        if any(t in stem for t in tokens):
            if name == 'normal_gl' and ('normaldx' in stem or 'nor_dx' in stem):
                return None
            return name + '.' + stem.rsplit('.', 1)[-1]
    return None


def resolve_polyhaven(name, f):
    slug, _, res = name.partition('@')
    res = (res or '2k').lower()
    info = get_json(f'https://api.polyhaven.com/info/{urllib.parse.quote(slug)}')
    files = get_json(f'https://api.polyhaven.com/files/{urllib.parse.quote(slug)}')
    kind = {0: 'hdri', 1: 'texture', 2: 'model'}[info['type']]
    if kind == 'hdri':
        f.download('environment.hdr', files['hdri'][res]['hdr']['url'])
    elif kind == 'texture':
        mapping = {'Diffuse': 'color', 'nor_gl': 'normal_gl', 'Rough': 'roughness',
                   'Displacement': 'displacement', 'AO': 'ao', 'Metal': 'metalness', 'Opacity': 'opacity'}
        for key, canon in mapping.items():
            entry = files.get(key, {}).get(res)
            if entry:
                fmt = 'jpg' if 'jpg' in entry else 'png'
                f.download(f'{canon}.{fmt}', entry[fmt]['url'])
    else:
        entry = files['gltf'][res]['gltf']
        f.download(f'{slug}.gltf', entry['url'])
        for rel, inc in entry.get('include', {}).items():
            f.download(rel, inc['url'])
    authors = ', '.join(info.get('authors', {}))
    return dict(kind=kind, title=info.get('name', slug), author=authors, license='CC0-1.0',
                source_url=f'https://polyhaven.com/a/{slug}')


def resolve_ambientcg(name, f):
    asset, _, res = name.partition('@')
    res = (res or '2K').upper()
    data = get_json('https://ambientcg.com/api/v2/full_json?' + urllib.parse.urlencode(
        {'id': asset, 'include': 'downloadData'}))
    found = data.get('foundAssets') or []
    if not found:
        raise ValueError(f'ambientCG has no asset {asset!r}')
    item = found[0]
    downloads = item['downloadFolders']['default']['downloadFiletypeCategories']['zip']['downloads']
    wanted = [d for d in downloads if d['attribute'].upper() in (f'{res}-JPG', f'{res}-HDR', f'{res}-PNG', res)]
    if not wanted:
        raise ValueError(f'ambientCG {asset} has no {res} download; available: ' + ', '.join(d['attribute'] for d in downloads))
    archive, _ = http(wanted[0]['fullDownloadPath'])
    if item.get('dataType') == 'HDRI':
        f.unzip(archive, keep=lambda n: n.lower().endswith(('.hdr', '.exr')), rename=lambda n: 'environment.' + n.rsplit('.', 1)[-1].lower())
        kind = 'hdri'
    elif item.get('dataType') in ('Material', 'Decal', 'Atlas', 'Terrain'):
        f.unzip(archive, keep=lambda n: n.lower().endswith(('.jpg', '.png')), rename=texture_name)
        kind = 'texture'
    else:
        f.unzip(archive)
        kind = 'model'
    return dict(kind=kind, title=item.get('displayName', asset), author='ambientCG', license='CC0-1.0',
                source_url=f'https://ambientcg.com/view?id={asset}')


def resolve_fontsource(name, f):
    font, _, rest = name.partition('@')
    weight, _, style = rest.partition(':')
    data = get_json(f'https://api.fontsource.org/v1/fonts/{urllib.parse.quote(font)}')
    weight = weight or ('400' if 400 in data['weights'] else str(data['weights'][0]))
    style = style or 'normal'
    variant = data['variants'][weight][style]
    subset = variant.get(data.get('defSubset', 'latin')) or next(iter(variant.values()))
    url = subset['url'].get('ttf') or subset['url'].get('woff2')
    if not url.endswith('.ttf'):
        raise ValueError(f'Fontsource has no TTF for {name}')
    f.download(f'{font}-{weight}-{style}.ttf', url)
    return dict(kind='font', title=data['family'], author=data.get('family'), license=data.get('license'),
                source_url=f'https://fontsource.org/fonts/{font}')


def resolve_khronos(name, f):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', name):
        raise ValueError('Khronos model names are letters, digits, - and _')
    base = f'https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/main/Models/{name}'
    meta = get_json(base + '/metadata.json')
    legal = meta.get('legal') or []
    licenses = {spdx(item.get('license', '').replace('CC-BY 4.0', 'CC-BY-4.0')) for item in legal}
    if len(licenses) != 1:
        raise LicenseError(f'Khronos {name} has mixed or missing licenses')
    try:
        f.download(f'{name}.glb', base + f'/glTF-Binary/{name}.glb')
    except ValueError:
        # Some samples ship only as multi-file glTF; fetch the folder listed by the GitHub API.
        listing = get_json('https://api.github.com/repos/KhronosGroup/glTF-Sample-Assets/contents/Models/'
                           f'{name}/glTF?ref=main')
        for item in listing:
            if item.get('type') == 'file':
                f.download(item['name'], item['download_url'])
    authors = ', '.join(sorted({item.get('artist') or item.get('owner', '') for item in legal}))
    return dict(kind='model', title=name, author=authors, license=licenses.pop(),
                source_url=f'https://github.com/KhronosGroup/glTF-Sample-Assets/tree/main/Models/{name}')


def strip_html(text):
    return re.sub(r'<[^>]+>', '', text or '').strip()


def resolve_wikimedia(name, f):
    title = name if name.startswith('File:') else 'File:' + name
    data = get_json('https://commons.wikimedia.org/w/api.php?' + urllib.parse.urlencode({
        'action': 'query', 'titles': title, 'prop': 'imageinfo', 'iiprop': 'url|extmetadata',
        'iiurlwidth': 3000, 'format': 'json'}))
    page = next(iter(data['query']['pages'].values()))
    if 'imageinfo' not in page:
        raise ValueError(f'Wikimedia Commons has no file {title!r}')
    info = page['imageinfo'][0]
    meta = info.get('extmetadata', {})
    license = spdx(meta.get('License', {}).get('value') or meta.get('LicenseShortName', {}).get('value'))
    url = info.get('thumburl') or info['url']
    f.download('image.' + url.rsplit('.', 1)[-1].lower()[:4], url)
    return dict(kind='image', title=page['title'], author=strip_html(meta.get('Artist', {}).get('value')),
                license=license, source_url=info.get('descriptionurl'))


def resolve_openverse(name, f):
    data = get_json(f'https://api.openverse.org/v1/images/{urllib.parse.quote(name)}/')
    license = spdx(data.get('license') + (f'-{data["license_version"]}' if data.get('license') == 'by' else ''))
    url = data['url']
    f.download('image.' + (url.rsplit('.', 1)[-1].lower()[:4] if '.' in url[-6:] else 'jpg'), url)
    return dict(kind='image', title=data.get('title') or name, author=data.get('creator') or '',
                license=license, source_url=data.get('foreign_landing_url'))


def resolve_met(name, f):
    data = get_json(f'https://collectionapi.metmuseum.org/public/collection/v1/objects/{int(name)}')
    if not data.get('isPublicDomain') or not data.get('primaryImage'):
        raise LicenseError(f'Met object {name} is not a public-domain image')
    f.download('image.jpg', data['primaryImage'])
    return dict(kind='image', title=data.get('title', name), author=data.get('artistDisplayName') or 'The Met',
                license='CC0-1.0', source_url=data.get('objectURL'))


def resolve_nasa(name, f):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('NASA asset path must be relative to the repository')
    url = 'https://raw.githubusercontent.com/nasa/NASA-3D-Resources/master/' + urllib.parse.quote(name)
    f.download(path.name, url)
    kind = 'model' if path.suffix.lower() in ('.glb', '.gltf', '.obj', '.fbx', '.stl', '.blend', '.3ds') else 'image'
    return dict(kind=kind, title=path.stem, author='NASA', license='LicenseRef-NASA-Media-Guidelines',
                source_url='https://github.com/nasa/NASA-3D-Resources/tree/master/' + urllib.parse.quote(str(path.parent)))


def resolve_blenderkit(name, f):
    if not re.fullmatch(r'[0-9a-f-]{36}', name):
        raise ValueError('BlenderKit IDs are asset UUIDs from its search API')
    item = get_json(f'https://www.blenderkit.com/api/v1/assets/{name}/')
    if item.get('license') != 'cc_zero' or not item.get('isFree', item.get('is_free', True)):
        raise LicenseError('Only free CC0 BlenderKit assets are allowed')
    files = {x.get('fileType'): x.get('downloadUrl') for x in item.get('files', [])}
    url = files.get('resolution_2K') or files.get('blend')
    if not url:
        raise ValueError('BlenderKit asset has no downloadable .blend')
    ticket = get_json(url + '?scene_uuid=' + str(uuid.uuid4()))
    f.download('asset.blend', ticket['filePath'])
    return dict(kind='blend', title=item.get('name', name), author=(item.get('author') or {}).get('fullName', 'BlenderKit'),
                license='CC0-1.0', source_url=f'https://www.blenderkit.com/get-blenderkit/{name}/',
                asset_type=item.get('assetType'))


def resolve_url(name, f):
    if not host_ok(name, CC0_HOSTS):
        raise LicenseError('Direct URLs are only accepted from the CC0 hosts: ' + ', '.join(CC0_HOSTS))
    data, final = http(name)
    if not host_ok(final, CC0_HOSTS):
        raise LicenseError(f'Download redirected off the CC0 hosts to {urllib.parse.urlsplit(final).hostname}')
    filename = PurePosixPath(urllib.parse.urlsplit(final).path).name or 'download'
    if filename.lower().endswith('.zip'):
        f.unzip(data)
    else:
        f.save(filename, data)
    ext = filename.rsplit('.', 1)[-1].lower()
    kind = {'hdr': 'hdri', 'exr': 'hdri', 'blend': 'blend', 'ttf': 'font', 'otf': 'font',
            'jpg': 'image', 'jpeg': 'image', 'png': 'image'}.get(ext, 'model' if ext in ('glb', 'gltf', 'obj', 'fbx') else 'archive')
    return dict(kind=kind, title=filename, author=urllib.parse.urlsplit(final).hostname, license='CC0-1.0', source_url=name)


RESOLVERS = {name: globals()['resolve_' + name] for name in SOURCES}


def parse(asset_id):
    m = ASSET_ID.fullmatch(asset_id) if isinstance(asset_id, str) else None
    if not m or m['source'] not in RESOLVERS:
        raise ValueError(f'Invalid asset ID {asset_id!r}; use <source>:<name> with a source from: ' + ', '.join(SOURCES))
    return m['source'], m['name']


def cache_dir(root, asset_id):
    return root / 'assets-cache' / hashlib.sha256(asset_id.encode()).hexdigest()[:24]


def resolve(root, asset_id):
    """Fetch (or reuse) one asset; return its manifest with the cached directory."""
    source, name = parse(asset_id)
    final = cache_dir(root, asset_id)
    if (final / 'asset.json').is_file():
        info = p.read(final / 'asset.json')
        for rel, digest in info['files'].items():
            if p.digest(final.joinpath(*PurePosixPath(rel).parts)) != digest:
                raise ValueError(f'Cached asset {asset_id} changed on disk; delete {final} to refetch')
        return info, final
    final.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = final.parent / ('.fetch-' + uuid.uuid4().hex)
    temp.mkdir(mode=0o700)
    try:
        f = Fetch(temp)
        meta = RESOLVERS[source](name, f)
        meta['license'] = spdx(meta['license']) if not ALLOWED_LICENSES.match(meta.get('license') or '') else meta['license']
        if not f.files:
            raise ValueError(f'{asset_id} produced no files')
        info = {'id': asset_id, 'source': source, **meta, 'files': f.files}
        p.write(temp / 'asset.json', info)
        temp.rename(final)
    except BaseException:
        shutil.rmtree(temp, ignore_errors=True)
        raise
    return info, final


def credit_line(info):
    by = f' by {info["author"]}' if info.get('author') else ''
    return f'{info["title"]}{by} — {info["license"]} — {info.get("source_url") or info["id"]}'


def attach(root, job, asset_ids):
    """Resolve the brief's assets into the job and write assets.json plus CREDITS.txt."""
    target = job / 'assets'
    target.mkdir(mode=0o700)
    manifest = {}
    for asset_id in asset_ids:
        info, cached = resolve(root, asset_id)
        folder = 'a-' + hashlib.sha256(asset_id.encode()).hexdigest()[:12]
        shutil.copytree(cached, target / folder)
        manifest[asset_id] = {**info, 'folder': folder}
    p.write(target / 'assets.json', manifest)
    lines = ['Credits for open-licensed assets used in this scene.', '']
    lines += [credit_line(info) for info in manifest.values()] or ['No external assets.']
    (job / 'CREDITS.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return manifest
