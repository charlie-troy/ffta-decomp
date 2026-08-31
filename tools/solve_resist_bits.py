"""Print the causally verified eight-slot resistance field map.

Retail slots 1 and 2 are equal, so correlation alone gives an ambiguous alias.
`validate_job_fields.py` resolves it by injecting distinct values 0..7.
"""
from job_fields import FIELDS


print(f"{'field':>6}  {'slot':>4}  formula")
print("-" * 72)
for field_id in range(0x0E, 0x16):
    field = FIELDS[field_id]
    print(f"  {field_id:#04x}  {field_id - 0x0E:>4}  {field.formula}")
