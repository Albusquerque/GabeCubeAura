"""Package the optional game-side WitcherScript telemetry bridge."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
VERSION = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["version"]
SOURCE = ROOT / "witcher_mod"
OUTPUT = ROOT / "out" / f"GabeCubeAura-Witcher3-Telemetry-v{VERSION}.zip"
CHECKSUM = ROOT / "out" / f"GabeCubeAura-Witcher3-Telemetry-v{VERSION}.sha256"


def iter_files():
    for path in sorted(SOURCE.rglob("*")):
        if path.is_file():
            yield path


def main():
    files = list(iter_files())
    if not files:
        raise SystemExit("Witcher telemetry mod sources are missing")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(OUTPUT, "w", ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(SOURCE))
    digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    CHECKSUM.write_text(f"{digest}  {OUTPUT.name}\n", encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
