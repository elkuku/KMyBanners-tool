"""Real screenshots from the KMyBanners-testdata repo (private): the whole list and bad captures.

The tests are skipped when the repo isn't there ($KMYBANNERS_TESTDATA or ~/repos/KMyBanners-testdata).
"""
import os
from pathlib import Path

import pytest
from PIL import Image

from ingress_banners import grid
from ingress_banners.stitch import StitchError, stitch

Image.MAX_IMAGE_PIXELS = None
DATA = Path(os.environ.get('KMYBANNERS_TESTDATA', Path.home() / 'repos/KMyBanners-testdata'))
needs_data = pytest.mark.skipif(not (DATA / 'full').is_dir(), reason='needs the KMyBanners-testdata repo')


def shots(folder: str) -> list[Image.Image]:
    return [Image.open(f) for f in sorted((DATA / folder).glob('*.jpg'))]


@needs_data
def test_the_whole_list():
    """62 screenshots plus 8 at the end of the list (with the loading spinner) give all 418 rows of
    nikp3h's list; only the last row, under the fade at the end, has a medal that didn't load."""
    im = stitch(shots('full'))
    rows = grid.find_rows(im)
    assert len(rows) == 418
    missing = grid.unloaded_rows(im)
    assert len(missing) <= 1 and all(y >= rows[-1][0] for y in missing)


@needs_data
@pytest.mark.parametrize('folder, message', [
    ('bad/gap', 'do not overlap'),
    ('bad/order', 'do not overlap'),
    ('bad/unloaded', 'had not loaded yet'),
])
def test_bad_captures_are_refused(folder, message):
    with pytest.raises(StitchError, match=message):
        stitch(shots(folder))


@needs_data
def test_empty_circles_are_found():
    """The unloaded screenshot has 5 rows of empty circles (the last one at the start of the fade); the
    same place 9 s later none."""
    first, later = [grid.normalize(s) for s in shots('bad/unloaded')]
    assert len(grid.unloaded_rows(first)) == 5
    assert grid.unloaded_rows(later, bottom=2030) == []
