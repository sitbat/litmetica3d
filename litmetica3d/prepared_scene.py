"""Repeatable scene traversal without duplicating every decoded block."""

from __future__ import annotations

from .litematic import Schematic


class PreparedScene:
    """Keep source coordinates available while exporting a translated scene."""

    def __init__(self, schematic: Schematic, selected_names=()):
        selected = set(selected_names) if selected_names else set(schematic.regions)
        missing = selected.difference(schematic.regions)
        if missing:
            raise ValueError("未找到区域：" + ", ".join(sorted(missing)))
        self.regions = tuple(
            (name, region) for name, region in schematic.regions.items()
            if name in selected
        )
        self.block_count = sum(len(region.blocks) for _, region in self.regions)
        self.minimum = tuple(
            min(
                (position[axis] + region.position[axis]
                 for _, region in self.regions for position in region.blocks),
                default=0,
            ) for axis in range(3)
        )

    def __iter__(self):
        for name, region in self.regions:
            offset = tuple(region.position[i] - self.minimum[i] for i in range(3))
            for local, palette_index in region.blocks.items():
                position = tuple(local[i] + offset[i] for i in range(3))
                yield name, position, region.palette[palette_index]

    def source_position(self, position):
        return tuple(position[i] + self.minimum[i] for i in range(3))

    def tile_entities(self):
        result = {}
        if not self.block_count:
            return result
        for _, region in self.regions:
            for tile in region.tile_entities:
                try:
                    position = tuple(
                        int(tile[axis]) + region.position[i] - self.minimum[i]
                        for i, axis in enumerate("xyz")
                    )
                except (KeyError, TypeError, ValueError):
                    continue
                result[position] = tile
        return result
