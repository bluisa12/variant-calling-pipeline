# Step 2: call SNVs and small indels with bcftools, normalize, and filter.


rule call_variants:
    """Find positions where the reads disagree with the reference.

    mpileup stacks up the reads at every position; call decides, using a
    statistical model, whether the sample is homozygous reference, heterozygous,
    or homozygous alternate. Low-quality reads and bases (< Q20) are ignored.
    """
    input:
        bam="results/{sample}/align/{sample}.bam",
        bai="results/{sample}/align/{sample}.bam.bai",
        ref=REF,
    output:
        temp("results/{sample}/calls/{sample}.raw.vcf.gz"),
    params:
        region=config["region"],
    threads: config["threads"]
    log:
        "results/{sample}/logs/call_variants.log",
    shell:
        """
        (bcftools mpileup --threads {threads} -f {input.ref} -r {params.region} \
            -q 20 -Q 20 -a FORMAT/AD,FORMAT/DP {input.bam} \
          | bcftools call --threads {threads} -m -v -Oz -o {output}) 2> {log}
        """


rule normalize_variants:
    """Write every variant in one standard form so it can be compared to the truth set.

    The same indel can often be written several ways (left/right-shifted);
    `norm` left-aligns indels and splits multi-allelic sites into separate rows.
    """
    input:
        vcf="results/{sample}/calls/{sample}.raw.vcf.gz",
        ref=REF,
    output:
        temp("results/{sample}/calls/{sample}.norm.vcf.gz"),
    log:
        "results/{sample}/logs/normalize_variants.log",
    shell:
        "bcftools norm -f {input.ref} -m -any -Oz -o {output} {input.vcf} 2> {log}"


rule filter_variants:
    """Label weak calls instead of deleting them, so the effect of filters can be measured.

    Calls failing the thresholds get FILTER=LowQual; passing calls get FILTER=PASS.
    """
    input:
        "results/{sample}/calls/{sample}.norm.vcf.gz",
    output:
        vcf="results/{sample}/calls/{sample}.vcf.gz",
        tbi="results/{sample}/calls/{sample}.vcf.gz.tbi",
    params:
        expr=f"QUAL<{config['filters']['min_qual']} || INFO/DP<{config['filters']['min_depth']}",
    log:
        "results/{sample}/logs/filter_variants.log",
    shell:
        """
        bcftools filter -s LowQual -e '{params.expr}' -Oz -o {output.vcf} {input} 2> {log}
        tabix -p vcf {output.vcf}
        """


rule variant_stats:
    """Summary counts: SNVs vs indels, transition/transversion ratio, quality spread."""
    input:
        vcf="results/{sample}/calls/{sample}.vcf.gz",
        tbi="results/{sample}/calls/{sample}.vcf.gz.tbi",
        ref=REF,
    output:
        "results/{sample}/qc/{sample}.bcftools_stats.txt",
    shell:
        "bcftools stats -f PASS -F {input.ref} {input.vcf} > {output}"
