# SPDX-License-Identifier: GPL-3.0-or-later
"""Rate-limited validation against the Broad SpliceAI Lookup API."""

from __future__ import annotations

import argparse
import csv
import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

SCORE_FIELDS = ("DS_AG", "DS_AL", "DS_DG", "DS_DL")
POSITION_FIELDS = ("DP_AG", "DP_AL", "DP_DG", "DP_DL")
DEFAULT_ENDPOINT = "https://spliceai-38-xwkwwwxdwq-uc.a.run.app/spliceai/"


def local_annotations(path: str) -> dict[str, dict[str, list[str]]]:
    """Return local SpliceAI fields keyed by API-style variant and gene."""
    result = {}
    with open(path, encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 8:
                raise ValueError(
                    f"{path}:{line_number}: expected at least 8 "
                    f"tab-separated VCF columns, found {len(fields)}"
                )
            chrom, pos, ref = fields[0], fields[1], fields[3]
            spliceai = next(
                (
                    item.split("=", 1)[1]
                    for item in fields[7].split(";")
                    if item.startswith("SpliceAI=")
                ),
                "",
            )
            by_alt_gene = {}
            for annotation in spliceai.split(",") if spliceai else []:
                parts = annotation.split("|")
                if len(parts) == 10:
                    by_alt_gene[(parts[0], parts[1])] = parts
            for alt in fields[4].split(","):
                variant = "-".join(
                    (
                        chrom if chrom.startswith("chr") else f"chr{chrom}",
                        pos,
                        ref,
                        alt,
                    )
                )
                result[variant] = {
                    gene: parts
                    for (entry_alt, gene), parts in by_alt_gene.items()
                    if entry_alt == alt
                }
    return result


def mane_select_score(
    response: dict[str, Any],
    gene: str,
) -> dict[str, Any] | None:
    """Choose the Broad response for the requested MANE Select gene."""
    matches = [
        score
        for score in response.get("scores", [])
        if score.get("g_name") == gene and score.get("t_priority") == "MS"
    ]
    if len(matches) != 1:
        return None
    return matches[0]


def compare_fields(
    local: list[str],
    broad: dict[str, Any],
) -> dict[str, Any]:
    """Compare the eight VCF delta fields with one Broad API score."""
    if len(local) != 10:
        raise ValueError(f"expected 10 local SpliceAI fields, found {len(local)}")
    if any(value == "." for value in local[2:10]):
        return {
            "comparison_status": "local_unscored",
            "score_fields_different": 0,
            "max_score_difference": 0.0,
            "position_fields_different": 0,
        }
    local_scores = [float(value) for value in local[2:6]]
    broad_scores = [float(broad[field]) for field in SCORE_FIELDS]
    local_positions = [int(value) for value in local[6:10]]
    broad_positions = [int(broad[field]) for field in POSITION_FIELDS]
    score_differences = [
        abs(left - right) for left, right in zip(local_scores, broad_scores)
    ]
    position_differences = [
        left != right for left, right in zip(local_positions, broad_positions)
    ]
    return {
        "comparison_status": "compared",
        "local_scores": local_scores,
        "broad_scores": broad_scores,
        "local_positions": local_positions,
        "broad_positions": broad_positions,
        "score_fields_different": sum(value > 0 for value in score_differences),
        "max_score_difference": max(score_differences),
        "position_fields_different": sum(position_differences),
    }


def response_parameters_match(
    response: dict[str, Any],
    variant: str,
    distance: int,
    mask: int,
) -> bool:
    """Confirm that a cached API response belongs to the requested run."""
    return (
        response.get("variant") == variant
        and str(response.get("hg")) == "38"
        and response.get("distance") == distance
        and response.get("mask") == mask
    )


def fetch(
    endpoint: str,
    variant: str,
    distance: int,
    mask: int,
    insecure: bool,
    retries: int,
    retry_delay_seconds: float,
) -> dict[str, Any]:
    query = urllib.parse.urlencode(
        {
            "hg": 38,
            "variant": variant,
            "distance": distance,
            "mask": mask,
        }
    )
    context = ssl._create_unverified_context() if insecure else None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(
                f"{endpoint}?{query}",
                timeout=180,
                context=context,
            ) as response:
                return json.load(response)
        except (OSError, urllib.error.URLError):
            if attempt == retries:
                raise
            time.sleep(retry_delay_seconds)
    raise RuntimeError("unreachable")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vcf", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--distance", type=int, default=500)
    parser.add_argument("--mask", type=int, choices=(0, 1), default=1)
    parser.add_argument("--delay-seconds", type=float, default=20)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--retry-delay-seconds", type=float, default=30)
    parser.add_argument("--insecure", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    responses_dir = output_dir / "responses"
    responses_dir.mkdir(parents=True, exist_ok=True)
    local = local_annotations(args.vcf)
    with open(args.manifest, encoding="utf-8") as handle:
        requested = list(csv.DictReader(handle, delimiter="\t"))

    rows = []
    fetched = 0
    for index, item in enumerate(requested):
        variant, gene = item["variant"], item["gene"]
        cache_path = responses_dir / f"{index + 1:02d}.{variant}.json"
        if cache_path.exists():
            response = json.loads(cache_path.read_text(encoding="utf-8"))
        else:
            if fetched:
                time.sleep(args.delay_seconds)
            response = fetch(
                args.endpoint,
                variant,
                args.distance,
                args.mask,
                args.insecure,
                args.retries,
                args.retry_delay_seconds,
            )
            fetched += 1
            cache_path.write_text(
                json.dumps(response, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

        local_entry = local.get(variant, {}).get(gene)
        broad_entry = mane_select_score(response, gene)
        row = dict(item)
        row["broad_transcript"] = (
            str(broad_entry.get("t_id", "")) if broad_entry else ""
        )
        row["response_parameters_match"] = response_parameters_match(
            response,
            variant,
            args.distance,
            args.mask,
        )
        row["matched_mane_select"] = bool(local_entry and broad_entry)
        if local_entry and broad_entry:
            row.update(compare_fields(local_entry, broad_entry))
        rows.append(row)

    summary = {
        "endpoint": args.endpoint,
        "distance": args.distance,
        "mask": args.mask,
        "queries": len(rows),
        "matched_mane_select": sum(row["matched_mane_select"] for row in rows),
        "response_parameters_match": sum(
            row["response_parameters_match"] for row in rows
        ),
        "comparisons_performed": sum(
            row.get("comparison_status") == "compared" for row in rows
        ),
        "local_unscored": sum(
            row.get("comparison_status") == "local_unscored" for row in rows
        ),
        "score_fields_different": sum(
            row.get("score_fields_different", 0) for row in rows
        ),
        "max_score_difference": max(
            (row.get("max_score_difference", 0.0) for row in rows),
            default=0.0,
        ),
        "position_fields_different": sum(
            row.get("position_fields_different", 0) for row in rows
        ),
        "certificate_verification_disabled": args.insecure,
    }
    failure_reasons = []
    if summary["queries"] == 0:
        failure_reasons.append("no_queries")
    if summary["comparisons_performed"] != summary["queries"]:
        failure_reasons.append("not_all_queries_compared")
    if summary["matched_mane_select"] != summary["queries"]:
        failure_reasons.append("not_all_mane_select_entries_matched")
    if summary["response_parameters_match"] != summary["queries"]:
        failure_reasons.append("response_parameters_mismatch")
    if summary["max_score_difference"] > 0.011:
        failure_reasons.append("score_difference_exceeds_tolerance")
    summary["passed"] = not failure_reasons
    summary["failure_reasons"] = failure_reasons

    (output_dir / "comparison.json").write_text(
        json.dumps({"summary": summary, "results": rows}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
