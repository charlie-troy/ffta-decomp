"""Emit candidate C variants for a target function, for a compile-and-diff sweep.

Matching is empirical: the same behaviour written several ways compiles to
different code, and only one spelling reproduces the original. This writes
every variant as `<target>__<tag>.c` so build_all.sh can compile the batch and
sweep_report.py can say which spelling won.

Usage:
    python tools/make_sweep.py <outdir>
"""
import os
import sys

PRELUDE = """\
typedef unsigned char u8;
typedef unsigned short u16;
"""

BITS8 = "    u8 b0:1, b1:1, b2:1, b3:1, b4:1, b5:1, b6:1, b7:1;"


def obj(off, field):
    return f"struct Obj\n{{\n    u8 filler_00[{off:#x}];\n{field}\n}};\n"


# ---------------------------------------------------------------- getter, byte
GET = {}
_o = obj(0xE8, "    u8 flags;")
_b = obj(0xE8, BITS8)
N = "sub_080CD92C"

GET["plain_if"] = _o + f"""
u8 {N}(struct Obj *obj)
{{
    if (obj->flags & 0x40)
        return 1;
    return 0;
}}
"""
GET["u8_temp"] = _o + f"""
u8 {N}(struct Obj *obj)
{{
    u8 v = obj->flags & 0x40;
    if (v)
        return 1;
    return 0;
}}
"""
GET["int_temp"] = _o + f"""
u8 {N}(struct Obj *obj)
{{
    int v = obj->flags & 0x40;
    if (v)
        return 1;
    return 0;
}}
"""
GET["ternary"] = _o + f"""
u8 {N}(struct Obj *obj)
{{
    return (obj->flags & 0x40) ? 1 : 0;
}}
"""
GET["mask_first"] = _o + f"""
u8 {N}(struct Obj *obj)
{{
    if (0x40 & obj->flags)
        return 1;
    return 0;
}}
"""
GET["load_temp"] = _o + f"""
u8 {N}(struct Obj *obj)
{{
    u8 v = obj->flags;
    if (v & 0x40)
        return 1;
    return 0;
}}
"""
GET["bitfield_if"] = _b + f"""
u8 {N}(struct Obj *obj)
{{
    if (obj->b6)
        return 1;
    return 0;
}}
"""
GET["bitfield_ret"] = _b + f"""
u8 {N}(struct Obj *obj)
{{
    return obj->b6;
}}
"""
GET["else_form"] = _o + f"""
u8 {N}(struct Obj *obj)
{{
    if ((obj->flags & 0x40) != 0)
        return 1;
    else
        return 0;
}}
"""

# ---------------------------------------------------------------- setter, byte
SET = {}
_o2 = obj(0xE8, "    u8 flags;")
_b2 = obj(0xE8, BITS8)
M = "sub_080CDD88"

SET["clear_then_set"] = _o2 + f"""
void {M}(struct Obj *obj, u8 set)
{{
    obj->flags &= ~0x10;
    if (set)
        obj->flags |= 0x10;
}}
"""
SET["int_temp"] = _o2 + f"""
void {M}(struct Obj *obj, u8 set)
{{
    int v = obj->flags & ~0x10;
    obj->flags = v;
    if (set)
        obj->flags = v | 0x10;
}}
"""
SET["bitfield_assign"] = _b2 + f"""
void {M}(struct Obj *obj, u8 set)
{{
    obj->b4 = set;
}}
"""
SET["bitfield_bool"] = _b2 + f"""
void {M}(struct Obj *obj, u8 set)
{{
    obj->b4 = set ? 1 : 0;
}}
"""
SET["bitfield_if"] = _b2 + f"""
void {M}(struct Obj *obj, u8 set)
{{
    if (set)
        obj->b4 = 1;
    else
        obj->b4 = 0;
}}
"""
SET["bitfield_ne"] = _b2 + f"""
void {M}(struct Obj *obj, u8 set)
{{
    obj->b4 = (set != 0);
}}
"""

# ------------------------------------------------------- getter, halfword flags
HW = {}
_o3 = obj(0x28, "    u16 flags;")
_b3 = obj(0x28, "    u16 pad:15;\n    u16 b15:1;")
K = "sub_080C8240"

HW["u16_temp"] = _o3 + f"""
u8 {K}(struct Obj *obj)
{{
    u16 v;
    if (obj == 0)
        return 0;
    v = obj->flags & 0x8000;
    return v != 0;
}}
"""
HW["plain_ne"] = _o3 + f"""
u8 {K}(struct Obj *obj)
{{
    if (obj == 0)
        return 0;
    return (obj->flags & 0x8000) != 0;
}}
"""
HW["cast_u16"] = _o3 + f"""
u8 {K}(struct Obj *obj)
{{
    if (obj == 0)
        return 0;
    return (u16)(obj->flags & 0x8000) != 0;
}}
"""
HW["bitfield_ne"] = _b3 + f"""
u8 {K}(struct Obj *obj)
{{
    if (obj == 0)
        return 0;
    return obj->b15 != 0;
}}
"""
HW["ternary_u16"] = _o3 + f"""
u8 {K}(struct Obj *obj)
{{
    u16 v;
    if (obj == 0)
        return 0;
    v = obj->flags & 0x8000;
    return v ? 1 : 0;
}}
"""


def main(argv):
    if len(argv) != 1:
        print(__doc__)
        return 2
    outdir = argv[0]
    os.makedirs(outdir, exist_ok=True)

    n = 0
    for target, variants in ((N, GET), (M, SET), (K, HW)):
        for tag, body in variants.items():
            path = os.path.join(outdir, f"{target}__{tag}.c")
            with open(path, "w", newline="\n") as fh:
                fh.write(PRELUDE + body)
            n += 1
    print(f"wrote {n} variants to {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
