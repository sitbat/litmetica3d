"""Placement and deterministic clustering of editable Blender lights."""

from __future__ import annotations


def _editable_light_position(
    block_name: str,
    position: tuple[int, int, int],
    occupied: set[tuple[int, int, int]],
) -> list[float]:
    """Place helper lights where closed luminous cubes cannot trap them."""
    base = block_name.split(":", 1)[-1]
    closed_sources = {
        "glowstone", "sea_lantern", "shroomlight", "redstone_lamp",
        "ochre_froglight", "pearlescent_froglight", "verdant_froglight",
        "magma_block", "crying_obsidian", "copper_bulb",
        "exposed_copper_bulb", "weathered_copper_bulb",
        "oxidized_copper_bulb",
    }
    center = [float(value) + 0.5 for value in position]
    if base not in closed_sources and "copper_bulb" not in base:
        return center
    for dx, dy, dz in (
        (0, 1, 0), (0, 0, -1), (0, 0, 1),
        (1, 0, 0), (-1, 0, 0), (0, -1, 0),
    ):
        neighbor = (
            position[0] + dx, position[1] + dy, position[2] + dz
        )
        if neighbor not in occupied:
            return [
                center[0] + dx * 0.56,
                center[1] + dy * 0.56,
                center[2] + dz * 0.56,
            ]
    return center


def _uses_editable_blender_lights(mode: str) -> bool:
    """Material mode emits through Cycles without creating Light objects."""
    return mode in {"exact", "clustered"}


def _emission_enabled(enabled: bool, mode: str) -> bool:
    """The explicit none mode always disables masks and helper lights."""
    return enabled and mode != "none"


def _cluster_editable_lights(sources: list[dict]) -> list[dict]:
    """Merge directly adjacent, equivalent sources for large Cycles scenes."""
    groups: dict[tuple, list[dict]] = {}
    for source in sources:
        key = (
            source["block"],
            round(float(source["level"]), 4),
            tuple(round(float(v), 4) for v in source["color"]),
        )
        groups.setdefault(key, []).append(source)
    result = []
    for members in groups.values():
        by_position = {
            tuple(item["block_position"]): item for item in members
        }
        remaining = set(by_position)
        for seed in sorted(by_position):
            if seed not in remaining:
                continue
            remaining.remove(seed)
            stack = [seed]
            component = []
            while stack:
                current = stack.pop()
                component.append(by_position[current])
                for axis in range(3):
                    for delta in (-1, 1):
                        neighbor = list(current)
                        neighbor[axis] += delta
                        neighbor = tuple(neighbor)
                        if neighbor in remaining:
                            remaining.remove(neighbor)
                            stack.append(neighbor)
            if len(component) == 1:
                result.append(component[0])
                continue
            merged = dict(component[0])
            merged["name"] = (
                f"MC Cluster {merged['block'].split(':', 1)[-1]} "
                f"[{len(component)} blocks]"
            )
            merged["position"] = [
                sum(item["position"][axis] for item in component)
                / len(component)
                for axis in range(3)
            ]
            merged["power"] = sum(item["power"] for item in component)
            merged["radius"] = max(
                merged["radius"], len(component) ** (1 / 3) * 0.2
            )
            merged["block_position"] = component[0]["block_position"]
            merged["block_count"] = len(component)
            result.append(merged)
    return result
