# Step 1: align reads to the reference, mark duplicates, and collect QC metrics.

REF = config["reference"]


rule bwa_mem:
    """Align paired reads with BWA-MEM, then coordinate-sort.

    `samtools fixmate -m` adds mate tags that `samtools markdup` needs later.
    BWA keeps read pairs together in its output, so fixmate can run directly on it.
    """
    input:
        r1=config["reads"]["r1"],
        r2=config["reads"]["r2"],
        ref=REF,
        idx=multiext(REF, ".amb", ".ann", ".bwt", ".pac", ".sa"),
    output:
        temp("results/{sample}/align/{sample}.sorted.bam"),
    params:
        # Read group: tells downstream tools which sample the reads belong to.
        rg=r"@RG\tID:{sample}\tSM:{sample}\tPL:ILLUMINA",
    threads: config["threads"]
    log:
        "results/{sample}/logs/bwa_mem.log",
    shell:
        """
        (bwa mem -t {threads} -R '{params.rg}' {input.ref} {input.r1} {input.r2} \
            | samtools fixmate -m - - \
            | samtools sort -@ {threads} -o {output} -) 2> {log}
        """


rule mark_duplicates:
    """Flag PCR/optical duplicates so they don't inflate evidence for a variant."""
    input:
        "results/{sample}/align/{sample}.sorted.bam",
    output:
        bam="results/{sample}/align/{sample}.bam",
        stats="results/{sample}/qc/{sample}.markdup.txt",
    threads: config["threads"]
    log:
        "results/{sample}/logs/markdup.log",
    shell:
        "samtools markdup -@ {threads} -f {output.stats} {input} {output.bam} 2> {log}"


rule index_bam:
    input:
        "results/{sample}/align/{sample}.bam",
    output:
        "results/{sample}/align/{sample}.bam.bai",
    shell:
        "samtools index {input}"


rule alignment_qc:
    """Mapping rate, insert size, error rate, and depth across the target region."""
    input:
        bam="results/{sample}/align/{sample}.bam",
        bai="results/{sample}/align/{sample}.bam.bai",
        ref=REF,
    output:
        flagstat="results/{sample}/qc/{sample}.flagstat.txt",
        stats="results/{sample}/qc/{sample}.stats.txt",
        coverage="results/{sample}/qc/{sample}.coverage.txt",
    params:
        region=config["region"],
    shell:
        """
        samtools flagstat {input.bam} > {output.flagstat}
        samtools stats -r {input.ref} {input.bam} > {output.stats}
        samtools coverage -r {params.region} {input.bam} > {output.coverage}
        """
