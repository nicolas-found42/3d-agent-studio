"""Regenerate skills/3d-agent-studio/references/kit.md from the kit's signatures and docstrings.

Run: uv run --locked python tools/kit_reference.py   (tests fail if the file is stale)
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / 'src' / 'agent_studio' / 'kit.py'
OUT = ROOT / 'skills' / '3d-agent-studio' / 'references' / 'kit.md'


def render():
    tree = ast.parse(KIT.read_text())
    module_doc = ast.get_docstring(tree)
    lines = ['# Scene kit reference', '', 'Generated from `src/agent_studio/kit.py` by `tools/kit_reference.py`; do not edit by hand.',
             '', module_doc, '', '## Module helpers', '']
    kit = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Kit')
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and not node.name.startswith('_'):
            lines.append(f'- `{node.name}({ast.unparse(node.args)})` — {(ast.get_docstring(node) or "").splitlines()[0] if ast.get_docstring(node) else ""}')
    lines += ['', '## `kit` attributes', '',
              '`kit.prompt`, `kit.brief`, `kit.seed`, `kit.rng` (seeded `random.Random`), `kit.fps`, `kit.seconds`, '
              '`kit.frames` (frame count), `kit.loop`, `kit.orientation`, `kit.width`/`kit.height`/`kit.aspect` (master size), '
              '`kit.scene`, `kit.references` (objects with `id`, `kind`, `role`, `name`, `note`, `paths`, and for videos `times`), '
              '`kit.assets` (declared asset manifests by ID).', '']
    section = None
    source = KIT.read_text().splitlines()
    for node in kit.body:
        if not isinstance(node, ast.FunctionDef) or node.name.startswith('_'):
            continue
        # Section headings come from the "# ---- name" comments in the source.
        for line in reversed(source[:node.lineno - 1]):
            if line.strip().startswith('# ---'):
                name = line.strip('# -').strip()
                if name != section:
                    section = name
                    lines += ['', f'## {name.capitalize()}', '']
                break
        args = ast.unparse(node.args).replace('self, ', '').replace('self', '')
        doc = ast.get_docstring(node) or ''
        lines.append(f'- `kit.{node.name}({args})`' + (f'  \n  {" ".join(doc.split())}' if doc else ''))
    return '\n'.join(lines).rstrip() + '\n'


if __name__ == '__main__':
    OUT.write_text(render())
    print('wrote', OUT)
