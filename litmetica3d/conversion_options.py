"""Shared conversion options and validation for CLI, GUI and API callers."""

from __future__ import annotations

import math
import pathlib
from dataclasses import dataclass, replace


@dataclass
class ConversionOptions:
    input_path: pathlib.Path
    output_path: pathlib.Path
    asset_path: pathlib.Path | None = None
    output_format: str = "stl"
    stl_binary: bool = True
    scale: float = 1.0
    center: bool = False
    water: str = "cube"
    fallback: str = "cube"
    optimize: str = "safe"
    minimum_thickness: float = 1 / 16
    regions: tuple[str, ...] = ()
    color: bool = False
    textures: bool = True
    seamless_glass: bool = False
    solid_textures: bool = False
    geometry: str = "print"
    components: str = "keep"
    min_component_volume: float = 1 / 4096
    cavities: str = "preserve"
    boolean_fallback: str = "voxel32"
    emission: bool = True
    emission_strength: float = 1.0
    emission_config: pathlib.Path | None = None
    blender_lights: str = "exact"
    save_report: bool = False


def validated_options(options: ConversionOptions) -> ConversionOptions:
    """Validate every entry point without mutating the caller's options."""
    values = {}
    for name in ("scale", "minimum_thickness", "min_component_volume", "emission_strength"):
        raw = getattr(options, name)
        try:
            value = float(raw)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"无效数值：{name}") from exc
        if (isinstance(raw, bool) or not math.isfinite(value) or value < 0
                or (name in {"scale", "minimum_thickness"} and value == 0)):
            raise ValueError(f"无效数值：{name} 必须是有限{'正' if name in {'scale', 'minimum_thickness'} else '非负'}数")
        values[name] = value
    choices = {
        "output_format": {"stl", "obj"}, "geometry": {"print", "visual"},
        "water": {"cube", "drop", "level"}, "fallback": {"cube", "ignore"},
        "optimize": {"raw", "none", "safe", "experimental"},
        "components": {"keep", "remove-small", "main"},
        "cavities": {"preserve", "fill"}, "boolean_fallback": {"voxel32", "fail"},
        "blender_lights": {"none", "off", "material", "exact", "clustered"},
    }
    for name, allowed in choices.items():
        if getattr(options, name) not in allowed:
            raise ValueError(f"无效参数：{name}")
    if options.optimize == "experimental":
        values["optimize"] = "safe"
    elif options.optimize == "none":
        values["optimize"] = "raw"
    if options.blender_lights == "off":
        values["blender_lights"] = "material"
    return replace(options, **values)
