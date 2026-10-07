"""Verify local recovery receipt hashes and exact available Git blob bytes.

Binary evidence may remain local. Tracked evidence must retain its captured
bytes; normalized line endings cannot silently pass the committed-hash audit.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", action="append", required=True)
    parser.add_argument("--git-ref", default="HEAD", help="Git revision, or index for staged bytes")
    args = parser.parse_args()
    errors = []
    checked = 0
    for receipt in args.receipt:
        doc = json.loads(Path(receipt).read_text())
        for section in ("source_sha256", "evidence_sha256"):
            for path, digest in doc[section].items():
                local = Path(path)
                if not local.is_file() or hashlib.sha256(local.read_bytes()).hexdigest() != digest:
                    errors.append(f"{receipt}: local hash differs: {path}")
                spec = ":" + path if args.git_ref == "index" else args.git_ref + ":" + path
                exists = subprocess.run(["git", "cat-file", "-e", spec], capture_output=True)
                if exists.returncode == 0:
                    blob = subprocess.run(["git", "show", spec], capture_output=True, check=True).stdout
                    if hashlib.sha256(blob).hexdigest() != digest:
                        errors.append(f"{receipt}: Git blob hash differs ({args.git_ref}): {path}")
                    checked += 1
    if errors:
        print("\n".join(errors))
        return 1
    print(f"PASS local receipt hashes and {checked} available Git blobs ({args.git_ref})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
