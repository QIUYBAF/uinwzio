from __future__ import annotations

import hashlib
import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "dist" / "RNGtuber"
RELEASE = ROOT / "release"
ZIP_PATH = RELEASE / "RNGtuber_V1_Windows.zip"


def main() -> None:
    executable = BUILD / "RNGtuber.exe"
    if not executable.is_file():
        raise SystemExit(f"missing packaged executable: {executable}")
    for filename in ("README.md", "QA_KNOWN_ISSUES.md"):
        shutil.copy2(ROOT / filename, BUILD / filename)
    RELEASE.mkdir(parents=True, exist_ok=True)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(BUILD.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(BUILD).as_posix())
    with zipfile.ZipFile(ZIP_PATH) as archive:
        bad = archive.testzip()
        names = set(archive.namelist())
    if bad is not None or "RNGtuber.exe" not in names:
        raise SystemExit(f"release validation failed: bad={bad!r}, exe={'RNGtuber.exe' in names}")
    digest = hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest()
    (RELEASE / "RNGtuber_V1_Windows.zip.sha256").write_text(
        f"{digest}  {ZIP_PATH.name}\n", encoding="ascii"
    )
    print(f"{ZIP_PATH} ({ZIP_PATH.stat().st_size} bytes)")
    print(f"sha256={digest}")


if __name__ == "__main__":
    main()
