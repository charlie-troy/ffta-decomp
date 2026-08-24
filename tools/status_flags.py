"""Behavior-backed names for unit status bits.

Keep this deliberately small: a name belongs here only after a retail reader
does something identifiable. Layout-only flags remain in flag_map.py.
"""

STATUS_FLAGS = [
    {
        "name": "speed_down",
        "getter": 0x080CDA34,
        "setter": 0x080CDF54,
        "offset": 0xEC,
        "mask": 0x04,
        "case": 20,
        "handler": 0x08132139,
    },
    {
        "name": "sleep",
        "getter": 0x080CDA64,
        "setter": 0x080CDF9C,
        "offset": 0xEA,
        "mask": 0x02,
        "case": 37,
        "handler": 0x08132521,
    },
    {
        "name": "slow",
        "getter": 0x080CDAC4,
        "setter": 0x080CE02C,
        "offset": 0xEA,
        "mask": 0x40,
        "case": 51,
        "handler": 0x08132B45,
    },
    {
        "name": "haste",
        "getter": 0x080CDAAC,
        "setter": 0x080CE008,
        "offset": 0xEA,
        "mask": 0x20,
        "case": 52,
        "handler": 0x08132BC5,
    },
]

KNOWN_BY_GETTER = {
    0x080CDB3C: "silence",
    0x080CD914: "reflect",
    **{entry["getter"]: entry["name"] for entry in STATUS_FLAGS},
}
