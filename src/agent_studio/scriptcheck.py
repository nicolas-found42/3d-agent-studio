"""Static pre-run check for agent-written scene scripts.

This catches honest mistakes (file I/O, shelling out, network, saving or rendering from the
script) before Blender starts. It is not a sandbox: Python can always be bent around a static
check, so the studio still runs scripts only as the local user who asked for them.
"""
import ast

MAX_BYTES = 400_000
ALLOWED_IMPORTS = frozenset({
    'bpy', 'bmesh', 'mathutils', 'math', 'random', 'colorsys', 'itertools', 'functools',
    'statistics', 'numpy',
})
BANNED_CALLS = frozenset({
    'open', 'exec', 'eval', 'compile', '__import__', 'input', 'breakpoint', 'globals', 'locals',
    'vars', 'getattr', 'setattr', 'delattr', 'memoryview',
})
# Attribute chains the studio owns: saving, rendering, add-ons, handlers and embedded scripts.
BANNED_PREFIXES = (
    'bpy.ops.wm', 'bpy.ops.render', 'bpy.ops.script', 'bpy.ops.preferences', 'bpy.ops.file',
    'bpy.app.handlers', 'bpy.app.timers', 'bpy.app.driver_namespace', 'bpy.utils', 'bpy.data.texts',
    'bpy.data.libraries.write', 'bpy.context.preferences', 'bpy.ops.image.save',
    'bpy.ops.export_', 'bpy.ops.ptcache.free',
)


def reserved(path):
    return any(path == prefix or path.startswith(prefix + '.') or (prefix.endswith('_') and path.startswith(prefix))
               for prefix in BANNED_PREFIXES)


def dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return '.'.join(reversed(parts))
    return None


def check(source):
    """Return a list of problems; an empty list means the script may run."""
    if not isinstance(source, str) or not source.strip():
        return ['Scene script is empty']
    if len(source.encode()) > MAX_BYTES:
        return [f'Scene script exceeds {MAX_BYTES} bytes']
    try:
        tree = ast.parse(source, filename='scene.py')
    except SyntaxError as exc:
        return [f'Syntax error on line {exc.lineno}: {exc.msg}']
    problems = []
    aliases = {}
    has_build = False

    def say(node, text):
        problems.append(f'line {getattr(node, "lineno", "?")}: {text}')

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for name in node.names:
                if name.name.split('.')[0] not in ALLOWED_IMPORTS:
                    say(node, f'import of {name.name!r} is not allowed')
                if reserved(name.name):
                    say(node, f'{name.name} is reserved for the studio')
                if name.asname:
                    aliases[name.asname] = name.name
        elif isinstance(node, ast.ImportFrom):
            if node.level or (node.module or '').split('.')[0] not in ALLOWED_IMPORTS:
                say(node, f'import from {node.module!r} is not allowed')
            for name in node.names:
                full = f'{node.module}.{name.name}'
                if reserved(full):
                    say(node, f'{full} is reserved for the studio')
                aliases[name.asname or name.name] = full
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in BANNED_CALLS:
            say(node, f'{node.func.id}() is not allowed; use kit helpers for data and references')
        elif isinstance(node, ast.Attribute) and node.attr.startswith('__') and node.attr.endswith('__'):
            say(node, f'dunder attribute access ({node.attr}) is not allowed')
        elif isinstance(node, ast.Name) and node.id.startswith('__') and node.id not in ('__name__',):
            say(node, f'dunder name ({node.id}) is not allowed')
        elif isinstance(node, ast.FunctionDef) and node.name == 'build' and node in tree.body:
            has_build = True
        if isinstance(node, ast.Attribute):
            chain = dotted(node)
            if chain:
                head, _, rest = chain.partition('.')
                full = aliases.get(head, head) + ('.' + rest if rest else '')
                if reserved(full):
                    say(node, f'{full} is reserved for the studio')
    if not has_build:
        problems.append('Script must define a top-level function build(kit)')
    # Report each distinct problem once, in source order.
    return list(dict.fromkeys(problems))
