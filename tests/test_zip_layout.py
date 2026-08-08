#!/usr/bin/env python3

from __future__ import annotations

import tempfile
import sys
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from mirrorlib import ZIP_LAYOUTS, validate_zip_layout  # noqa: E402


class ZipLayoutTests(unittest.TestCase):
    def make_zip(
        self,
        os_name: str,
        arch: str,
        *,
        omit: str | None = None,
        unsafe: bool = False,
    ) -> Path:
        layout = ZIP_LAYOUTS[(os_name, arch)]
        handle = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        handle.close()
        path = Path(handle.name)
        members = [str(layout["executable"]), *layout["required"], *layout["required_prefixes"]]
        with zipfile.ZipFile(path, "w") as archive:
            for member in members:
                if member == omit:
                    continue
                info = zipfile.ZipInfo(member)
                info.external_attr = (0o755 if member == layout["executable"] else 0o644) << 16
                archive.writestr(info, b"runtime")
            if unsafe:
                archive.writestr(f"{layout['root']}../escape", b"bad")
        self.addCleanup(path.unlink, missing_ok=True)
        return path

    def artifact(self, os_name: str, arch: str) -> dict:
        upstream = {
            ("linux", "x64"): "linux64",
            ("macos", "arm64"): "mac-arm64",
            ("macos", "x64"): "mac-x64",
            ("windows", "x64"): "win64",
        }[(os_name, arch)]
        return {
            "os": os_name,
            "arch": arch,
            "format": "zip",
            "filename": f"chrome-{os_name}-{arch}.zip",
            "source_url": f"https://storage.googleapis.com/example/{upstream}/chrome.zip",
        }

    def test_accepts_every_current_official_platform_layout(self) -> None:
        platforms = (
            ("linux", "x64"),
            ("windows", "x64"),
            ("macos", "arm64"),
            ("macos", "x64"),
        )
        for os_name, arch in platforms:
            with self.subTest(os=os_name, arch=arch):
                validate_zip_layout(self.make_zip(os_name, arch), self.artifact(os_name, arch))

    def test_rejects_missing_documented_executable(self) -> None:
        layout = ZIP_LAYOUTS[("linux", "x64")]
        with self.assertRaisesRegex(ValueError, "required runtime members"):
            validate_zip_layout(
                self.make_zip("linux", "x64", omit=str(layout["executable"])),
                self.artifact("linux", "x64"),
            )

    def test_rejects_path_traversal(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsafe ZIP member"):
            validate_zip_layout(
                self.make_zip("linux", "x64", unsafe=True),
                self.artifact("linux", "x64"),
            )


if __name__ == "__main__":
    unittest.main()
