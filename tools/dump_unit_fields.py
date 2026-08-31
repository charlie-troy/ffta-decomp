"""Print the exact job-accessor field formulas.

The former instruction-pattern guesser was intentionally retired after it
misread redirect guards and packed loads. `tools/job_fields.py` is validated
against all 5,568 retail record/field combinations.

Usage:
    python tools/dump_unit_fields.py [--md]
"""
import sys

from job_fields import FIELDS


def main(argv):
    markdown = "--md" in argv
    if markdown:
        print("| field | name | formula |")
        print("|---|---|---|")
        for field_id, field in enumerate(FIELDS):
            print(f"| `{field_id:#04x}` | {field.name} | `{field.formula}` |")
    else:
        for field_id, field in enumerate(FIELDS):
            print(f"field {field_id:#04x}  {field.name:<24} {field.formula}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
