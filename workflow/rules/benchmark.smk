# Step 3: score our calls against the GIAB truth set with RTG vcfeval.
#
# vcfeval is the comparison engine used by the GA4GH benchmarking standard. It
# matches variants by the haplotypes they produce, so a correct call written in a
# different but equivalent way still counts as correct.
#
# Two comparisons are run:
#   genotype - the call must have the right alleles AND the right genotype
#              (e.g. heterozygous 0/1 vs homozygous 1/1). This is the strict score.
#   allele   - only the alleles need to match (--squash-ploidy). The gap between
#              the two scores tells us how many errors are genotype mistakes.

SDF = config["reference"].removesuffix(".fa") + ".sdf"
RTG_MEM = config.get("rtg_mem", "2g")


rule reference_sdf:
    """Convert the reference FASTA to RTG's own format (done once)."""
    input:
        REF,
    output:
        directory(SDF),
    log:
        "results/logs/reference_sdf.log",
    shell:
        "rm -rf {output} && rtg RTG_MEM={RTG_MEM} format -o {output} {input} > {log} 2>&1"


rule vcfeval:
    input:
        calls="results/{sample}/calls/{sample}.vcf.gz",
        calls_tbi="results/{sample}/calls/{sample}.vcf.gz.tbi",
        truth=config["truth_vcf"],
        bed=config["truth_bed"],
        sdf=SDF,
    output:
        directory("results/{sample}/benchmark/{mode}"),
    params:
        extra=lambda wc: "--squash-ploidy" if wc.mode == "allele" else "",
    wildcard_constraints:
        mode="genotype|allele",
    log:
        "results/{sample}/logs/vcfeval_{mode}.log",
    shell:
        # vcfeval refuses to write into an existing folder, so clear it first.
        # Only PASS calls are scored; -f QUAL lets vcfeval also build a ROC curve.
        """
        rm -rf {output}
        rtg RTG_MEM={RTG_MEM} vcfeval -b {input.truth} -c {input.calls} -t {input.sdf} \
            -e {input.bed} -f QUAL {params.extra} -o {output} > {log} 2>&1
        """


rule benchmark_summary:
    """Precision, recall and F1, split into SNVs and indels."""
    input:
        genotype="results/{sample}/benchmark/genotype",
        allele="results/{sample}/benchmark/allele",
        script="scripts/summarize_benchmark.py",
    output:
        tsv="results/{sample}/benchmark/{sample}.summary.tsv",
        md="results/{sample}/benchmark/{sample}.summary.md",
    shell:
        "python {input.script} {input.genotype} {input.allele} {output.tsv} {output.md}"


rule figures:
    """README figures (light + dark). Written to docs/ so they are committed to git."""
    input:
        summary="results/{sample}/benchmark/{sample}.summary.tsv",
        genotype="results/{sample}/benchmark/genotype",
        ref=REF,
        script="scripts/make_figures.py",
    output:
        multiext("docs/figures/{sample}_benchmark", "_light.png", "_dark.png"),
        multiext("docs/figures/{sample}_indel_context", "_light.png", "_dark.png"),
    params:
        region=config["region"],
    log:
        "results/{sample}/logs/figures.log",
    shell:
        "python {input.script} {input.summary} {input.genotype} {input.ref} "
        "{params.region} docs/figures/{wildcards.sample}_ > {log} 2>&1"
