"""Real screenshots from the KMyBanners-testdata repo (private): the whole list and bad captures.

The tests are skipped when the repo isn't there ($KMYBANNERS_TESTDATA or ~/repos/KMyBanners-testdata).
"""
import os
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from ingress_banners import grid
from ingress_banners.stitch import StitchError, join, stitch

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
    # Every row has 6 medals: also the dark ones (Aquis Mattiacis, rows 16-17) and the last row under the fade
    assert [grid.row_medals(im, r) for r in rows] == [6] * 418


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


def without_first_rows(im: Image.Image, n: int) -> Image.Image:
    """The list as it was before its newest n medal rows came in: the header, then from row n on."""
    rows = grid.find_rows(im)
    head = im.crop((0, 0, im.width, (rows[0][0] + grid.header_end(im)) // 2))
    rest = im.crop((0, (rows[n - 1][1] + rows[n][0]) // 2, im.width, im.height))
    out = Image.new('RGB', (im.width, head.height + rest.height))
    out.paste(head, (0, 0))
    out.paste(rest, (0, head.height))
    return out


@needs_data
def test_an_update_needs_only_the_new_medals():
    """3 new rows on top: screenshots down to medals that were there before (the first 10 of the full capture,
    the last one with faded rows at its bottom) joined onto the capture before give the whole list."""
    full = stitch(shots('full'))
    before = without_first_rows(full, 3)
    assert len(grid.find_rows(before)) == 415
    joined = join(stitch(shots('full')[:10]), before)
    rows, want = grid.find_rows(joined), grid.find_rows(full)
    assert len(rows) == 418
    for r, w in zip(rows, want):
        assert np.abs(grid.row_fingerprints(joined, r) - grid.row_fingerprints(full, w)).mean() < 0.03


@needs_data
def test_a_whole_new_list_is_used_alone():
    full = stitch(shots('full'))
    assert join(full, without_first_rows(full, 3)) is full


@needs_data
def test_an_update_that_does_not_reach_the_old_medals_is_refused():
    full = stitch(shots('full'))
    with pytest.raises(StitchError, match='do not reach the medals already on your page'):
        join(stitch(shots('full')[:3]), without_first_rows(full, 60))


@needs_data
def test_the_build_keeps_the_screenshots(tmp_path):
    """The inbox goes to captures/ (not deleted), the new medals onto capture/medals.jpg."""
    from ingress_banners.site import take_inbox
    import shutil
    (tmp_path / 'capture').mkdir()
    without_first_rows(stitch(shots('full')), 3).save(tmp_path / 'capture' / 'medals.jpg', quality=92)
    batch = tmp_path / 'inbox' / '2026-11-20T150000Z'
    batch.mkdir(parents=True)
    for f in sorted((DATA / 'full').glob('*.jpg'))[:10]:
        shutil.copy(f, batch)
    take_inbox(tmp_path)
    assert not any((tmp_path / 'inbox').iterdir())
    assert len(list((tmp_path / 'captures' / '2026-11-20T150000Z').glob('*.jpg'))) == 10
    assert len(grid.find_rows(grid.normalize(Image.open(tmp_path / 'capture' / 'medals.jpg')))) == 418
