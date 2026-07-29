# SPDX-License-Identifier: GPL-3.0-or-later

import importlib
import sys
import types
from typing import ClassVar

import numpy as np
import pytest


@pytest.fixture
def cli(monkeypatch):
    tensorflow = types.ModuleType("tensorflow")
    tensorflow.random = types.SimpleNamespace(set_seed=lambda seed: None)
    pysam = types.ModuleType("pysam")
    spliceai = types.ModuleType("spliceai")
    utils = types.ModuleType("spliceai.utils")
    utils.Annotator = object
    utils.normalise_chrom = lambda chrom, target: chrom
    utils.one_hot_encode = lambda sequence: np.zeros(
        (len(sequence), 4),
        dtype=np.int64,
    )
    spliceai.utils = utils

    monkeypatch.setitem(sys.modules, "tensorflow", tensorflow)
    monkeypatch.setitem(sys.modules, "pysam", pysam)
    monkeypatch.setitem(sys.modules, "spliceai", spliceai)
    monkeypatch.setitem(sys.modules, "spliceai.utils", utils)
    sys.modules.pop("spliceai_batched.cli", None)
    module = importlib.import_module("spliceai_batched.cli")
    yield module
    sys.modules.pop("spliceai_batched.cli", None)


class Record:
    chrom = "1"
    pos = 6000
    ref = "A"
    alts = ("C",)

    def __init__(self, info=None):
        self.info = {} if info is None else info


class UnscoredAnnotator:
    ref_fasta: ClassVar = {"1": object()}
    models: ClassVar = []

    @staticmethod
    def get_name_and_strand(chrom, pos):
        return [], [], []


def test_unscored_record_preserves_existing_annotation(cli) -> None:
    record = Record({"SpliceAI": ("C|OLD|0.10|0.00|0.00|0.00|0|0|0|0",)})

    cli.annotate_chunk(
        [record],
        UnscoredAnnotator(),
        distance=1,
        mask=0,
        batch_size=1,
    )

    assert record.info["SpliceAI"][0].startswith("C|OLD|")


class Sequence:
    def __init__(self, value):
        self.seq = value


class Contig:
    def __getitem__(self, item):
        return Sequence("A" * 10003)


class Model:
    def __init__(self, seen_dtypes):
        self.seen_dtypes = seen_dtypes

    def predict(self, inputs, batch_size, verbose):
        self.seen_dtypes.append(inputs.dtype)
        return np.zeros((len(inputs), inputs.shape[1] - 10000, 3), dtype=np.float32)


class ScoredAnnotator:
    ref_fasta: ClassVar = {"1": Contig()}

    def __init__(self, seen_dtypes):
        self.models = [Model(seen_dtypes) for _ in range(5)]

    @staticmethod
    def get_name_and_strand(chrom, pos):
        return ["GENE"], ["+"], [0]

    @staticmethod
    def get_pos_data(index, pos):
        return -5001, 5001, 99


def test_one_hot_inputs_are_compacted_before_batching(cli) -> None:
    seen_dtypes = []
    record = Record()

    cli.annotate_chunk(
        [record],
        ScoredAnnotator(seen_dtypes),
        distance=1,
        mask=0,
        batch_size=1,
    )

    assert seen_dtypes
    assert set(seen_dtypes) == {np.dtype(np.uint8)}
    assert "SpliceAI" in record.info


class WrongCountModel:
    @staticmethod
    def predict(inputs, batch_size, verbose):
        return np.zeros(
            (len(inputs) - 1, inputs.shape[1] - 10000, 3),
            dtype=np.float32,
        )


def test_prediction_count_mismatch_is_rejected(cli) -> None:
    encoded = np.zeros((10003, 4), dtype=np.uint8)

    with pytest.raises(
        RuntimeError,
        match="returned 0 predictions for 1 inputs",
    ):
        cli.predict_ensemble([WrongCountModel()], [encoded], batch_size=1)
