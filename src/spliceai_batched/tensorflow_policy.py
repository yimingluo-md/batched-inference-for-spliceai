# SPDX-License-Identifier: GPL-3.0-or-later
"""TensorFlow execution policy shared by all SpliceAI entry points."""

from __future__ import annotations

import os
from typing import Any

DETERMINISM_ENVIRONMENT = {
    "TF_DETERMINISTIC_OPS": "1",
    "TF_CUDNN_DETERMINISTIC": "1",
    "TF_USE_CUDNN_AUTOTUNE": "0",
}


def configure_determinism_environment() -> dict[str, str]:
    """Set TensorFlow determinism controls before TensorFlow is imported."""
    for name, value in DETERMINISM_ENVIRONMENT.items():
        os.environ.setdefault(name, value)
    return {name: os.environ[name] for name in DETERMINISM_ENVIRONMENT}


def disable_tf32(tf: Any) -> bool:
    """Disable TensorFloat-32 when the installed TensorFlow exposes the API."""
    experimental = getattr(getattr(tf, "config", None), "experimental", None)
    setter = getattr(
        experimental,
        "enable_tensor_float_32_execution",
        None,
    )
    if not callable(setter):
        return False
    setter(False)
    return True


def tf32_enabled(tf: Any) -> bool | None:
    """Return the effective TensorFloat-32 state when it can be queried."""
    experimental = getattr(getattr(tf, "config", None), "experimental", None)
    getter = getattr(
        experimental,
        "tensor_float_32_execution_enabled",
        None,
    )
    if not callable(getter):
        return None
    return bool(getter())
