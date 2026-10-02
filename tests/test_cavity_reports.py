"""Cavity measurements must describe the geometry retained by component policy."""
import manifold3d as m3d
import pytest

from litmetica3d.solid import SolidReport, process_components_and_cavities


def hollow_box(size, wall, origin=(0, 0, 0)):
    shell = m3d.Manifold.cube((size,) * 3) - m3d.Manifold.cube(
        (size - 2 * wall,) * 3
    ).translate((wall,) * 3)
    return shell.translate(origin)


@pytest.mark.parametrize("components", ["main", "remove-small"])
@pytest.mark.parametrize("outside_hollow", [False, True])
def test_removed_component_does_not_cancel_reported_cavity_fill(components, outside_hollow):
    outer = hollow_box(10, 1)
    outside = (
        hollow_box(9, 1, (20, 0, 0)) if outside_hollow
        else m3d.Manifold.cube((9,) * 3).translate((20, 0, 0))
    )
    report = SolidReport()
    result = process_components_and_cavities(
        outer + outside, cavities="fill", components=components,
        min_component_volume=800, report=report,
    )
    assert report.removed_components == 1
    assert result.volume() == pytest.approx(1000)
    assert report.volume_before_cavity_fill == pytest.approx(488)
    assert report.volume_after_cavity_fill == pytest.approx(1000)
    assert report.filled_cavity_volume == pytest.approx(512)


@pytest.mark.parametrize("components,threshold,before,after,filled", [
    ("keep", 0, 489, 1000, 511),
    ("main", 0, 488, 1000, 512),
    ("remove-small", 0, 489, 1000, 511),
    ("remove-small", 2, 488, 1000, 512),
])
def test_fill_counts_only_unoccupied_volume_after_component_selection(
    components, threshold, before, after, filled,
):
    source = hollow_box(10, 1) + m3d.Manifold.cube().translate((4, 4, 4))
    report = SolidReport()
    result = process_components_and_cavities(
        source, cavities="fill", components=components,
        min_component_volume=threshold, report=report,
    )
    assert result.volume() == pytest.approx(after)
    assert report.volume_before_cavity_fill == pytest.approx(before)
    assert report.volume_after_cavity_fill == pytest.approx(after)
    assert report.filled_cavity_volume == pytest.approx(filled)


@pytest.mark.parametrize("components", ["main", "remove-small"])
def test_preserved_cavity_volume_is_measured_after_component_selection(components):
    source = hollow_box(10, 1) + m3d.Manifold.cube((9,) * 3).translate((20, 0, 0))
    report = SolidReport()
    result = process_components_and_cavities(
        source, cavities="preserve", components=components,
        min_component_volume=800, report=report,
    )
    assert result.volume() == pytest.approx(488)
    assert report.volume_before_cavity_fill == pytest.approx(488)
    assert report.volume_after_cavity_fill == pytest.approx(488)
    assert report.filled_cavity_volume == 0
