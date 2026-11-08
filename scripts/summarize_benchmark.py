"""Summarize RTG vcfeval output as precision / recall / F1, split by variant type.

vcfeval writes four VCFs into its output folder:
    tp.vcf.gz           our calls that match the truth set   (true positives, call side)
    tp-baseline.vcf.gz  truth variants that we found         (true positives, truth side)
    fp.vcf.gz           our calls that are not in the truth  (false positives)
    fn.vcf.gz           truth variants that we missed        (false negatives)

    precision = TP(call) / (TP(call) + FP)    "of what we called, how much is real?"
    recall    = TP(truth) / (TP(truth) + FN)  "of what is real, how much did we find?"
    F1        = harmonic mean of precision and recall

Usage:
    python scripts/summarize_benchmark.py GENOTYPE_DIR ALLELE_DIR OUT.tsv OUT.md
"""

import csv
import gzip
import sys
from collections import Counter
from pathlib import Path

TYPES = ["SNV", "INDEL", "ALL"]


def variant_type(ref: str, alt: str) -> str:
    """SNV if every allele is a single base, otherwise INDEL."""
    alts = alt.split(",")
    if len(ref) == 1 and all(len(a) == 1 for a in alts):
        return "SNV"
    return "INDEL"


def count_by_type(vcf: Path) -> Counter:
    counts = Counter()
    with gzip.open(vcf, "rt") as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            fields = line.split("\t", 5)
            vtype = variant_type(fields[3], fields[4])
            counts[vtype] += 1
            counts["ALL"] += 1
    return counts


def safe_ratio(num: int, den: int) -> float:
    return num / den if den else float("nan")


def score(folder: Path) -> dict:
    tp_call = count_by_type(folder / "tp.vcf.gz")
    tp_base = count_by_type(folder / "tp-baseline.vcf.gz")
    fp = count_by_type(folder / "fp.vcf.gz")
    fn = count_by_type(folder / "fn.vcf.gz")
    rows = {}
    for t in TYPES:
        precision = safe_ratio(tp_call[t], tp_call[t] + fp[t])
        recall = safe_ratio(tp_base[t], tp_base[t] + fn[t])
        f1 = safe_ratio(2 * precision * recall, precision + recall)
        rows[t] = {
            "truth_total": tp_base[t] + fn[t],
            "tp": tp_base[t],
            "fp": fp[t],
            "fn": fn[t],
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
    return rows


def main() -> None:
    genotype_dir, allele_dir, out_tsv, out_md = map(Path, sys.argv[1:5])
    results = {"genotype": score(genotype_dir), "allele": score(allele_dir)}

    fields = ["match", "type", "truth_total", "tp", "fp", "fn", "precision", "recall", "f1"]
    with open(out_tsv, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        for match, rows in results.items():
            for t, r in rows.items():
                writer.writerow({"match": match, "type": t, **{k: round(v, 6) if isinstance(v, float) else v for k, v in r.items()}})

    lines = [
        "| Match | Type | Truth variants | TP | FP | FN | Precision | Recall | F1 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for match, rows in results.items():
        for t, r in rows.items():
            lines.append(
                f"| {match} | {t} | {r['truth_total']:,} | {r['tp']:,} | {r['fp']:,} | {r['fn']:,} "
                f"| {r['precision']:.1%} | {r['recall']:.1%} | {r['f1']:.1%} |"
            )
    Path(out_md).write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
