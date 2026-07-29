# SPDX-License-Identifier: GPL-3.0-or-later
"""Run the official SpliceAI CLI with the repository's TensorFlow policy."""

from __future__ import annotations

import random

import numpy as np

from spliceai_batched.tensorflow_policy import configure_determinism_environment

configure_determinism_environment()


def main() -> None:
    import tensorflow as tf

    from spliceai_batched.tensorflow_policy import disable_tf32

    disable_tf32(tf)
    random.seed(1)
    np.random.seed(1)
    tf.random.set_seed(1)

    # Import only after applying the numerical policy.
    from spliceai.__main__ import main as spliceai_main

    spliceai_main()


if __name__ == "__main__":
    main()
