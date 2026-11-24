"""Frame dimensions shared by the job contract and Blender scene builder."""

DEFAULT_ORIENTATION = 'vertical'
MASTER_SIZES = {'vertical': (1080, 1920), 'horizontal': (1920, 1080)}


def stage_size(orientation: str, stage: str) -> tuple[int, int]:
    width, height = MASTER_SIZES[orientation]
    if stage == 'preview':
        return width // 3, height // 3
    if stage == 'master':
        return width, height
    raise ValueError(f'Unknown render stage: {stage}')
