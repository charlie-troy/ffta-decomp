# AI evaluator: the 92 effect cases

> Historical linear report. For reconstruction boundaries use the generated,
> control-flow-aware [AI evaluator partitions](ai-evaluator-cfg.md). This file
> can include shared tails and literal-pool bytes in a case's apparent length.

`sub_080C32C0` ends in a 92-way switch on the action's effect id, dispatching
through the table at `0x080C3624`. Every target is inside the function, so it
is one switch rather than a table of handlers, which is why Ghidra reports
"could not recover jumptable, too many branches" and omits all of it.

Regenerate with:

```bash
python tools/analyze_switch.py <rom> build/functions_all.json \
    0x080C3624 92 0x080C32C0 0x080C47A6
```

66 distinct bodies cover the 92 ids; several ids share a body.

The common shape is a scoring helper (`sub_08002804`), a maths routine at
`0x08142950`, a status getter for the effect being considered, and a branch
back into the shared tail. Cases that only branch to the tail are effects the
evaluator does not score specially.

```

case ids                     addr   len  calls
------------------------------------------------------------------------------------------------
1                      0x080c3794    32  sub_0812E368, sub_080C32C0
5,18,26,39,40,44,...   0x080c37b4    12  sub_080C32C0
2                      0x080c37c0    40  sub_0812E368, sub_080C32C0
3                      0x080c37e8   118  sub_08002804, 0x8142950, sub_080C32C0, sub_080CDBE4
7                      0x080c385e     8  sub_080C32C0
8                      0x080c3866   102  sub_08022840, sub_081342A8, sub_081342B4, sub_081342C0
9                      0x080c38cc    52  sub_080C7EA4, 0x8142ab0, sub_080C32C0
10                     0x080c3900    74  sub_08002804, 0x8142950, sub_080C32C0, sub_080CD8FC
11,53,54,58,79         0x080c394a    94  sub_08022840, 0x8142250, sub_08133BB4, sub_08022854
12                     0x080c39a8    74  sub_08002804, 0x8142950, sub_080C32C0, sub_080CD95C
13                     0x080c39f2    10  sub_080CD95C, sub_080C32C0
15,50                  0x080c39fc    38  sub_080C32C0, sub_08002804, 0x8142950
16                     0x080c3a22    28  sub_080C32C0, sub_080C13C8
17                     0x080c3a3e    74  sub_08002804, 0x8142950, sub_080C32C0, sub_080CDA1C
19                     0x080c3a88    74  sub_08002804, 0x8142950, sub_080C32C0, sub_080CDADC
20                     0x080c3ad2    74  sub_08002804, 0x8142950, sub_080C32C0, sub_080CDA34
4,6,21                 0x080c3b1c    10  sub_080C32C0
22                     0x080c3b26    74  sub_08002804, 0x8142950, sub_080C32C0, sub_080CDB9C
23                     0x080c3b70    10  sub_080CDB9C, sub_080C32C0
24                     0x080c3b7a    74  sub_08002804, 0x8142950, sub_080C32C0, sub_080CDB84
25                     0x080c3bc4    10  sub_080CDB84, sub_080C32C0
27                     0x080c3bce    74  sub_08002804, 0x8142950, sub_080C32C0, sub_080CD944
28                     0x080c3c18    98  sub_08002804, 0x8142950, sub_080C32C0, sub_080CDAAC
29                     0x080c3c7a    74  sub_080CDB9C, sub_080CDB84, sub_080CD98C, sub_080CD944
30                     0x080c3cc4    60  sub_080CDB9C, sub_080CDB84, sub_080CDAC4, sub_080CDADC
31                     0x080c3d00    74  sub_08002804, 0x8142950, sub_080C32C0, sub_080CD8E4
32                     0x080c3d4a    74  sub_08002804, 0x8142950, sub_080C32C0, sub_080CD914
33                     0x080c3d94    74  sub_08002804, 0x8142950, sub_080C32C0, sub_080CD8CC
35                     0x080c3dde    74  sub_08002804, 0x8142950, sub_080C32C0, sub_080CD98C
36                     0x080c3e28     8  sub_080CD98C
37                     0x080c3e30    74  sub_08002804, 0x8142950, sub_080C32C0, sub_080CDA64
38                     0x080c3e7a    48  sub_080C32C0, sub_080C7EA4, 0x8142ab0
41                     0x080c3eaa    88  sub_08002804, 0x8142950, sub_080C32C0, sub_080CDB6C
42                     0x080c3f02    74  sub_08002804, 0x8142950, sub_080C32C0, sub_080CDA94
43                     0x080c3f4c   172  sub_08002804, 0x8142950, sub_080CDAC4, sub_080CD98C
45                     0x080c3ff8    70  sub_08002804, 0x8142950, sub_080CDB24
46                     0x080c403e    70  sub_08002804, 0x8142950, sub_080CD92C
47                     0x080c4084     8  sub_080CD92C
48                     0x080c408c    96  sub_08002804, 0x8142950, sub_080CDC5C, sub_080C32C0
49                     0x080c40ec    50  sub_080C7EA4, sub_080CA7A4, sub_080C32C0
51                     0x080c411e    70  sub_08002804, 0x8142950, sub_080CDAC4
52                     0x080c4164    70  sub_08002804, 0x8142950, sub_080CDAAC
55                     0x080c41aa   110  sub_08002804, 0x8142950, sub_080CDA4C, sub_080C7EA4
56                     0x080c4218    70  sub_08002804, 0x8142950, sub_080CDB3C
57                     0x080c425e     8  sub_080CDB3C
59                     0x080c4266    66  sub_08002804, 0x8142950, sub_080C32C0
60                     0x080c42a8    70  sub_08002804, 0x8142950, sub_080CD9BC
61                     0x080c42ee    70  sub_08002804, 0x8142950, sub_080CD974
62                     0x080c4334    70  sub_08002804, 0x8142950, sub_080CD974
63                     0x080c437a    90  sub_08002804, 0x8142950, sub_080C7EA4, sub_08131030
64                     0x080c43d4    20  sub_08131030, sub_080C32C0
65,66,67               0x080c43e8    80  sub_08002804, 0x8142950, sub_0812F0D8, sub_080C32C0
69                     0x080c4438    70  sub_08002804, 0x8142950, sub_080CDBFC
70                     0x080c447e    70  sub_08002804, 0x8142950, sub_080CD9EC
71                     0x080c44c4    70  sub_08002804, 0x8142950, sub_080CDBB4
72                     0x080c450a    70  sub_08002804, 0x8142950, sub_080CDC5C
73                     0x080c4550    70  sub_08002804, 0x8142950, sub_080CDC44
75                     0x080c4596    18  sub_080C7EA4, sub_080C32C0
76                     0x080c45a8    70  sub_08002804, 0x8142950, sub_080CDC2C
77                     0x080c45ee    70  sub_08002804, 0x8142950, sub_080CDC8C
78                     0x080c4634    70  sub_08002804, 0x8142950, sub_080CDC74
80                     0x080c467a    84  sub_08002804, 0x8142950, sub_080CDB54, sub_080C32C0
82                     0x080c46ce    68  sub_08002804, 0x8142950, sub_080CDB0C
83                     0x080c4712    76  sub_08002804, 0x8142950, sub_080CDAF4, sub_080C32C0
92                     0x080c475e    28  sub_080C832C, sub_080C32C0
14,34,74,84,85,86...   0x080c477a    44  sub_080C32C0
```
