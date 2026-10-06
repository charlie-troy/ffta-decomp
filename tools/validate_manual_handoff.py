"""Exercise the real window handoff helper against synthetic UI responses.

Certifies rejection/control flow only; live action/resume remains a separate gate.
"""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import c3_manual_layer as manual


def run_case(root, label, wrong_result=False, frozen=False, target_open=False):
    out = root/label
    out.mkdir(parents=True, exist_ok=True)
    receipt = out/'run.json'
    receipt.write_text(json.dumps({'final_state': 'paused',
                                  'manual_handoff': {'pid': 12345, 'port': 2345}}))
    clock = [0.0]
    tile = [4,11]
    target = list(tile)
    ui = {'mode': 'target' if target_open else 'command', 'cursor': 0,
          'closed': False, 'ct': 735, 'walk': None}
    sent = []

    class Monitor:
        def __init__(self, *args):
            self.reads = self.faults = self.reconnects = 0
        def close(self):
            pass
        def read(self, addr, length=1):
            self.reads += 1
            if addr == manual.CMD_CURSOR:
                return bytes([ui['cursor']])
            if addr == manual.TARGET_X:
                return bytes(target)
            if addr == manual.KEYINPUT:
                return (0x3FF).to_bytes(2,'little')
            if addr == manual.ROSTER + manual.STRIDE*6 + manual.OFF_CT:
                if ui['closed']:
                    ui['ct'] += 10
                return ui['ct'].to_bytes(2,'little')
            if addr == manual.ROSTER + manual.STRIDE*6 + manual.OFF_TILE_X:
                return bytes(tile)
            raise AssertionError(f'unexpected monitor read {addr:x}')

    def sendkey(pid, token):
        k = token.split(':')[0]
        sent.append(k)
        if frozen:
            return
        if ui['mode'] == 'command':
            if k == 'DOWN':
                ui['cursor'] = (ui['cursor']+1)%4
            elif k == 'UP':
                ui['cursor'] = (ui['cursor']-1)%4
            elif k == 'A' and ui['cursor'] == 0:
                ui['mode'] = 'target'
            elif k == 'A' and ui['cursor'] == 2:
                ui['mode'] = 'facing'
        elif ui['mode'] == 'target':
            if k == 'DOWN': target[1] += 1
            elif k == 'RIGHT': target[0] += 1
            elif k == 'UP': target[1] -= 1
            elif k == 'LEFT': target[0] -= 1
            elif k == 'A':
                ui['walk'] = list(target)
                ui['mode'], ui['cursor'] = 'command', 0
        elif ui['mode'] == 'facing' and k == 'A':
            ui['closed'] = True
            if not wrong_result:
                tile[:] = ui['walk']

    fake_time = SimpleNamespace(time=lambda: clock[0], sleep=lambda seconds: clock.__setitem__(0, clock[0]+seconds))
    with patch.object(manual, 'time', fake_time), patch.object(manual, 'Monitor', Monitor), \
            patch.object(manual, 'pid_alive', lambda pid: True), \
            patch.object(manual, 'capture', lambda *args: None), \
            patch.object(manual, 'sendkey', sendkey):
        rc = manual.main(['--receipt', str(receipt), '--window-timeout', '30'])
    result = json.loads((out/'manual-layer.json').read_text())
    if wrong_result:
        assert rc == 1 and result['manual_move_committed'] is False
        assert result.get('manual_turn_committed') is None
        assert result.get('observed_ct_progress') is True
    elif frozen:
        assert rc == 1 and 'A' not in sent
    else:
        assert rc == 0 and result['manual_move_committed'] is True
        assert result['tile_before'] != result['tile_after']
    print('PASS', label)


def main():
    root = Path('outputs/autobattle/a51-manual-controls')
    run_case(root, 'command-menu-own-tile-is-not-target-mode')
    run_case(root, 'already-open-target-mode', target_open=True)
    run_case(root, 'ct-progress-with-wrong-move-rejects', wrong_result=True)
    run_case(root, 'no-cursor-echo-no-confirmation', frozen=True)
    print('MANUAL HANDOFF CONTROL PASS: 4 checks (synthetic, no live claim)')


if __name__ == '__main__':
    main()
