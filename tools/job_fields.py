"""Exact formulas for the 48-field retail job-table accessor.

The accessor is not a stat-at-level calculator. Except for field 2 (the
redirect marker itself), it first resolves job byte +0x05: zero means use the
selected record, 0xff means use the caller's fallback record, and any other
value redirects to that job index. It then loads or unpacks one field.
"""
from dataclasses import dataclass


TABLE = 0x08521A14 - 0x08000000
STRIDE = 0x34
COUNT = 116
ACCESSOR = 0x080C8570


@dataclass(frozen=True)
class Field:
    name: str
    formula: str
    reader: object


def u8(offset):
    return lambda record: record[offset]


def u16(offset):
    return lambda record: record[offset] | (record[offset + 1] << 8)


def bits(offset, shift, mask=0x07):
    return lambda record: (record[offset] >> shift) & mask


def split3(offset, low_shift, next_mask, next_shift):
    return lambda record: ((record[offset] >> low_shift) |
                           ((record[offset + 1] & next_mask) << next_shift))


def packed12(offset, high_shift):
    if high_shift == 0:
        return lambda record: record[offset] | ((record[offset + 1] & 0x0F) << 8)
    return lambda record: ((record[offset] >> 4) |
                           (record[offset + 1] << 4))


FIELDS = (
    Field("name_id", "u16(+0x00)", u16(0x00)),
    Field("race", "u8(+0x04)", u8(0x04)),
    Field("redirect_marker", "u8(+0x05), never redirected", u8(0x05)),
    Field("unit_kind", "u8(+0x06)", u8(0x06)),
    Field("sprite_index", "u16(+0x07)", u16(0x07)),
    Field("u16_09", "u16(+0x09)", u16(0x09)),
    Field("palette_low", "(+0x0b >> 0) & 0x0f", bits(0x0B, 0, 0x0F)),
    Field("palette_high", "(+0x0b >> 4) & 0x0f", bits(0x0B, 4, 0x0F)),
    Field("raw_0c", "u8(+0x0c)", u8(0x0C)),
    Field("portrait_palette", "u8(+0x0d)", u8(0x0D)),
    Field("portrait_index", "u8(+0x0e)", u8(0x0E)),
    Field("portrait_graphic", "u8(+0x0f)", u8(0x0F)),
    Field("a_ability_index", "u8(+0x10)", u8(0x10)),
    Field("innate_element_id", "u8(+0x11)", u8(0x11)),
    Field("resistance_0", "(+0x12 >> 3) & 7", bits(0x12, 3)),
    Field("resistance_1", "((+0x12 >> 6) | ((+0x13 & 1) << 2))", split3(0x12, 6, 1, 2)),
    Field("resistance_2", "(+0x13 >> 1) & 7", bits(0x13, 1)),
    Field("resistance_3", "(+0x13 >> 4) & 7", bits(0x13, 4)),
    Field("resistance_4", "((+0x13 >> 7) | ((+0x14 & 3) << 1))", split3(0x13, 7, 3, 1)),
    Field("resistance_5", "(+0x14 >> 2) & 7", bits(0x14, 2)),
    Field("resistance_6", "(+0x14 >> 5) & 7", bits(0x14, 5)),
    Field("resistance_7", "+0x15 & 7", bits(0x15, 0)),
    Field("status_defense", "u8(+0x16)", u8(0x16)),
    Field("base_hp", "u8(+0x17)", u8(0x17)),
    Field("base_mp", "u8(+0x18)", u8(0x18)),
    Field("base_speed", "u8(+0x19)", u8(0x19)),
    Field("base_attack", "u12(+0x1a, +0x1b low nibble)", packed12(0x1A, 0)),
    Field("base_defense", "u12(+0x1b high nibble, +0x1c)", packed12(0x1B, 4)),
    Field("base_magic_power", "u12(+0x1d, +0x1e low nibble)", packed12(0x1D, 0)),
    Field("base_resistance", "u12(+0x1e high nibble, +0x1f)", packed12(0x1E, 4)),
    Field("movement", "u8(+0x28)", u8(0x28)),
    Field("jump", "u8(+0x29)", u8(0x29)),
    Field("evade", "u8(+0x2a)", u8(0x2A)),
    Field("raw_2c", "u8(+0x2c)", u8(0x2C)),
    Field("movement_style_low", "+0x2b & 0x0f", bits(0x2B, 0, 0x0F)),
    Field("movement_style_high", "+0x2b >> 4", bits(0x2B, 4, 0x0F)),
    Field("equip_index", "u8(+0x2d)", u8(0x2D)),
    Field("ability_start", "u8(+0x2e)", u8(0x2E)),
    Field("ability_end", "u8(+0x2f)", u8(0x2F)),
    Field("job_requirement", "u8(+0x30)", u8(0x30)),
    Field("morph_family_flags", "u8(+0x31); bit 0 enables morph-family index", u8(0x31)),
    Field("growth_hp", "u8(+0x20)", u8(0x20)),
    Field("growth_mp", "u8(+0x21)", u8(0x21)),
    Field("growth_speed", "u8(+0x22)", u8(0x22)),
    Field("growth_attack", "u8(+0x23)", u8(0x23)),
    Field("growth_defense", "u8(+0x24)", u8(0x24)),
    Field("growth_magic_power", "u8(+0x25)", u8(0x25)),
    Field("growth_resistance", "u8(+0x26)", u8(0x26)),
)


def record(rom, index):
    start = TABLE + index * STRIDE
    return rom[start:start + STRIDE]


def resolve_index(rom, index, fallback):
    """Resolve +0x05 exactly; reject malformed cycles in edited data."""
    seen = set()
    while True:
        if not 0 <= index < COUNT or index in seen:
            raise ValueError("job redirect is out of range or cyclic")
        seen.add(index)
        marker = record(rom, index)[0x05]
        if marker == 0:
            return index
        index = fallback if marker == 0xFF else marker


def read_field(rom, index, fallback, field_id):
    if not 0 <= field_id < len(FIELDS):
        raise ValueError("field id outside 0x00..0x2f")
    selected = index if field_id == 2 else resolve_index(rom, index, fallback)
    return FIELDS[field_id].reader(record(rom, selected))
