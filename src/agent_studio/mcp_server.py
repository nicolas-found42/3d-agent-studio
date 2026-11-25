"""Local stdio MCP adapter. Job policy lives in pipeline, not in any host."""
import argparse
from pathlib import Path
from typing import Any, Literal

from . import ingest, pipeline


INSTRUCTIONS = (
    'Turn any prompt (with optional reference images, video, models, data, logos, fonts or shot lists) into an '
    'animated Blender scene and a silent video. You write the scene: a Python script defining build(kit) that uses '
    'the studio kit and bpy. There are no presets. Before writing, read the 3d-agent-studio skill and study at least '
    'three studio_examples from different categories; borrow techniques, never copy a composition. '
    'Flow: studio_doctor, studio_ingest each reference file, studio_brief, studio_probe (3 timed stills, fast '
    'iteration), then studio_draft and poll studio_status. Look at every review board with studio_view, judge it '
    'against the prompt and references, revise with a new job (brief.parent) when needed, and compare drafts with '
    'studio_compare. Finalize only with the current board hashes and your real review notes; if you cannot see the '
    'images, ask the user to review and leave the master unrendered. The job root and executables are controlled by '
    'the person starting this server.'
)
Board = Literal['probe.jpg', 'references.jpg', 'timeline.jpg', 'angles.jpg', 'seam.jpg', 'cover.png']


def make_server(root):
    from mcp.server.fastmcp import FastMCP, Image
    from mcp.types import ToolAnnotations

    server = FastMCP('3d-agent-studio', instructions=INSTRUCTIONS)
    read_only = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
    writes_new = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
    fetches = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True)

    @server.tool(annotations=read_only)
    def studio_doctor() -> dict[str, Any]:
        """Check Blender 5.2+, FFprobe and FFmpeg/libx264. Returns the job root, orientations, fps choices, the full
        brief schema, reference kinds and roles, open asset sources, and the example count."""
        return pipeline.doctor(root)

    @server.tool(annotations=read_only)
    def studio_brief(brief: dict[str, Any]) -> dict[str, Any]:
        """Validate and normalize a brief without rendering. Required: prompt. Optional: references (ingest IDs or
        {id, role, note}), assets (open asset IDs), orientation (vertical, horizontal, square, portrait, ultrawide),
        seconds 2-30, loop, fps 24/30/60/120, seed, title + show_title, quality standard|fast, budget_minutes
        {probe, draft, master}, samples {preview, master}, extras [prores, png], parent, max_references."""
        return pipeline.validate_brief(brief)

    @server.tool(annotations=writes_new)
    def studio_ingest(path: str, role: str | None = None, max_frames: int = ingest.DEFAULT_MAX_FRAMES) -> dict[str, Any]:
        """Copy one local file (absolute path) into the job root and return its reference ID. Images take roles
        subject/style/composition/palette/storyboard; a video is reduced to up to max_frames scene-change frames
        (role may also be motion); models (glb/gltf/obj/fbx/usd/blend/stl/ply) are assets; csv/tsv/json are data;
        svg is a logo; ttf/otf are fonts; txt/md are shot lists or notes. Put returned IDs in brief.references."""
        return ingest.ingest(root, path, role, max_frames)

    @server.tool(annotations=read_only)
    def studio_examples(query: str = '', tags: list[str] | None = None, limit: int = 6,
                        include_script: bool = False) -> dict[str, Any]:
        """Search the example scene library by words and tags (category, camera, lighting, style, motion). Returns
        prompts, tags, poster and clip paths, and with include_script the full scene scripts to learn from."""
        return pipeline.examples(query, tags, limit, include_script)

    @server.tool(annotations=fetches)
    def studio_probe(brief: dict[str, Any], script: str) -> dict[str, Any]:
        """Create a job from a brief and scene script (Python defining build(kit)), resolve its assets, run the
        script, save the editable scene, and render three timed stills. Poll studio_status; view probe.jpg (and
        references.jpg). The probe's estimate predicts draft and master time."""
        return pipeline.start_probe(root, brief, script)

    @server.tool(annotations=fetches)
    def studio_draft(brief: dict[str, Any] | None = None, script: str | None = None,
                     job_id: str | None = None) -> dict[str, Any]:
        """Render the full preview sequence. Pass job_id to draft an already probed job, or a brief and script to
        probe and draft a new job in one go. Poll studio_status until preview.state is ready, failed or stalled."""
        return pipeline.start_draft(root, brief, script, job_id)

    @server.tool(annotations=read_only)
    def studio_status(job_id: str) -> dict[str, Any]:
        """Read probe, preview and master state, artifacts, estimates, QC warnings, and the review hashes for a job."""
        return pipeline.status(root, job_id)

    @server.tool(annotations=read_only, structured_output=False)
    def studio_view(job_id: str, stage: Literal['probe', 'preview', 'master'], board: Board):
        """Return one review image as MCP image content plus its local path. Probe: probe.jpg, references.jpg.
        Preview/master: timeline.jpg, angles.jpg, references.jpg (with image references), seam.jpg (loops),
        cover.png."""
        info = pipeline.status(root, job_id)[stage]
        if not info or info['state'] != 'ready':
            raise ValueError(f'{stage} is not ready; check studio_status')
        if board not in info['artifacts']:
            raise ValueError(f'{board} is not part of this {stage}; boards: ' +
                             ', '.join(n for n in info['artifacts'] if n.endswith(('.jpg', '.png'))))
        path = Path(info['artifacts'][board])
        return [str(path), Image(path=path, format='png' if board.endswith('.png') else 'jpeg')]

    @server.tool(annotations=writes_new)
    def studio_compare(before: str, after: str) -> dict[str, Any]:
        """Stack matching boards from two ready drafts (same orientation, duration, fps and loop): before on top."""
        return pipeline.compare(root, before, after)

    @server.tool(annotations=writes_new)
    def studio_finalize(job_id: str, hashes: dict[str, str], notes: str, budget_minutes: int | None = None,
                        quality: Literal['standard', 'fast'] | None = None, samples: int | None = None) -> dict[str, Any]:
        """Queue the full-size master after visual review. Copy preview.review_hashes exactly; notes must describe
        what you saw on each board against the prompt and references. Refuses with a time estimate if the master
        would exceed its budget: raise budget_minutes, lower samples, or pass quality 'fast'."""
        return pipeline.finalize(root, job_id, {'hashes': hashes, 'notes': notes}, budget_minutes, quality, samples)

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
