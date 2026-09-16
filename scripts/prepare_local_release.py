"""Create an exact-commit HA PREVIEW archive locally; no Actions or publication.

This is packaging, not a claim that the private-Core runtime migration works.
The stable release gate remains actual HA generation/QR/review verification.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "custom_components/lotto_645"


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def main() -> None:
    if git("status", "--porcelain", "--untracked-files=normal").strip():
        raise SystemExit("Use a clean committed checkout. Nothing was packaged.")
    commit = git("rev-parse", "HEAD").decode().strip()
    manifest = json.loads(git("show", f"{commit}:{PREFIX}/manifest.json"))
    output = Path(tempfile.mkdtemp(prefix="lotto-ha-preview-"))
    archive = output / "lotto_645-preview.zip"
    subprocess.run(["git", "archive", "--format=zip", f"--output={archive}",
                    f"{commit}:{PREFIX}"], cwd=ROOT, check=True)
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        if "manifest.json" not in names or "__init__.py" not in names:
            raise SystemExit("Incomplete component archive; not a release.")
        for name in names:
            parts = name.replace("\\", "/").split("/")
            if name.startswith("/") or ".." in parts or any(p in {".env", ".git"} for p in parts):
                raise SystemExit("Unexpected path or credential file; inspect the archive before use.")
        legacy_core = any(n.startswith("lotto_core/") for n in names)
    info = output / "BUILD_INFO.json"
    info.write_text(json.dumps({
        "repository": "1bobby-git/HA-Lotto-645", "commit": commit,
        "component_version": manifest["version"], "artifact": archive.name,
        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "contains_legacy_bundled_core": legacy_core,
        "classification": "development preview; not a stable release",
        "product_tests_run_by_this_script": False,
        "private_core_transition_verified_by_this_script": False,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "SHA256SUMS.txt").write_text("".join(
        f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in (archive, info)
    ), encoding="utf-8")
    print(f"Preview files: {output}\nSource commit: {commit}")
    print("No tag/Release/workflow was created. Do not replace a working HA with this preview.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"Packaging stopped: {exc}") from None
