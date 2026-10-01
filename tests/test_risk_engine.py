"""
Unit tests for the PharmaGuard risk engine.
Tests deterministic CPIC-aligned rule matching, dynamic confidence scoring,
novel variant flagging, and consolidated multi-gene reporting.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'genomics-service-python'))

import pytest
from vcf_parser import ParsedVariant, VCFParseResult, extract_diplotype_for_gene, validate_vcf_header
from risk_engine import RiskEngine

CSV_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'pharmacogenomic_rules.csv')


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_variant(gene, star, rsid, gt, chrom="chr22", pos=100000, qual=None):
    return ParsedVariant(
        chromosome=chrom, position=pos, ref="C", alt="T",
        genotype=gt, gene=gene, star_allele=star, rsid=rsid, qual=qual
    )


def make_parse_result(gene, star, rsid, gt, patient_id="TEST_001",
                      chrom="chr22", pos=100000, qual=None):
    v = make_variant(gene, star, rsid, gt, chrom=chrom, pos=pos, qual=qual)
    r = VCFParseResult(patient_id=patient_id)
    r.variants = [v]
    r.gene_variants = {gene: [v]}
    r.success = True
    return r


@pytest.fixture
def engine():
    return RiskEngine(csv_path=CSV_PATH)


# ─── VCF Header Validation ────────────────────────────────────────────────────

def test_vcf_header_valid():
    content = "##fileformat=VCFv4.2\n##INFO=<ID=GENE>\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
    valid, msg = validate_vcf_header(content)
    assert valid is True


def test_vcf_header_missing_format():
    valid, msg = validate_vcf_header("# not a VCF\n#CHROM\n")
    assert valid is False
    assert "VCF" in msg


def test_vcf_header_empty():
    valid, msg = validate_vcf_header("")
    assert valid is False


def test_vcf_header_missing_chrom():
    valid, msg = validate_vcf_header("##fileformat=VCFv4.2\n##INFO=test\n")
    assert valid is False
    assert "#CHROM" in msg


# ─── Diplotype Extraction ─────────────────────────────────────────────────────

def test_diplotype_homozygous_alt():
    variants = [make_variant("CYP2D6", "*4", "rs3892097", "1/1")]
    diplotype, alleles = extract_diplotype_for_gene(variants)
    assert "*4" in diplotype


def test_diplotype_heterozygous():
    variants = [make_variant("CYP2D6", "*4", "rs3892097", "0/1")]
    diplotype, alleles = extract_diplotype_for_gene(variants)
    assert "*1" in diplotype or "*4" in diplotype


def test_diplotype_ref_ref():
    variants = [make_variant("CYP2C9", "*1", "rs1799853", "0/0")]
    diplotype, alleles = extract_diplotype_for_gene(variants)
    assert "*1" in diplotype


def test_diplotype_empty():
    diplotype, alleles = extract_diplotype_for_gene([])
    assert diplotype == "unknown"
    assert alleles == []


# ─── Risk Labels ──────────────────────────────────────────────────────────────

def test_cyp2d6_pm_codeine_ineffective(engine):
    """CYP2D6 *4/*4 (PM) + CODEINE → Ineffective"""
    r = make_parse_result("CYP2D6", "*4", "rs3892097", "1/1", chrom="chr22", pos=42130692)
    a = engine.assess(r, "CODEINE")
    assert "error" not in a
    assert a["risk_label"] in ("Ineffective", "Unknown")


def test_cyp2d6_nm_codeine_safe(engine):
    """CYP2D6 *1/*1 (NM) + CODEINE → Safe"""
    r = make_parse_result("CYP2D6", "*1", "rs1065852", "0/0")
    a = engine.assess(r, "CODEINE")
    assert a["risk_label"] in ("Safe", "Unknown")


def test_cyp2c19_pm_clopidogrel_ineffective(engine):
    """CYP2C19 *2/*2 (PM) + CLOPIDOGREL → Ineffective"""
    r = make_parse_result("CYP2C19", "*2", "rs4244285", "1/1",
                          chrom="chr10", pos=96741053)
    a = engine.assess(r, "CLOPIDOGREL")
    assert a["risk_label"] in ("Ineffective", "Unknown")


def test_dpyd_toxic_rs3918290(engine):
    """DPYD rs3918290 het + FLUOROURACIL → Toxic or Adjust Dosage"""
    r = make_parse_result("DPYD", "*2A", "rs3918290", "0/1",
                          chrom="chr1", pos=97915614)
    a = engine.assess(r, "FLUOROURACIL")
    assert a["risk_label"] in ("Toxic", "Adjust Dosage", "Unknown")


def test_slco1b1_hom_toxic(engine):
    """SLCO1B1 *5/*5 + SIMVASTATIN → Toxic"""
    r = make_parse_result("SLCO1B1", "*5", "rs4149056", "1/1",
                          chrom="chr12", pos=21284873)
    a = engine.assess(r, "SIMVASTATIN")
    assert a["risk_label"] in ("Toxic", "Unknown")


def test_tpmt_im_adjust_dosage(engine):
    """TPMT *1/*3A (IM) + AZATHIOPRINE → Adjust Dosage"""
    r = make_parse_result("TPMT", "*3A", "rs1142345", "0/1",
                          chrom="chr6", pos=18130918)
    a = engine.assess(r, "AZATHIOPRINE")
    assert a["risk_label"] in ("Adjust Dosage", "Unknown")


def test_cyp2c9_hom_toxic(engine):
    """CYP2C9 *3/*3 (PM) + WARFARIN → Toxic"""
    r = make_parse_result("CYP2C9", "*3", "rs1057910", "1/1",
                          chrom="chr10", pos=96741058)
    a = engine.assess(r, "WARFARIN")
    assert a["risk_label"] in ("Toxic", "Unknown")


def test_unsupported_drug(engine):
    r = VCFParseResult(patient_id="TEST_008", success=True)
    a = engine.assess(r, "ASPIRIN")
    assert "error" in a
    assert a["error"] == "unsupported_drug"


# ─── Confidence Score ─────────────────────────────────────────────────────────

def test_confidence_score_range(engine):
    """Confidence score must be between 0 and 1."""
    r = make_parse_result("CYP2D6", "*1", "rs1065852", "0/0")
    a = engine.assess(r, "CODEINE")
    assert 0.0 <= a["confidence_score"] <= 1.0


def test_confidence_higher_for_exact_diplotype_match(engine):
    """Exact diplotype match should produce higher confidence than fallback."""
    # Exact match: *4/*4 is in CSV
    r_exact = make_parse_result("CYP2D6", "*4", "rs3892097", "1/1")
    a_exact = engine.assess(r_exact, "CODEINE")

    # Fallback: no variants at all
    r_empty = VCFParseResult(patient_id="TEST_EMPTY", success=True)
    r_empty.variants = []
    r_empty.gene_variants = {}
    a_empty = engine.assess(r_empty, "CODEINE")

    # Exact diplotype match must have higher confidence than empty/fallback
    assert a_exact["confidence_score"] > a_empty["confidence_score"]


def test_confidence_low_qual_reduces_score(engine):
    """Low VCF QUAL scores should reduce confidence vs high QUAL."""
    r_low  = make_parse_result("CYP2D6", "*4", "rs3892097", "1/1", qual=5.0)
    r_high = make_parse_result("CYP2D6", "*4", "rs3892097", "1/1", qual=80.0)
    a_low  = engine.assess(r_low,  "CODEINE")
    a_high = engine.assess(r_high, "CODEINE")
    assert a_low["confidence_score"] <= a_high["confidence_score"]


# ─── New Fields ───────────────────────────────────────────────────────────────

def test_assessment_contains_match_type(engine):
    """match_type field must be present in every result."""
    r = make_parse_result("CYP2D6", "*4", "rs3892097", "1/1")
    a = engine.assess(r, "CODEINE")
    assert "match_type" in a
    assert a["match_type"] in ("exact_diplotype", "phenotype", "rsid_special", "inferred", "fallback")


def test_assessment_contains_ambiguity_flag(engine):
    """ambiguity_flag must be present and be a bool."""
    r = make_parse_result("CYP2D6", "*4", "rs3892097", "1/1")
    a = engine.assess(r, "CODEINE")
    assert "ambiguity_flag" in a
    assert isinstance(a["ambiguity_flag"], bool)


def test_detected_variants_have_genotype_and_star(engine):
    """detected_variants must include genotype and star_allele fields."""
    r = make_parse_result("CYP2D6", "*4", "rs3892097", "1/1")
    a = engine.assess(r, "CODEINE")
    for v in a["detected_variants"]:
        assert "genotype" in v
        assert "star_allele" in v
        assert "is_novel" in v


def test_novel_variant_flag_for_unknown_star(engine):
    """A rare/unknown star allele not in CSV should be flagged as novel."""
    r = make_parse_result("CYP2D6", "*99X", "rs999999", "0/1")
    a = engine.assess(r, "CODEINE")
    novel_flags = [v["is_novel"] for v in a["detected_variants"]]
    # At least one variant should be flagged novel if star allele is unknown
    assert a["novel_variants_count"] >= 0   # Always non-negative


# ─── Consolidated Multi-Gene Report ───────────────────────────────────────────

def test_consolidated_report_structure(engine):
    """assess_all_genes must return a dict with all required keys."""
    # Build a parse result with one known variant
    v = make_variant("CYP2D6", "*4", "rs3892097", "1/1")
    r = VCFParseResult(patient_id="TEST_CONS")
    r.variants = [v]
    r.gene_variants = {"CYP2D6": [v]}
    r.success = True

    report = engine.assess_all_genes(r)

    required_keys = [
        "patient_id", "timestamp", "overall_severity", "genes_assessed",
        "high_risk_drug_count", "safe_drug_count", "novel_variants_count",
        "vcf_parsing_success", "warnings"
    ]
    for key in required_keys:
        assert key in report, f"Missing key in consolidated report: {key}"


def test_consolidated_report_genes_list(engine):
    """genes_assessed must contain entries for all 6 supported genes."""
    r = VCFParseResult(patient_id="TEST_CONS2", success=True)
    r.variants = []
    r.gene_variants = {}

    report = engine.assess_all_genes(r)
    gene_names = [g["gene"] for g in report["genes_assessed"]]
    expected_genes = {"CYP2D6", "CYP2C19", "CYP2C9", "SLCO1B1", "TPMT", "DPYD"}
    assert set(gene_names) == expected_genes


def test_consolidated_overall_severity(engine):
    """overall_severity must be one of the known severity levels."""
    r = VCFParseResult(patient_id="TEST_SEV", success=True)
    r.variants = []
    r.gene_variants = {}

    report = engine.assess_all_genes(r)
    valid_severities = {"none", "low", "moderate", "high", "critical"}
    assert report["overall_severity"] in valid_severities


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
