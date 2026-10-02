"""GUI output layout: one root and one directory per schematic."""

from __future__ import annotations

from contextlib import suppress
from pathlib import Path


OUTPUT_ROOT_NAME = "L3D_output"


def normalize_output_root(selected: str | Path) -> Path:
    """Treat an existing L3D_output as the root; otherwise append it once."""
    path = Path(selected)
    if path.name.casefold() == OUTPUT_ROOT_NAME.casefold():
        return path
    return path / OUTPUT_ROOT_NAME


def next_model_path(
    root: Path, source: Path, output_format: str, reserved: set[str] | None = None,
) -> Path:
    """Choose a schematic-named folder without overwriting an earlier result."""
    stem = source.stem
    index = 1
    while True:
        folder = root / (stem if index == 1 else f"{stem} ({index})")
        key = folder.name.casefold()
        if (not folder.exists() and not folder.is_symlink()
                and (reserved is None or key not in reserved)):
            if reserved is not None:
                reserved.add(key)
            return folder / f"{stem}.{output_format}"
        index += 1


def publish_model_directory(
    stage: Path, root: Path, source: Path, output_format: str,
    preferred: Path, reserved: set[str] | None = None,
) -> Path:
    """Claim a fresh result directory and publish its already converted assets.

    Names chosen before conversion may have been claimed by another process.
    mkdir is exclusive on every supported platform, whereas renaming a directory
    may replace an existing empty directory on POSIX. Roll back our moved entries
    if publication fails, without removing files created by another process.
    """
    model = preferred
    while True:
        try:
            model.parent.mkdir()
            break
        except FileExistsError:
            model = next_model_path(root, source, output_format, reserved)
    moved = []
    try:
        for asset in stage.iterdir():
            destination = model.parent / asset.name
            asset.rename(destination)
            moved.append(destination)
    except BaseException:
        for asset in reversed(moved):
            with suppress(OSError):
                asset.rename(stage / asset.name)
        with suppress(OSError):
            model.parent.rmdir()
        raise
    return model
