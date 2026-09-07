
## 2026-09-07 (session 3): A2 input channel solved; turn manager captured live

* Natural-boot load flow re-established (title START burst -> Load -> FILE 2 ->
  world map); saved worldmap-nat.ss0. The title "hang" was the attract
  cutscene transition; a DMA-wait hang (0x0800143C) also appears on -g boots.
* Battle-menu D-pad is dead from all input sources (setKeys, keyboard);
  A/B/START/SELECT work. Root-caused the key system: poll 0x08000482->bl
  0x0800221C, struct at 0x03000000 (held/pressed/unconsumed, enable +5, mode
  +7); update_keys recomputes pressed fields from r1 each frame, so shadow
  writes get clobbered in battle.
* Working battle input: GDB P-register patch of r1 at 0x08000494
  (tools/gdb_force_key.py). Drove Wait end-to-end on the live battle.
* Trap recorded: single-stepping through update_keys and resuming mid-function
  crashes to the BIOS handler (pc=4, S04) while the screen still renders.
* Ended Marche's turn hands-off: enemies acted (442->436->438) and the menu
  auto-reopens -> the A3 autonomous loop exists.
* Turn manager sub_0809E05C captured live (30 hits, lr=0x0809E261, struct
  0x020159E4, unit array stride 0x108, candidate gates 0x080CD8B4/0x0812E368).
  Docs: docs/player-ai-control.md. Next: actor-pick decode + Controlled seam.
