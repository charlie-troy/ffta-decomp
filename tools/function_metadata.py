"""Load discovery metadata plus explicitly tracked non-discovery functions."""
import json
import os


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_metadata(discovery_path):
    with open(discovery_path, encoding="utf-8") as handle:
        data = json.load(handle)
    rows = data["functions"] if isinstance(data, dict) else data
    metadata = {row["name"]: row for row in rows}
    manual_path = os.path.join(REPO, "data", "manual_functions.json")
    with open(manual_path, encoding="utf-8") as handle:
        manual_rows = json.load(handle)["functions"]
    for manual in manual_rows:
        prior = metadata.get(manual["name"])
        if prior is not None and prior["offset"] != manual["offset"]:
            raise ValueError(f"conflicting offsets for {manual['name']}")
        merged = dict(prior or {})
        merged.update(manual)
        metadata[manual["name"]] = merged
    return metadata
