# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path

from spliceai_batched.runtime_manifest import (
    distribution_version,
    resource_details,
    sha256,
)


def test_sha256(tmp_path: Path) -> None:
    path = tmp_path / "content"
    path.write_bytes(b"abc")
    assert sha256(str(path)) == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_resource_details_uses_modern_importlib_resources() -> None:
    details = resource_details("spliceai_batched", "__init__.py")
    assert details["bytes"] > 0
    assert len(details["sha256"]) == 64


def test_unknown_distribution_version() -> None:
    assert distribution_version("package-that-cannot-exist-93f634") == "unknown"
