# SPDX-License-Identifier: GPL-3.0-or-later

from types import SimpleNamespace

from spliceai_batched.tensorflow_policy import (
    configure_determinism_environment,
    disable_tf32,
    tf32_enabled,
)


def test_determinism_environment_is_configured_before_tensorflow(
    monkeypatch,
) -> None:
    for name in (
        "TF_DETERMINISTIC_OPS",
        "TF_CUDNN_DETERMINISTIC",
        "TF_USE_CUDNN_AUTOTUNE",
    ):
        monkeypatch.delenv(name, raising=False)

    configured = configure_determinism_environment()

    assert configured == {
        "TF_DETERMINISTIC_OPS": "1",
        "TF_CUDNN_DETERMINISTIC": "1",
        "TF_USE_CUDNN_AUTOTUNE": "0",
    }


def test_tf32_is_disabled_and_reported() -> None:
    state = {"enabled": True}
    experimental = SimpleNamespace(
        enable_tensor_float_32_execution=lambda enabled: state.update(enabled=enabled),
        tensor_float_32_execution_enabled=lambda: state["enabled"],
    )
    tf = SimpleNamespace(config=SimpleNamespace(experimental=experimental))

    assert disable_tf32(tf)
    assert tf32_enabled(tf) is False


def test_old_tensorflow_without_tf32_api_is_supported() -> None:
    tf = SimpleNamespace(config=SimpleNamespace(experimental=SimpleNamespace()))
    assert disable_tf32(tf) is False
    assert tf32_enabled(tf) is None
