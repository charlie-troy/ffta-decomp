"""Run the complete local FFTA release gate from one command.

    python tools/validate_all.py baserom.gba
"""
import argparse
import os
import subprocess
import sys
import time


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VALIDATORS = (
    "validate_ai.py",
    "validate_ai_strategy.py",
    "validate_missions.py",
    "validate_maps.py",
    "validate_items.py",
    "validate_statuses.py",
    "validate_job_fields.py",
    "validate_text.py",
)


def wsl_path(path):
    drive, tail = os.path.splitdrive(os.path.abspath(path))
    if not drive or not drive.endswith(":"):
        raise ValueError(f"cannot map path into WSL: {path}")
    return f"/mnt/{drive[0].lower()}/{tail.lstrip('\\/').replace(os.sep, '/')}"


def run(label, command):
    print()
    print(f"=== {label} ===", flush=True)
    result = subprocess.run(command, cwd=REPO)
    if result.returncode:
        print(f"FAILED: {label} (exit {result.returncode})")
    return result.returncode


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom")
    args = parser.parse_args(argv)
    rom = os.path.abspath(args.rom)
    if not os.path.isfile(rom):
        parser.error(f"ROM not found: {rom}")

    started = time.time()
    failures = []
    if os.name == "nt":
        make = ["wsl", "make"]
        make_rom = f"ROM={wsl_path(rom)}"
    else:
        make = ["make"]
        make_rom = f"ROM={rom}"

    build_steps = (
        ("build source-driven proof mod", make + ["mod-ai-always-pass", make_rom]),
        ("strict proof-mod receipt", make + ["verify-mod", make_rom,
                                               "MOD=build/ffta-mod.gba"]),
        ("function byte checks", make + ["check"]),
        ("byte-identical full ROM", make + ["rom", make_rom]),
    )
    for label, command in build_steps:
        if run(label, command):
            failures.append(label)
            break

    if not failures:
        for validator in VALIDATORS:
            label = os.path.splitext(validator)[0]
            command = [sys.executable, os.path.join("tools", validator), rom]
            if run(label, command):
                failures.append(label)

    elapsed = time.time() - started
    print()
    if failures:
        print(f"FULL VALIDATION FAILED in {elapsed:.1f}s: {', '.join(failures)}")
        return 1
    print(f"FULL VALIDATION PASSED in {elapsed:.1f}s")
    print("workspace restored to the default retail-build configuration")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
