"""Geometry-preserving post processing for axis-aligned quad faces."""

from collections import defaultdict
from dataclasses import dataclass

from .block_models import Face, Vec3

_DIGITS = 9


@dataclass(frozen=True)
class _Rect:
    face: Face
    axis: str
    offset: float
    sign: int
    u1: float
    v1: float
    u2: float
    v2: float

    @property
    def plane_key(self):
        return self.axis, self.offset

    @property
    def exact_key(self):
        return self.axis, self.offset, self.u1, self.v1, self.u2, self.v2


def _q(value: float) -> float:
    return round(float(value), _DIGITS)


def _rect(face: Face) -> _Rect | None:
    if len(face.vertices) != 4:
        return None
    normal = (_q(face.normal.x), _q(face.normal.y), _q(face.normal.z))
    nonzero = [i for i, value in enumerate(normal) if abs(value) == 1]
    if len(nonzero) != 1 or any(
        value not in (-1.0, 0.0, 1.0) for value in normal
    ):
        return None
    axis_index = nonzero[0]
    coords = [
        (vertex.x, vertex.y, vertex.z)[axis_index] for vertex in face.vertices
    ]
    if max(coords) - min(coords) > 10 ** (-_DIGITS):
        return None
    axis = "xyz"[axis_index]
    uv_indices = [i for i in range(3) if i != axis_index]
    us = [(v.x, v.y, v.z)[uv_indices[0]] for v in face.vertices]
    vs = [(v.x, v.y, v.z)[uv_indices[1]] for v in face.vertices]
    unique_u = sorted({_q(value) for value in us})
    unique_v = sorted({_q(value) for value in vs})
    if len(unique_u) != 2 or len(unique_v) != 2:
        return None
    expected = {
        (unique_u[0], unique_v[0]), (unique_u[0], unique_v[1]),
        (unique_u[1], unique_v[0]), (unique_u[1], unique_v[1]),
    }
    actual = {(_q(u), _q(v)) for u, v in zip(us, vs)}
    if actual != expected:
        return None
    for i in range(4):
        du = abs(_q(us[(i + 1) % 4] - us[i]))
        dv = abs(_q(vs[(i + 1) % 4] - vs[i]))
        if du > 0 and dv > 0:
            return None
    return _Rect(
        face, axis, _q(coords[0]), int(normal[axis_index]),
        _q(min(us)), _q(min(vs)), _q(max(us)), _q(max(vs)),
    )


def _face_from_rect(rect: _Rect, material: str) -> Face:
    a, o, s = rect.axis, rect.offset, rect.sign
    u1, v1, u2, v2 = rect.u1, rect.v1, rect.u2, rect.v2
    if a == "x":
        verts = [Vec3(o, u1, v1), Vec3(o, u1, v2),
                 Vec3(o, u2, v2), Vec3(o, u2, v1)]
        normal = Vec3(s, 0, 0)
        reverse = s > 0
    elif a == "y":
        verts = [Vec3(u1, o, v1), Vec3(u1, o, v2),
                 Vec3(u2, o, v2), Vec3(u2, o, v1)]
        normal = Vec3(0, s, 0)
        reverse = s < 0
    else:
        verts = [Vec3(u1, v1, o), Vec3(u2, v1, o),
                 Vec3(u2, v2, o), Vec3(u1, v2, o)]
        normal = Vec3(0, 0, s)
        reverse = s < 0
    if reverse:
        verts.reverse()
    return Face(verts, normal, material)


def _cancel_exact(rects: list[_Rect]) -> list[_Rect]:
    groups: dict[tuple, dict[int, list[_Rect]]] = defaultdict(
        lambda: {1: [], -1: []}
    )
    for rect in rects:
        groups[rect.exact_key][rect.sign].append(rect)
    result = []
    for signs in groups.values():
        count = min(len(signs[1]), len(signs[-1]))
        result.extend(signs[1][count:count + 1])
        result.extend(signs[-1][count:count + 1])
    return result


def _try_merge(a: _Rect, b: _Rect) -> _Rect | None:
    if (a.axis, a.offset, a.sign, a.face.material) != (
        b.axis, b.offset, b.sign, b.face.material
    ):
        return None
    if a.v1 == b.v1 and a.v2 == b.v2 and (a.u2 == b.u1 or b.u2 == a.u1):
        values = min(a.u1, b.u1), a.v1, max(a.u2, b.u2), a.v2
    elif a.u1 == b.u1 and a.u2 == b.u2 and (a.v2 == b.v1 or b.v2 == a.v1):
        values = a.u1, min(a.v1, b.v1), a.u2, max(a.v2, b.v2)
    else:
        return None
    merged = _Rect(a.face, a.axis, a.offset, a.sign, *values)
    return _Rect(
        _face_from_rect(merged, a.face.material),
        merged.axis, merged.offset, merged.sign, *values,
    )


def _merge_adjacent(rects: list[_Rect]) -> list[_Rect]:
    current = list(rects)
    for orientation in ("u", "v"):
        groups: dict[tuple, list[_Rect]] = defaultdict(list)
        for item in current:
            common = (
                item.axis, item.offset, item.sign, item.face.material,
            )
            key = (
                common + (item.v1, item.v2)
                if orientation == "u"
                else common + (item.u1, item.u2)
            )
            groups[key].append(item)
        merged_all: list[_Rect] = []
        for group in groups.values():
            group.sort(
                key=(lambda r: (r.u1, r.u2))
                if orientation == "u" else (lambda r: (r.v1, r.v2))
            )
            active = group[0]
            for following in group[1:]:
                merged = _try_merge(active, following)
                if merged is None:
                    merged_all.append(active)
                    active = following
                else:
                    active = merged
            merged_all.append(active)
        current = merged_all
    return current


def optimize_faces(faces: list[Face], level: str = "safe") -> list[Face]:
    """Optimize faces without fuzzy plane matching or silhouette changes."""
    if level == "raw":
        return list(faces)
    rects, passthrough = [], []
    for face in faces:
        item = _rect(face)
        (rects if item is not None else passthrough).append(item or face)
    rects = _cancel_exact(rects)
    if level in {"safe", "experimental"}:
        rects = _merge_adjacent(rects)
    return [item.face for item in rects] + passthrough
