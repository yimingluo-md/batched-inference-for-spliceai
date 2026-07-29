# SPDX-License-Identifier: GPL-3.0-or-later
# Adapted from SpliceAI 1.3.1, Copyright (c) 2013-2018 Illumina, Inc.
# Substantially modified in 2026 by Yiming Luo; see NOTICE.
"""Batched VCF annotator that uses a separately installed SpliceAI 1.3.1."""

from __future__ import annotations

import argparse
import collections
import logging
import random
import time

import numpy as np
import pysam

from spliceai_batched.tensorflow_policy import (
    configure_determinism_environment,
    disable_tf32,
)

configure_determinism_environment()

import tensorflow as tf

disable_tf32(tf)

random.seed(1)
np.random.seed(1)
tf.random.set_seed(1)

from spliceai.utils import Annotator, normalise_chrom, one_hot_encode

from spliceai_batched import __version__
from spliceai_batched.scoring import format_score, orient_prediction

LOGGER = logging.getLogger(__name__)

INFO_HEADER = (
    '##INFO=<ID=SpliceAI,Number=.,Type=String,Description="SpliceAIv1.3.1 '
    "variant annotation. These include delta scores (DS) and delta positions (DP) "
    "for acceptor gain (AG), acceptor loss (AL), donor gain (DG), and donor "
    "loss (DL). Format: "
    'ALLELE|SYMBOL|DS_AG|DS_AL|DS_DG|DS_DL|DP_AG|DP_AL|DP_DG|DP_DL">'
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("-I", "--input", required=True)
    parser.add_argument("-O", "--output", required=True)
    parser.add_argument("-R", "--reference", required=True)
    parser.add_argument("-A", "--annotation", required=True)
    parser.add_argument("-D", "--distance", type=int, default=50)
    parser.add_argument("-M", "--mask", type=int, choices=(0, 1), default=0)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--chunk-records", type=int, default=2048)
    return parser.parse_args()


def predict_ensemble(models, arrays, batch_size):
    """Return the mean prediction across the five official models."""
    if not arrays:
        return np.empty((0, 0, 3), dtype=np.float32)
    inputs = np.stack(arrays)
    mean = None
    for model_index, model in enumerate(models, start=1):
        predicted = np.asarray(model.predict(inputs, batch_size=batch_size, verbose=0))
        if predicted.ndim == 0 or predicted.shape[0] != inputs.shape[0]:
            observed = 0 if predicted.ndim == 0 else predicted.shape[0]
            raise RuntimeError(
                f"model {model_index} returned {observed} predictions "
                f"for {inputs.shape[0]} inputs"
            )
        if mean is None:
            mean = predicted.astype(np.float32, copy=False)
        else:
            if predicted.shape != mean.shape:
                raise RuntimeError(
                    f"model {model_index} returned shape {predicted.shape}; "
                    f"expected {mean.shape}"
                )
            mean += predicted
    mean /= len(models)
    return mean


def annotate_chunk(records, ann, distance, mask, batch_size):
    """Prepare, batch-predict, and annotate one ordered list of VCF records."""
    cov = 2 * distance + 1
    wid = 10000 + cov
    scores = [[] for _ in records]
    tasks = []
    reference_inputs = collections.OrderedDict()
    sequence_cache = {}
    fasta_target = next(iter(ann.ref_fasta.keys()))

    for record_index, record in enumerate(records):
        try:
            chrom, pos, ref, alts = (
                record.chrom,
                record.pos,
                record.ref,
                record.alts,
            )
            len(alts)
        except TypeError:
            LOGGER.warning("Skipping record (bad input): %s", record)
            continue

        genes, strands, indexes = ann.get_name_and_strand(chrom, pos)
        if len(indexes) == 0:
            continue

        normalized_chrom = normalise_chrom(chrom, fasta_target)
        sequence_key = (normalized_chrom, pos)
        if sequence_key not in sequence_cache:
            try:
                sequence_cache[sequence_key] = ann.ref_fasta[normalized_chrom][
                    pos - wid // 2 - 1 : pos + wid // 2
                ].seq
            except (IndexError, ValueError):
                LOGGER.warning("Skipping record (fasta issue): %s", record)
                continue
        seq = sequence_cache[sequence_key]

        if seq[wid // 2 : wid // 2 + len(ref)].upper() != ref:
            LOGGER.warning("Skipping record (ref issue): %s", record)
            continue
        if len(seq) != wid:
            LOGGER.warning("Skipping record (near chromosome end): %s", record)
            continue
        if len(ref) > 2 * distance:
            LOGGER.warning("Skipping record (ref too long): %s", record)
            continue

        for alt in alts:
            for gene, strand, index in zip(genes, strands, indexes):
                if any(symbol in alt for symbol in (".", "-", "*", "<", ">")):
                    continue

                slot = len(scores[record_index])
                if len(ref) > 1 and len(alt) > 1:
                    scores[record_index].append(f"{alt}|{gene}|.|.|.|.|.|.|.|.")
                    continue
                scores[record_index].append(None)

                dist_start, dist_end, dist_exon = ann.get_pos_data(index, pos)
                pad_left = max(wid // 2 + dist_start, 0)
                pad_right = max(wid // 2 - dist_end, 0)
                x_ref_seq = (
                    "N" * pad_left + seq[pad_left : wid - pad_right] + "N" * pad_right
                )
                x_alt_seq = (
                    x_ref_seq[: wid // 2] + str(alt) + x_ref_seq[wid // 2 + len(ref) :]
                )
                x_ref = one_hot_encode(x_ref_seq).astype(np.uint8, copy=False)
                x_alt = one_hot_encode(x_alt_seq).astype(np.uint8, copy=False)
                if strand == "-":
                    x_ref = x_ref[::-1, ::-1]
                    x_alt = x_alt[::-1, ::-1]

                reference_key = (normalized_chrom, pos, int(index))
                reference_inputs.setdefault(reference_key, x_ref)
                tasks.append(
                    {
                        "record_index": record_index,
                        "slot": slot,
                        "ref_key": reference_key,
                        "alt": str(alt),
                        "gene": str(gene),
                        "dist_exon": int(dist_exon),
                        "ref_len": len(ref),
                        "alt_len": len(alt),
                        "reverse_output": strand == "-",
                        "x_alt": x_alt,
                    }
                )

    reference_keys = list(reference_inputs)
    reference_predictions = predict_ensemble(
        ann.models, list(reference_inputs.values()), batch_size
    )
    reference_by_key = dict(zip(reference_keys, reference_predictions))

    tasks_by_length = collections.defaultdict(list)
    for task in tasks:
        tasks_by_length[len(task["x_alt"])].append(task)

    for same_length_tasks in tasks_by_length.values():
        alt_predictions = predict_ensemble(
            ann.models,
            [task["x_alt"] for task in same_length_tasks],
            batch_size,
        )
        for task, y_alt in zip(same_length_tasks, alt_predictions):
            reverse_output = task["reverse_output"]
            score = format_score(
                task,
                orient_prediction(
                    reference_by_key[task["ref_key"]],
                    reverse_output,
                ),
                orient_prediction(y_alt, reverse_output),
                cov,
                mask,
            )
            scores[task["record_index"]][task["slot"]] = score

    for record, record_scores in zip(records, scores):
        completed = [score for score in record_scores if score is not None]
        if completed:
            record.info["SpliceAI"] = completed


def main() -> None:
    args = parse_args()
    if not 0 <= args.distance < 5000:
        raise ValueError("--distance must be between 0 and 4999")
    if args.batch_size < 1:
        raise ValueError("--batch-size must be positive")
    if args.chunk_records < 1:
        raise ValueError("--chunk-records must be positive")

    input_vcf = pysam.VariantFile(args.input)
    if "SpliceAI" not in input_vcf.header.info:
        input_vcf.header.add_line(INFO_HEADER)
    mode = "wz" if args.output.endswith(".gz") else "w"
    output_vcf = pysam.VariantFile(args.output, mode=mode, header=input_vcf.header)
    annotator = Annotator(args.reference, args.annotation)

    processed = 0
    started = time.monotonic()
    while True:
        records = []
        for _ in range(args.chunk_records):
            try:
                records.append(next(input_vcf))
            except StopIteration:
                break
        if not records:
            break

        annotate_chunk(
            records,
            annotator,
            args.distance,
            args.mask,
            args.batch_size,
        )
        for record in records:
            output_vcf.write(record)
        processed += len(records)
        elapsed = time.monotonic() - started
        LOGGER.info(
            "processed=%d elapsed_seconds=%.1f variants_per_second=%.2f",
            processed,
            elapsed,
            processed / elapsed,
        )

    input_vcf.close()
    output_vcf.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    main()
