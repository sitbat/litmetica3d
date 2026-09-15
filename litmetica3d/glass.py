"""Seamless glass surfaces, kept separate from legacy model rendering."""
from itertools import product
from .block_models import _cuboid

COLORS = ('white orange magenta light_blue yellow lime pink gray light_gray '
          'cyan purple blue brown green red black').split()
GLASS = {'minecraft:glass', 'minecraft:glass_pane'} | {
    f'minecraft:{color}_stained_glass{suffix}'
    for color in COLORS for suffix in ('', '_pane')
}


def glass_type(name):
    return name.removesuffix('_pane') if name in GLASS else None


def boxes(name, props):
    if not name.endswith('_pane'):
        return [(0, 0, 0, 1, 1, 1)]
    a, b = 7 / 16, 9 / 16
    result = [(a, 0, a, b, 1, b)]
    arms = {'north': (a, 0, 0, b, 1, a),
            'south': (a, 0, b, b, 1, 1),
            'west': (0, 0, a, a, 1, b),
            'east': (b, 0, a, 1, 1, b)}
    result.extend(box for key, box in arms.items() if props.get(key) == 'true')
    return result


def glass_faces(name, props, position, neighbors, texture):
    """Exact local cell union; remove only same-color covered contact surfaces."""
    own = boxes(name, props)
    covering = list(own)
    for axis in range(3):
        for sign in (-1, 1):
            offset = tuple(sign if i == axis else 0 for i in range(3))
            other = neighbors.get(tuple(position[i] + offset[i] for i in range(3)))
            if other is not None and glass_type(other.name) == glass_type(name):
                covering.extend(tuple(box[i] + offset[i % 3] for i in range(6))
                                for box in boxes(other.name, other.properties))
    coordinates = [sorted({v for box in covering for v in (box[i], box[i+3])
                           if 0 <= v <= 1} | {0, 1}) for i in range(3)]

    def inside(point, candidates):
        return any(all(box[i] < point[i] < box[i+3] for i in range(3))
                   for box in candidates)

    faces = []
    for indices in product(*(range(len(c)-1) for c in coordinates)):
        lo = tuple(coordinates[i][indices[i]] for i in range(3))
        hi = tuple(coordinates[i][indices[i]+1] for i in range(3))
        center = tuple((lo[i]+hi[i])/2 for i in range(3))
        if not inside(center, own):
            continue
        for face in _cuboid(*lo, *hi, name):
            normal = (face.normal.x, face.normal.y, face.normal.z)
            probe = tuple(center[i] + normal[i]*((hi[i]-lo[i])/2+1e-7)
                          for i in range(3))
            if inside(probe, covering):
                continue
            face.texture = texture
            face.material = f'texture:{texture}'
            face.uvs = [(0, 0), (0, 1), (1, 1), (1, 0)]
            faces.append(face)
    return faces
