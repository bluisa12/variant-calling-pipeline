#!/usr/bin/env bash
# Download a small, laptop-sized test dataset for the pipeline:
#   - chr20 of the GRCh38 reference genome (UCSC)
#   - HG003 Illumina NovaSeq reads (35x) for a 1 Mb region of chr20
#     (GIAB sample, chr20-only copy hosted by Google's DeepVariant team)
#   - The GIAB v4.2.1 truth set for that region, used to score our variant calls
#
# Usage (from the project folder, with the environment active):
#   conda activate variants
#   bash scripts/download_data.sh
#
# Needs about 1.5 GB of free space while running (large files are deleted after
# the region is extracted) and takes roughly 5-15 minutes depending on your
# connection. Safe to re-run: steps that are already done are skipped.

set -euo pipefail

SAMPLE=HG003
REGION="chr20:10000000-11000000"
CHROM="chr20"
START=10000000
END=11000000

REF_URL=https://hgdownload.soe.ucsc.edu/goldenPath/hg38/chromosomes/chr20.fa.gz
DV=https://storage.googleapis.com/deepvariant/case-study-testdata
BAM_URL=$DV/HG003.novaseq.pcr-free.35x.dedup.grch38_no_alt.chr20.bam
TRUTH_VCF_URL=$DV/HG003_GRCh38_1_22_v4.2.1_benchmark.vcf.gz
TRUTH_BED_URL=$DV/HG003_GRCh38_1_22_v4.2.1_benchmark_noinconsistent.bed

cd "$(dirname "$0")/.."
mkdir -p data/reference data/reads data/truth data/downloads

# Download a whole file with curl, resuming if a previous attempt was cut off.
# (samtools' built-in remote access proved unreliable, so we never stream.)
fetch() {
  local url=$1 out=$2 n
  [ -s "$out" ] && return 0
  for n in 1 2 3 4 5; do
    if curl -fL --retry 3 -C - --progress-bar -o "$out.part" "$url"; then
      mv "$out.part" "$out"; return 0
    fi
    echo "  download attempt $n failed, retrying in 10s..." >&2
    sleep 10
  done
  echo "ERROR: could not download $url" >&2
  return 1
}

echo "== 1/3 Reference genome (chr20, ~20 MB)"
if [ ! -s data/reference/chr20.fa ]; then
  fetch "$REF_URL" data/downloads/chr20.fa.gz
  gunzip -c data/downloads/chr20.fa.gz > data/reference/chr20.fa
  rm data/downloads/chr20.fa.gz
fi
[ -s data/reference/chr20.fa.fai ] || samtools faidx data/reference/chr20.fa
if [ ! -s data/reference/chr20.fa.bwt ]; then
  echo "  building BWA index (about a minute)..."
  bwa index data/reference/chr20.fa 2> data/reference/bwa_index.log
fi

echo "== 2/3 Reads for $REGION (downloads ~1.1 GB, keeps ~30 MB)"
if [ ! -s data/reads/${SAMPLE}_R1.fastq.gz ]; then
  fetch "$BAM_URL" data/downloads/chr20.bam
  fetch "$BAM_URL.bai" data/downloads/chr20.bam.bai
  # Keep only our region, drop secondary/supplementary alignments, then turn the
  # reads back into raw paired FASTQ so the pipeline does its own alignment.
  samtools view -b -F 0x900 -o data/downloads/region.bam data/downloads/chr20.bam "$REGION"
  samtools collate -u -O data/downloads/region.bam data/downloads/collate \
    | samtools fastq -1 data/reads/${SAMPLE}_R1.fastq.gz -2 data/reads/${SAMPLE}_R2.fastq.gz \
        -0 /dev/null -s /dev/null -n -
  rm -f data/downloads/chr20.bam data/downloads/chr20.bam.bai data/downloads/region.bam
fi

echo "== 3/3 GIAB truth set for $REGION (downloads ~160 MB, keeps <1 MB)"
if [ ! -s data/truth/${SAMPLE}_truth.vcf.gz ]; then
  fetch "$TRUTH_VCF_URL" data/downloads/truth.vcf.gz
  fetch "$TRUTH_VCF_URL.tbi" data/downloads/truth.vcf.gz.tbi
  bcftools view -r "$REGION" -Oz -o data/truth/${SAMPLE}_truth.vcf.gz data/downloads/truth.vcf.gz
  tabix -f -p vcf data/truth/${SAMPLE}_truth.vcf.gz
  rm -f data/downloads/truth.vcf.gz data/downloads/truth.vcf.gz.tbi
fi
if [ ! -s data/truth/${SAMPLE}_truth.bed ]; then
  fetch "$TRUTH_BED_URL" data/downloads/truth.bed
  # Keep only the confident regions that overlap our slice, clipped to its edges.
  awk -v c="$CHROM" -v s="$START" -v e="$END" 'BEGIN{OFS="\t"}
      $1==c && $3>s && $2<e { if ($2<s) $2=s; if ($3>e) $3=e; print $1,$2,$3 }' \
    data/downloads/truth.bed > data/truth/${SAMPLE}_truth.bed
  rm -f data/downloads/truth.bed
fi
rmdir data/downloads 2>/dev/null || true

echo
echo "Done. Summary:"
printf "  reference:         %s\n" "$(du -h data/reference/chr20.fa | cut -f1)"
printf "  read pairs:        %s\n" "$(( $(gzip -dc data/reads/${SAMPLE}_R1.fastq.gz | wc -l) / 4 ))"
printf "  truth variants:    %s\n" "$(bcftools view -H data/truth/${SAMPLE}_truth.vcf.gz | wc -l | tr -d ' ')"
printf "  confident bases:   %s\n" "$(awk '{s+=$3-$2} END{print s}' data/truth/${SAMPLE}_truth.bed)"
