"""Make the README figures from the benchmark results.

Writes a light and a dark version of each figure, so the README can show the one
that matches the reader's GitHub theme:

    PREFIX + benchmark_{light,dark}.png      precision / recall / F1 for SNVs vs indels
    PREFIX + indel_context_{light,dark}.png  share of real indels called wrong, by repeat context

Usage:
    python scripts/make_figures.py SUMMARY_TSV GENOTYPE_DIR REFERENCE REGION OUT_PREFIX
    e.g. OUT_PREFIX = docs/figures/HG003_
"""

import csv
import gzip
import subprocess
import sys
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# Colors from a colorblind-validated palette (series 1 and 2 pass every check in
# both modes). Text always uses ink colors, never the series color.
THEMES = {
    "light": {
        "surface": "#fcfcfb", "ink": "#0b0b0b", "ink2": "#52514e", "muted": "#898781",
        "grid": "#e1e0d9", "axis": "#c3c2b7", "s1": "#2a78d6", "s2": "#eb6834",
    },
    "dark": {
        "surface": "#1a1a19", "ink": "#f0efec", "ink2": "#c3c2b7", "muted": "#898781",
        "grid": "#2c2c2a", "axis": "#383835", "s1": "#3987e5", "s2": "#d95926",
    },
}
FONT = ["system-ui", "-apple-system", "Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"]
CONTEXTS = ["Non-repeat", "Homopolymer", "Tandem repeat"]


# ---------------------------------------------------------------- data

def read_summary(path):
    """Genotype-match precision / recall / F1 for SNV and INDEL, in percent."""
    out = {}
    with open(path) as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            if row["match"] == "genotype" and row["type"] in ("SNV", "INDEL"):
                out[row["type"]] = {m: float(row[m]) * 100 for m in ("precision", "recall", "f1")}
    return out


def load_region(reference, region):
    chrom, span = region.split(":")
    start, end = (int(x) for x in span.split("-"))
    pad_start = max(1, start - 1000)
    fasta = subprocess.run(
        ["samtools", "faidx", reference, f"{chrom}:{pad_start}-{end + 1000}"],
        capture_output=True, text=True, check=True,
    ).stdout
    return "".join(fasta.split("\n")[1:]).upper(), pad_start


def repeat_context(seq, offset, pos):
    """Classify a left-aligned indel by the repeat that starts right after its anchor base.

    Homopolymer: a run of one base >= 6 bp (e.g. AAAAAA).
    Tandem repeat: a 2-6 bp unit repeated >= 3 times, spanning >= 8 bp (e.g. AGAGAGAG).
    """
    s = seq[pos - offset + 1: pos - offset + 61]
    best_k, best_span = 0, 0
    for k in range(1, 7):
        unit, n = s[:k], 0
        while s[n * k:(n + 1) * k] == unit:
            n += 1
        if n * k > best_span:
            best_k, best_span = k, n * k
    if best_k == 1 and best_span >= 6:
        return "Homopolymer"
    if best_k > 1 and best_span >= 8 and best_span // best_k >= 3:
        return "Tandem repeat"
    return "Non-repeat"


def indel_positions(vcf):
    out = []
    with gzip.open(vcf, "rt") as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.split("\t", 5)
            ref, alts = f[3], f[4].split(",")
            if len(ref) == 1 and all(len(a) == 1 for a in alts):
                continue
            out.append(int(f[1]))
    return out


def indel_error_rates(genotype_dir, reference, region):
    """Per context: truth indels, and how many were missed or given the wrong genotype."""
    seq, offset = load_region(reference, region)
    found = indel_positions(Path(genotype_dir) / "tp-baseline.vcf.gz")
    wrong = indel_positions(Path(genotype_dir) / "fn.vcf.gz")
    total = Counter(repeat_context(seq, offset, p) for p in found + wrong)
    errors = Counter(repeat_context(seq, offset, p) for p in wrong)
    return {c: (errors[c], total[c]) for c in CONTEXTS}


# ---------------------------------------------------------------- drawing

def style_axes(ax, t):
    ax.set_facecolor(t["surface"])
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(t["axis"])
    ax.tick_params(colors=t["muted"], labelsize=10, length=0)
    ax.grid(axis="x", color=t["grid"], linewidth=0.8)
    ax.set_axisbelow(True)


def titles(fig, t, title, subtitle):
    fig.text(0.03, 0.95, title, color=t["ink"], fontsize=14, fontweight="bold", va="top")
    fig.text(0.03, 0.865, subtitle, color=t["ink2"], fontsize=10.5, va="top")


def plot_benchmark(scores, t, out):
    """Dot plot: one row per metric, a dot for SNVs and one for indels."""
    metrics = [("precision", "Precision"), ("recall", "Recall"), ("f1", "F1")]
    fig, ax = plt.subplots(figsize=(8, 3.6), dpi=200)
    fig.patch.set_facecolor(t["surface"])
    style_axes(ax, t)
    fig.subplots_adjust(left=0.14, right=0.97, top=0.70, bottom=0.14)

    for i, (key, _) in enumerate(metrics):
        y = len(metrics) - 1 - i
        snv, indel = scores["SNV"][key], scores["INDEL"][key]
        ax.plot([indel, snv], [y, y], color=t["axis"], linewidth=2, zorder=1, solid_capstyle="round")
        for val, color in ((snv, t["s1"]), (indel, t["s2"])):
            ax.scatter(val, y, s=110, color=color, edgecolors=t["surface"], linewidths=2, zorder=3)
        # Selective direct labels: the value for each dot, in ink, never series color
        ax.annotate(f"{indel:.1f}%", (indel, y), xytext=(-10, 0), textcoords="offset points",
                    ha="right", va="center", color=t["ink2"], fontsize=10)
        ax.annotate(f"{snv:.1f}%", (snv, y), xytext=(0, 11), textcoords="offset points",
                    ha="center", va="bottom", color=t["ink2"], fontsize=10)

    ax.set_yticks(range(len(metrics)))
    ax.set_yticklabels([label for _, label in reversed(metrics)], color=t["ink"], fontsize=11)
    ax.set_ylim(-0.6, len(metrics) - 0.35)
    ax.set_xlim(88, 101)
    ax.set_xticks(range(88, 101, 2))
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")

    titles(fig, t, "SNVs are near-perfect; indels are where the errors are",
           "Genotype-match benchmark vs. GIAB HG003 v4.2.1 truth set · chr20:10–11 Mb")
    handles = [plt.Line2D([], [], marker="o", linestyle="", markersize=9, color=c,
                          markeredgecolor=t["surface"], markeredgewidth=1.5, label=l)
               for c, l in ((t["s1"], "SNVs"), (t["s2"], "Indels"))]
    leg = fig.legend(handles=handles, loc="upper right", bbox_to_anchor=(0.97, 0.80), ncol=2,
                     frameon=False, fontsize=10, handletextpad=0.3, columnspacing=1.2)
    for text in leg.get_texts():
        text.set_color(t["ink"])
    fig.savefig(out, facecolor=t["surface"])
    plt.close(fig)


def plot_indel_context(rates, t, out):
    """Horizontal bars from zero: % of real indels called wrong, per repeat context."""
    fig, ax = plt.subplots(figsize=(8, 3.4), dpi=200)
    fig.patch.set_facecolor(t["surface"])
    style_axes(ax, t)
    fig.subplots_adjust(left=0.19, right=0.95, top=0.68, bottom=0.15)

    labels = list(reversed(CONTEXTS))
    pct = [100 * rates[c][0] / rates[c][1] if rates[c][1] else 0 for c in labels]
    ax.barh(labels, pct, height=0.5, color=t["s1"], zorder=2)
    for y, c in enumerate(labels):
        err, tot = rates[c]
        ax.annotate(f"{pct[y]:.0f}%  ({err} of {tot})", (pct[y], y), xytext=(6, 0),
                    textcoords="offset points", va="center", color=t["ink2"], fontsize=10)

    ax.set_xlim(0, max(pct) * 1.35 if max(pct) else 1)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.tick_params(axis="y", colors=t["ink"], labelsize=11)

    titles(fig, t, "Indel errors concentrate in repetitive DNA",
           "Share of real indels missed or given the wrong genotype, by sequence context")
    fig.text(0.03, 0.03,
             "Homopolymer: one base repeated ≥ 6 times (AAAAAA). "
             "Tandem repeat: a 2–6 bp unit repeated ≥ 3 times (AGAGAGAG).",
             color=t["muted"], fontsize=8.5)
    fig.savefig(out, facecolor=t["surface"])
    plt.close(fig)


def main():
    summary_tsv, genotype_dir, reference, region, prefix = sys.argv[1:6]
    Path(prefix).parent.mkdir(parents=True, exist_ok=True)
    plt.rcParams["font.family"] = FONT

    scores = read_summary(summary_tsv)
    rates = indel_error_rates(genotype_dir, reference, region)
    for mode, theme in THEMES.items():
        plot_benchmark(scores, theme, f"{prefix}benchmark_{mode}.png")
        plot_indel_context(rates, theme, f"{prefix}indel_context_{mode}.png")
    for c, (err, tot) in rates.items():
        print(f"{c:14s} {err:3d} wrong of {tot:3d} indels")


if __name__ == "__main__":
    main()
