"""Resolve the name id in each table to readable text.

Every table stores a name as an index into a pointer table of strings, but not
all of them point at the same one: abilities index the UI table while items and
jobs index the main one, which is why an ability's name id reads as an item
name if you use the wrong table.

    from ffta_names import Names
    names = Names(rom_bytes)
    names.ability(1)   -> 'Cure'
    names.item(1)      -> 'Shortsword'
    names.job(2)       -> 'Soldier'
    names.mission(1)   -> 'Snowball Fight'
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ffta_text import decode, decode1, score

MAIN_STRINGS = 0x08526680      # 753: jobs, monsters, clans, items
UI_STRINGS = 0x085567F0        # 767: menus, ability names at 200-599
MISSION_STRINGS = 0x0855A64C   # 512, indexed by mission id
CHAR_NAMES = 0x085680DC        # 725 first names

# The stat table stops at 375, but item ids keep going: loot and quest items
# have names and can be required by missions without having combat stats. Their
# names continue in the main table at the same offset the stat table implies,
# name index = id + 123, which holds from "Shortsword" at id 1 all the way to
# the last entry.
ITEM_NAME_OFFSET = 123
ITEM_ID_MAX = 629

ABILITY = (0x0855187C, 0x1C, 347)
ITEM = (0x0851D180, 0x20, 376)
JOB = (0x08521A14, 0x34, 116)
MISSION = (0x0855AE4C, 0x46, 512)


class Names:
    def __init__(self, rom):
        self.rom = rom

    def _string(self, table, i):
        o = table - 0x08000000 + i * 4
        if o + 4 > len(self.rom):
            return ""
        a = int.from_bytes(self.rom[o:o + 4], "little") - 0x08000000
        if not 0 <= a < len(self.rom):
            return ""
        x = decode(self.rom, a)[0]
        y = decode1(self.rom, a)[0]
        return x if score(x) >= score(y) else y

    def _name_id(self, spec, i):
        base, stride, count = spec
        if not 0 <= i < count:
            return None
        o = base - 0x08000000 + i * stride
        return int.from_bytes(self.rom[o:o + 2], "little")

    def ability(self, i):
        n = self._name_id(ABILITY, i)
        return self._string(UI_STRINGS, n) if n is not None else ""

    def item(self, i):
        n = self._name_id(ITEM, i)
        return self._string(MAIN_STRINGS, n) if n is not None else ""

    def job(self, i):
        n = self._name_id(JOB, i)
        return self._string(MAIN_STRINGS, n) if n is not None else ""

    def mission(self, i):
        return self._string(MISSION_STRINGS, i)

    def item_by_id(self, i):
        """Name for any item id, including loot beyond the stat table.

        Checked against the missions that require them: "The Hero Blade" wants
        a Rusty Sword, "Desert Rose" a Flower Vase, "A Dragon's Aid" a
        Wyrmstone.
        """
        if not 0 < i <= ITEM_ID_MAX:
            return ""
        return self._string(MAIN_STRINGS, i + ITEM_NAME_OFFSET)
