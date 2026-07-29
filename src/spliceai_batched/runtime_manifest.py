# SPDX-License-Identifier: GPL-3.0-or-later
"""Capture hashes and versions from a separately installed SpliceAI runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def distribution_version(name: str) -> str:
    try:
        from importlib.metadata import PackageNotFoundError, version
    except ImportError:  # pragma: no cover - Python 3.7 compatibility
        from pkg_resources import DistributionNotFound, get_distribution

        try:
            return get_distribution(name).version
        except DistributionNotFound:
            return "unknown"

    try:
        return version(name)
    except PackageNotFoundError:  # pragma: no cover - environment-dependent
        return "unknown"


@contextmanager
def resource_path(package: str, resource: str) -> Iterator[Path]:
    """Yield a package resource path without requiring pkg_resources."""
    try:
        from importlib.resources import as_file, files
    except ImportError:  # pragma: no cover - Python 3.7 compatibility
        from pkg_resources import resource_filename

        yield Path(resource_filename(package, resource))
        return

    with as_file(files(package).joinpath(resource)) as path:
        yield path


def resource_details(package: str, resource: str) -> dict[str, object]:
    with resource_path(package, resource) as path:
        return {
            "sha256": sha256(str(path)),
            "bytes": path.stat().st_size,
        }


def collect() -> dict[str, object]:
    import numpy as np
    import pysam

    from spliceai_batched import __version__
    from spliceai_batched.tensorflow_policy import (
        configure_determinism_environment,
        disable_tf32,
        tf32_enabled,
    )

    determinism_environment = configure_determinism_environment()

    import tensorflow as tf

    disable_tf32(tf)

    models = {}
    for index in range(1, 6):
        name = f"spliceai{index}.h5"
        models[name] = resource_details("spliceai", f"models/{name}")
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "runner_version": __version__,
        "git_commit": os.environ.get(
            "SPLICEAI_BATCHED_GIT_COMMIT",
            "unknown",
        ),
        "spliceai": distribution_version("spliceai"),
        "tensorflow": tf.__version__,
        "numpy": np.__version__,
        "pysam": pysam.__version__,
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "tensorflow_determinism_environment": determinism_environment,
        "tf32_enabled": tf32_enabled(tf),
        "models": models,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    args = parser.parse_args()
    content = json.dumps(collect(), indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(content, encoding="utf-8")
    else:
        print(content, end="")


if __name__ == "__main__":
    main()
