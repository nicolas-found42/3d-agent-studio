"""Local stdio MCP adapter. Job policy lives in pipeline, not in any host."""
import argparse
from pathlib import Path
from typing import Any, Literal

from . import pipeline


INSTRUCTIONS = (
    'Generate editable, silent vertical (9:16) or horizontal (16:9) Blender loops. Start with studio_doctor, then '
    'validate a brief and queue a draft. Poll studio_status for readiness. Inspect all '
    'four review boards with studio_view or a local viewer, and watch the two-cycle '
    'preview before promoting. For revisions, create a fresh draft and use studio_compare. '
    'Use the current preview hashes and actual review notes to finalize. '
    'If you cannot inspect the evidence, ask the user to review it and leave the master unrendered. '
    'The job root and executables are controlled by the person starting this server.'
)


def make_server(root):
    from mcp.server.fastmcp import FastMCP, Image
    from mcp.types import ToolAnnotations

    server = FastMCP('3d-agent-studio', instructions=INSTRUCTIONS)
    read_only = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
    writes_new = ToolAnnotations(readOnlyHint=False, destructiveHint=False,
                                 idempotentHint=False, openWorldHint=False)

    @server.tool(annotations=read_only)
    def studio_doctor() -> dict[str, Any]:
        """Check Blender, FFprobe and FFmpeg/libx264. Return the job root, available orientations and brief defaults."""
        return pipeline.doctor(root)

    @server.tool(annotations=read_only)
    def studio_brief(brief: dict[str, Any]) -> dict[str, Any]:
        """Validate a brief without rendering. Fields: orientation (vertical or horizontal; default vertical), title (ASCII, 1–24), template (gravity-conveyor or orbit-bloom), seconds (integer 2–8), primary and accent (#RRGGBB), seed (integer 0–999999). All are optional."""
        return pipeline.validate_brief(brief)

    @server.tool(annotations=writes_new)
    def studio_draft(brief: dict[str, Any]) -> dict[str, Any]:
        """Queue an editable Blender scene and preview in the requested orientation. Pass the same brief object as studio_brief. Returns a job ID; poll studio_status."""
        return pipeline.start_draft(root, brief)

    @server.tool(annotations=read_only)
    def studio_status(job_id: str) -> dict[str, Any]:
        """Read preview/master state, local artifact paths, QC and preview review hashes for a job ID."""
        return pipeline.status(root, job_id)

    @server.tool(annotations=read_only, structured_output=False)
    def studio_view(job_id: str, stage: Literal['preview', 'master'],
                    board: Literal['timeline.jpg', 'angles.jpg', 'sections.jpg', 'seam.jpg']):
        """Return one verified review JPEG as MCP image content. If the client cannot display it, open the included local path."""
        info = pipeline.status(root, job_id)[stage]
        if not info or info['state'] != 'ready':
            raise ValueError(f'{stage} is not ready; check studio_status')
        path = Path(info['artifacts'][board])
        return [str(path), Image(path=path, format='jpeg')]

    @server.tool(annotations=writes_new)
    def studio_compare(before: str, after: str) -> dict[str, Any]:
        """Stack four matched boards from two ready drafts with the same template, orientation and duration. Returns local JPEG paths; before is on top."""
        return pipeline.compare(root, before, after)

    @server.tool(annotations=writes_new)
    def studio_finalize(job_id: str, hashes: dict[str, str], notes: str) -> dict[str, Any]:
        """Queue a full-HD master in the approved preview's orientation after visual review. Copy all four exact preview.review_hashes from studio_status. Notes must describe what you reviewed (12–1800 characters)."""
        return pipeline.finalize(root, job_id, {'hashes': hashes, 'notes': notes})

    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path,
                        help='Jobs directory (also STUDIO_OUTPUT_ROOT; defaults to ~/3d-agent-studio-jobs)')
    args = parser.parse_args()
    try:
        server = make_server(pipeline.output_root(args.output_root))
    except ModuleNotFoundError as exc:
        if exc.name != 'mcp':
            raise
        parser.error("Install the MCP extra: uv sync --extra mcp (or pip install '.[mcp]')")
    server.run(transport='stdio')


if __name__ == '__main__':
    main()
