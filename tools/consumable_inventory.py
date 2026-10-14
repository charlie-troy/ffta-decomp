"""Read the native consumable pool; never synthesize unknown quantities.

080CB2B4 searches fourteen four-byte records at 02001940+5A4 and
returns the matched u8 owned quantity minus its u8 reserved quantity.
080CB388 maps Item-menu rows 1..14 to global item IDs in ITEM_IDS order.
This reader rejects corrupt arithmetic instead of exposing native u8 wrap.
Inventory availability alone is not target or law legality.
"""
from dataclasses import dataclass
import hashlib

from recovery_menu import exact, integer, require

INVENTORY = 0x02001EE4
ITEM_IDS = (362, 363, 364, 365, 366, 375, 369, 370, 371, 373, 372, 367, 374, 368)


def decode_inventory(raw):
    require(len(raw) == 56, 'short consumable inventory')
    result = {i: {'owned':0, 'reserved':0, 'available':0, 'record':None} for i in ITEM_IDS}
    seen = set()
    for offset in range(0, 56, 4):
        item, owned, reserved = integer(raw, offset, 2), raw[offset+2], raw[offset+3]
        if item == 0:
            require(owned == reserved == 0, 'empty inventory record carries quantity')
            continue
        require(item in ITEM_IDS and item not in seen, 'foreign/aliased consumable inventory item')
        require(0 <= reserved <= owned <= 99, 'invalid consumable quantity/reservation')
        seen.add(item)
        result[item] = {'owned':owned, 'reserved':reserved, 'available':owned-reserved,
                        'record':INVENTORY+offset}
    return result


@dataclass(frozen=True)
class InventoryToken:
    raw: bytes
    sha256: str

    def items(self):
        return decode_inventory(self.raw)


class ConsumableInventory:
    def __init__(self, g):
        self.g = g

    def snapshot(self):
        raw = exact(self.g, INVENTORY, 56)
        decode_inventory(raw)
        require(exact(self.g, INVENTORY, 56) == raw, 'consumable inventory changed during read')
        return InventoryToken(raw, hashlib.sha256(raw).hexdigest())

    def revalidate(self, token):
        require(isinstance(token, InventoryToken) and self.snapshot() == token,
                'stale/foreign consumable inventory token')
        return token
