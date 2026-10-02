"""Minecraft-style, state-aware visual emission rules.

The vanilla model assets only mark a small number of model elements with
``light_emission``.  Shader packs therefore combine that attribute with block
IDs, block states and texture colour masks.  This module does the same for the
visual Blender workflow.  Print geometry never imports or calls this module.
"""

from __future__ import annotations

import json
import math
from pathlib import Path


_FIXED_LEVELS = {
    "beacon": 15,
    "conduit": 15,
    "end_gateway": 15,
    "end_portal": 15,
    "fire": 15,
    "glowstone": 15,
    "jack_o_lantern": 15,
    "lantern": 15,
    "lava": 15,
    "sea_lantern": 15,
    "shroomlight": 15,
    "ochre_froglight": 15,
    "pearlescent_froglight": 15,
    "verdant_froglight": 15,
    "torch": 14,
    "end_rod": 14,
    "cave_vines": 14,
    "cave_vines_plant": 14,
    "furnace": 13,
    "blast_furnace": 13,
    "smoker": 13,
    "soul_fire": 10,
    "soul_lantern": 10,
    "soul_torch": 10,
    "soul_wall_torch": 10,
    "crying_obsidian": 10,
    "redstone_torch": 7,
    "redstone_wall_torch": 7,
    "glow_lichen": 7,
    "sculk_catalyst": 6,
    "amethyst_cluster": 5,
    "large_amethyst_bud": 4,
    "magma_block": 3,
    "medium_amethyst_bud": 2,
    "small_amethyst_bud": 1,
    "brown_mushroom": 1,
    "dragon_egg": 1,
}

_FULL_SURFACE = {
    "glowstone", "sea_lantern", "shroomlight",
    "ochre_froglight", "pearlescent_froglight", "verdant_froglight",
}

_CONDITIONAL_LIT = {
    "furnace", "blast_furnace", "smoker", "campfire", "soul_campfire",
    "redstone_lamp", "redstone_torch", "redstone_wall_torch",
    "candle", "candle_cake", "redstone_ore", "deepslate_redstone_ore",
    "copper_bulb", "exposed_copper_bulb", "weathered_copper_bulb",
    "oxidized_copper_bulb", "waxed_copper_bulb",
    "waxed_exposed_copper_bulb", "waxed_weathered_copper_bulb",
    "waxed_oxidized_copper_bulb",
}


def _base(name: str) -> str:
    return name.split(":", 1)[-1]


def block_light_level(name: str, properties: dict[str, str]) -> int:
    """Return the source light level (0..15) for a complete block state."""
    base = _base(name)
    if base in _CONDITIONAL_LIT and properties.get("lit", "false") != "true":
        return 0
    if base.endswith("_candle") or base.endswith("_candle_cake"):
        if properties.get("lit", "false") != "true":
            return 0
        try:
            candles = max(1, min(4, int(properties.get("candles", "1"))))
        except ValueError:
            candles = 1
        return min(15, candles * 3)
    if base == "campfire":
        return 15
    if base == "soul_campfire":
        return 10
    if base == "redstone_lamp":
        return 15
    if base in {"redstone_ore", "deepslate_redstone_ore"}:
        return 9
    if base == "respawn_anchor":
        try:
            return 15 if int(properties.get("charges", "0")) > 0 else 0
        except ValueError:
            return 0
    if "copper_bulb" in base:
        if properties.get("lit", "false") != "true":
            return 0
        if "oxidized" in base:
            return 4
        if "weathered" in base:
            return 8
        if "exposed" in base:
            return 12
        return 15
    if base == "sea_pickle":
        if properties.get("waterlogged", "true") != "true":
            return 0
        try:
            return min(15, 3 + 3 * int(properties.get("pickles", "1")))
        except ValueError:
            return 6
    if base in {"cave_vines", "cave_vines_plant"}:
        return 14 if properties.get("berries") == "true" else 0
    if base == "end_portal_frame":
        return 1 if properties.get("eye") == "true" else 0
    if base == "redstone_wire":
        try:
            power = max(0, min(15, int(properties.get("power", "0"))))
        except ValueError:
            power = 0
        return 0 if power == 0 else max(1, round(power * 7 / 15))
    if base == "light":
        try:
            return max(0, min(15, int(properties.get("level", "15"))))
        except ValueError:
            return 15
    return _FIXED_LEVELS.get(base, 0)


def emission_profile(
    name: str,
    texture: str | None,
    properties: dict[str, str],
    explicit_level: float = 0.0,
) -> tuple[int, str] | None:
    """Return ``(level, pixel-mask profile)`` for a rendered face."""
    level = max(block_light_level(name, properties), round(explicit_level))
    if level <= 0 or not texture:
        return None
    base = _base(name)
    tex = texture.lower()
    if explicit_level > 0 and ("emissive" in tex or base in {
        "firefly_bush", "open_eyeblossom", "potted_open_eyeblossom",
    }):
        return level, "full"
    if base in _FULL_SURFACE:
        return level, "full"
    if base == "redstone_wire" or "redstone" in tex:
        return level, "red"
    if "soul_" in base or "soul_" in tex:
        return level, "soul"
    if base in {"crying_obsidian", "respawn_anchor", "end_portal", "end_gateway"}:
        return level, "purple"
    if any(token in tex for token in (
        "fire", "flame", "lantern", "torch", "candle", "campfire",
        "furnace_front_on", "smoker_front_on", "blast_furnace_front_on",
        "jack_o_lantern", "lava", "magma", "cave_vines_lit",
    )):
        return level, "warm"
    if any(token in tex for token in (
        "sea_lantern", "froglight", "shroomlight", "glowstone",
        "end_rod", "beacon", "conduit", "glow_lichen", "amethyst",
        "sculk_catalyst", "sea_pickle", "copper_bulb",
    )):
        return level, "bright"
    # Do not turn structural side/top textures into emitters merely because the
    # block itself emits light.  This is especially important for furnaces,
    # lantern frames and campfire logs.
    return None


def load_overrides(path: str | Path | None) -> dict:
    if not path:
        return {"global_multiplier": 1.0, "rules": []}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("发光配置必须是 JSON 对象")
    data.setdefault("global_multiplier", 1.0)
    data.setdefault("rules", [])
    data["global_multiplier"] = _finite_number(
        data["global_multiplier"], "global_multiplier", nonnegative=True,
    )
    for index, rule in enumerate(data["rules"]):
        if not isinstance(rule, dict):
            continue
        if "multiplier" in rule:
            rule["multiplier"] = _finite_number(
                rule["multiplier"], f"rules[{index}].multiplier", nonnegative=True,
            )
        raw_color = rule.get("color")
        if isinstance(raw_color, list) and len(raw_color) == 3:
            rule["color"] = [
                _finite_number(value, f"rules[{index}].color") for value in raw_color
            ]
    return data


def _finite_number(value, label, *, nonnegative=False, float32=False):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"发光参数 {label} 必须是有限数值") from exc
    if (isinstance(value, bool) or not math.isfinite(number)
            or (nonnegative and number < 0)
            or (float32 and abs(number) > 3.4028234663852886e38)):
        raise ValueError(f"发光参数 {label} 超出有限{'非负' if nonnegative else ''}数值范围")
    return number


def validate_light_sources(sources):
    """Validate Blender's numeric fields and JSON before writing any outputs."""
    for index, source in enumerate(sources):
        for field in ("level", "power", "radius"):
            if field in source:
                _finite_number(source[field], f"lights[{index}].{field}",
                               nonnegative=True, float32=True)
        for field in ("position", "color"):
            for value in source.get(field, ()):
                _finite_number(value, f"lights[{index}].{field}",
                               nonnegative=field == "color", float32=True)
    try:
        json.dumps(sources, allow_nan=False)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("发光灯光数据必须是有限数值的 JSON") from exc


def resolve_override(
    config: dict,
    block: str,
    properties: dict[str, str],
    region: str,
    position: tuple[int, int, int],
) -> tuple[float, tuple[float, float, float] | None]:
    """Resolve global, state and coordinate rules in declaration order."""
    multiplier = _finite_number(config.get("global_multiplier", 1.0),
                                "global_multiplier", nonnegative=True)
    color = None
    for rule in config.get("rules", []):
        if not isinstance(rule, dict):
            continue
        if rule.get("block") not in (None, "", block):
            continue
        if rule.get("region") not in (None, "", region):
            continue
        wanted_position = rule.get("position")
        if wanted_position is not None:
            try:
                if tuple(map(int, wanted_position)) != tuple(position):
                    continue
            except (TypeError, ValueError):
                continue
        wanted_properties = rule.get("properties", {})
        if not isinstance(wanted_properties, dict) or any(
            str(properties.get(str(key))) != str(value)
            for key, value in wanted_properties.items()
        ):
            continue
        multiplier = _finite_number(rule.get("multiplier", multiplier),
                                    "rule.multiplier", nonnegative=True)
        raw_color = rule.get("color")
        if isinstance(raw_color, list) and len(raw_color) == 3:
            color = tuple(max(0.0, min(1.0, _finite_number(v, "rule.color")))
                          for v in raw_color)
    return multiplier, color


def default_light_color(name: str) -> tuple[float, float, float]:
    base = _base(name)
    if "soul_" in base:
        return (0.12, 0.65, 1.0)
    if "redstone" in base:
        return (1.0, 0.04, 0.01)
    if base in {"end_portal", "end_gateway", "respawn_anchor", "crying_obsidian"}:
        return (0.58, 0.12, 1.0)
    if "froglight" in base:
        if "verdant" in base:
            return (0.55, 1.0, 0.58)
        if "pearlescent" in base:
            return (1.0, 0.55, 0.82)
        return (1.0, 0.78, 0.45)
    if base in {"sea_lantern", "conduit", "beacon", "end_rod"}:
        return (0.65, 0.9, 1.0)
    return (1.0, 0.48, 0.18)
