"""File-level regressions for Litematica storage and lightweight summaries."""
import io
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from litmetica3d.litematic import (
    BlockState, _decode_block_states, _read_packed_index,
    load_schematic, load_schematic_info,
)
from litmetica3d.nbt import (
    TAG_BYTE, TAG_BYTE_ARRAY, TAG_LONG_ARRAY, _read_tag, _write_tag_value,
    read_nbt, write_gzip_nbt, write_nbt,
)


def _pack(indices, bits):
    words = [0] * ((len(indices) * bits + 63) // 64)
    for index, value in enumerate(indices):
        word, shift = divmod(index * bits, 64)
        words[word] |= value << shift
        if shift + bits > 64:
            words[word + 1] |= value >> (64 - shift)
    return [(word & ((1 << 64) - 1)) - (1 << 64) if word & (1 << 63)
            else word & ((1 << 64) - 1) for word in words]


class LitematicStorageTests(unittest.TestCase):
    def test_two_entry_palette_keeps_four_consecutive_stone_blocks(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'four-stone.litematic'
            write_gzip_nbt(path, {
                'Version': 6, 'MinecraftDataVersion': 3955,
                'Metadata': {'Name': 'Four stones', 'TotalBlocks': 4},
                'Regions': {'stones': {
                    'Position': {'x': 10, 'y': 20, 'z': 30},
                    'Size': {'x': 4, 'y': 1, 'z': 1},
                    'BlockStatePalette': [
                        {'Name': 'minecraft:air'}, {'Name': 'minecraft:stone'},
                    ],
                    'BlockStates': _pack([1] * 4, 2),
                }},
            })
            schematic = load_schematic(path)
            self.assertEqual({(x, 0, 0): 1 for x in range(4)}, schematic.regions['stones'].blocks)

    def test_single_entry_palette_still_uses_two_bits(self):
        self.assertEqual(33, len(_decode_block_states(
            [0, 0], [BlockState('minecraft:stone')], (33, 1, 1))))
        with self.assertRaisesRegex(ValueError, 'Truncated BlockStates'):
            _decode_block_states([0], [BlockState('minecraft:stone')], (33, 1, 1))

    def test_signed_words_and_cross_word_indices(self):
        palette = [BlockState(f'minecraft:block_{index}') for index in range(20)]
        indices = [index % len(palette) for index in range(70)]
        blocks = _decode_block_states(_pack(indices, 5), palette, (-7, 2, 5))
        for index, value in enumerate(indices):
            x = index % 7 - 6
            z = (index // 7) % 5
            y = index // 35
            self.assertEqual(value, blocks[x, y, z])

    def test_truncated_or_missing_block_storage_is_not_silent_air(self):
        palette = [BlockState('minecraft:air'), BlockState('minecraft:stone')]
        for words in ([], [1]):
            with self.subTest(words=words), self.assertRaisesRegex(ValueError, 'Truncated BlockStates'):
                _decode_block_states(words, palette, (33, 1, 1))
        with self.assertRaisesRegex(ValueError, 'no block palette'):
            _decode_block_states([0], [], (1, 1, 1))

    def test_invalid_palette_index_reports_its_location(self):
        palette = [BlockState('minecraft:air'), BlockState('minecraft:stone')]
        with self.assertRaisesRegex(ValueError, 'Invalid palette index 3 at block 1'):
            _decode_block_states(_pack([1, 3], 2), palette, (2, 1, 1))

    def test_direct_read_rejects_incomplete_cross_word_value(self):
        with self.assertRaisesRegex(ValueError, 'Truncated BlockStates'):
            _read_packed_index([0], 12, 5)

    def test_summary_has_region_info_but_never_decodes_arrays_or_blocks(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'summary.litematic'
            write_gzip_nbt(path, {
                'Version': 6, 'Metadata': {'Name': 'Summary'},
                'Regions': {'large': {
                    'Position': {'x': -10, 'y': 2, 'z': 3},
                    'Size': {'x': 320000, 'y': 1, 'z': 1},
                    'BlockStatePalette': [{'Name': 'minecraft:stone'}],
                    'BlockStates': [0] * 10000,
                    'TileEntities': [{'id': 'minecraft:chest', 'Items': [{'data': 'large'}]}],
                    'Entities': [{'Pos': [1.0, 2.0, 3.0]}],
                }},
            })
            with patch('litmetica3d.nbt._read_long_array', side_effect=AssertionError('allocated array')), \
                    patch('litmetica3d.litematic._decode_block_states', side_effect=AssertionError('decoded blocks')):
                info = load_schematic_info(path)
            self.assertEqual('Summary', info.name)
            region = info.regions['large']
            self.assertEqual((-10, 2, 3), region.position)
            self.assertEqual((320000, 1, 1), region.size)
            self.assertEqual('minecraft:stone', region.palette[0].name)
            self.assertEqual({}, region.blocks)
            self.assertEqual([], region.tile_entities)


class NBTValidationTests(unittest.TestCase):
    def test_tag_byte_read_and_write_are_signed(self):
        for value in (-128, -1, 0, 1, 127):
            with self.subTest(value=value):
                stream = io.BytesIO()
                _write_tag_value(stream, value, TAG_BYTE)
                self.assertEqual(struct.pack('>b', value), stream.getvalue())
                stream.seek(0)
                self.assertEqual(value, _read_tag(stream, TAG_BYTE))

    def test_boolean_round_trip_retains_nbt_byte_representation(self):
        self.assertEqual({'flag': 1}, read_nbt(io.BytesIO(write_nbt({'flag': True}))))

    def test_negative_array_lengths_are_rejected(self):
        for tag in (TAG_BYTE_ARRAY, TAG_LONG_ARRAY):
            with self.subTest(tag=tag), self.assertRaisesRegex(ValueError, 'Negative NBT array length'):
                _read_tag(io.BytesIO(struct.pack('>i', -1)), tag)

    def test_short_array_payload_is_rejected_even_when_skipped(self):
        raw = b'\x0a\x00\x00\x0c\x00\x0bBlockStates' + struct.pack('>iq', 2, 0)
        for skip in (frozenset(), frozenset({'BlockStates'})):
            with self.subTest(skip=skip), self.assertRaisesRegex(ValueError, 'Truncated NBT payload'):
                read_nbt(io.BytesIO(raw), skip_tags=skip)

    def test_truncated_string_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Truncated NBT payload'):
            read_nbt(io.BytesIO(b'\x0a\x00\x05abc'))
