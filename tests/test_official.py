# SPDX-License-Identifier: GPL-3.0-or-later

import importlib
import os
import sys
import types

import numpy as np


def test_official_entry_point_configures_all_tensorflow_controls(
    monkeypatch,
) -> None:
    names = (
        "TF_DETERMINISTIC_OPS",
        "TF_CUDNN_DETERMINISTIC",
        "TF_USE_CUDNN_AUTOTUNE",
    )
    for name in names:
        monkeypatch.delenv(name, raising=False)

    state = {
        "tf32": True,
        "tensorflow_seed": None,
        "numpy_seed": None,
        "called": False,
    }
    tensorflow = types.ModuleType("tensorflow")
    tensorflow.config = types.SimpleNamespace(
        experimental=types.SimpleNamespace(
            enable_tensor_float_32_execution=lambda enabled: state.update(tf32=enabled)
        )
    )
    tensorflow.random = types.SimpleNamespace(
        set_seed=lambda value: state.update(tensorflow_seed=value)
    )
    monkeypatch.setattr(
        np.random,
        "seed",
        lambda value: state.update(numpy_seed=value),
    )
    spliceai = types.ModuleType("spliceai")
    upstream_main = types.ModuleType("spliceai.__main__")
    upstream_main.main = lambda: state.update(called=True)
    monkeypatch.setitem(sys.modules, "tensorflow", tensorflow)
    monkeypatch.setitem(sys.modules, "spliceai", spliceai)
    monkeypatch.setitem(sys.modules, "spliceai.__main__", upstream_main)
    sys.modules.pop("spliceai_batched.official", None)

    official = importlib.import_module("spliceai_batched.official")
    official.main()

    assert {name: os.environ.get(name) for name in names} == {
        "TF_DETERMINISTIC_OPS": "1",
        "TF_CUDNN_DETERMINISTIC": "1",
        "TF_USE_CUDNN_AUTOTUNE": "0",
    }
    assert state == {
        "tf32": False,
        "tensorflow_seed": 1,
        "numpy_seed": 1,
        "called": True,
    }
    sys.modules.pop("spliceai_batched.official", None)
