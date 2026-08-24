"""Behavior-backed names for unit status bits.

Keep this deliberately small: a name belongs here only after a retail reader
does something identifiable. Layout-only flags remain in flag_map.py.
"""

STATUS_FLAGS = [
    {
        "name": "speed_down",
        "ability_name": "Speedbreak",
        "ability_id": 80,
        "raw_effect": 49,
        "getter": 0x080CDA34,
        "setter": 0x080CDF54,
        "offset": 0xEC,
        "mask": 0x04,
        "case": 20,
        "handler": 0x08132139,
    },
    {
        "name": "sleep",
        "ability_name": "Sleep",
        "ability_id": 32,
        "raw_effect": 97,
        "getter": 0x080CDB24,
        "setter": 0x080CE0B8,
        "offset": 0xEB,
        "mask": 0x04,
        "case": 45,
        "handler": 0x081328E1,
    },
    {
        "name": "slow",
        "ability_name": "Slow",
        "ability_id": 35,
        "raw_effect": 104,
        "getter": 0x080CDAC4,
        "setter": 0x080CE02C,
        "offset": 0xEA,
        "mask": 0x40,
        "case": 51,
        "handler": 0x08132B45,
    },
    {
        "name": "haste",
        "ability_name": "Haste",
        "ability_id": 42,
        "raw_effect": 105,
        "getter": 0x080CDAAC,
        "setter": 0x080CE008,
        "offset": 0xEA,
        "mask": 0x20,
        "case": 52,
        "handler": 0x08132BC5,
    },
    {
        "name": "poison",
        "ability_name": "Poison",
        "ability_id": 64,
        "raw_effect": 125,
        "getter": 0x080CD974,
        "setter": 0x080CDE38,
        "offset": 0xE9,
        "mask": 0x02,
        "case": 61,
        "handler": 0x081331A5,
    },
]

KNOWN_BY_GETTER = {
    0x080CDB3C: "silence",
    0x080CD914: "reflect",
    **{entry["getter"]: entry["name"] for entry in STATUS_FLAGS},
}
