"""Frame dimensions and rates shared by the job contract, worker and Blender runner."""

DEFAULT_ORIENTATION = 'vertical'
# Master sizes; every dimension is even so H.264 4:2:0 needs no padding.
MASTER_SIZES = {
    'vertical': (1080, 1920),    # 9:16
    'horizontal': (1920, 1080),  # 16:9
    'square': (1080, 1080),      # 1:1
    'portrait': (1080, 1350),    # 4:5
    'ultrawide': (2520, 1080),   # 21:9
}
ASPECT_LABELS = {'vertical': '9:16', 'horizontal': '16:9', 'square': '1:1', 'portrait': '4:5', 'ultrawide': '21:9'}
FPS_CHOICES = (24, 30, 60, 120)
STAGES = ('probe', 'preview', 'master')


def stage_size(orientation: str, stage: str) -> tuple[int, int]:
    width, height = MASTER_SIZES[orientation]
    if stage in ('probe', 'preview'):
        return (width // 3) // 2 * 2, (height // 3) // 2 * 2
    if stage == 'master':
        return width, height
    raise ValueError(f'Unknown render stage: {stage}')
