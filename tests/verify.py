"""
PharmaGuard v2 — Quick Verification Script
Validates:
  1. Python syntax for all service modules
  2. Module imports
  3. CSV knowledge base schema
  4. Sample VCF file integrity
  5. Deterministic risk engine (per-drug + consolidated)
  6. Dynamic confidence scoring
  7. Novel variant flagging
  8. Dual-tier LLM explanation (template path)
  9. JSON schema compliance for PharmaGuardResponse
"""
import sys
import os
import ast
import pathlib

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'genomics-service-python'))
os.chdir(os.path.join(os.path.dirname(__file__), '..', 'genomics-service-python'))

PASS = "  [OK]  "
WARN = "  [WARN]"
FAIL = "  [FAIL]"

print("=" * 60)
print("  PharmaGuard v2 - Verification Suite")
print("=" * 60)

# ── 1. Syntax Check ───────────────────────────────────────────────────────────

print("\n[1] Python Syntax Check")
all_ok = True
for f in pathlib.Path('.').glob('*.py'):
    try:
        ast.parse(f.read_text(encoding='utf-8'))
        print(f"{PASS}: {f.name}")
    except SyntaxError as e:
        print(f"{FAIL}: {f.name} — {e}")
        all_ok = False


# ── 2. Import Check ───────────────────────────────────────────────────────────

print("\n[2] Module Import Check")

try:
    from models import (
        PharmaGuardResponse, ErrorResponse, ConsolidatedRiskReport,
        LLMGeneratedExplanation, QualityMetrics
    )
    print(f"{PASS}: models.py (ConsolidatedRiskReport, LLMGeneratedExplanation)")
except Exception as e:
    print(f"{FAIL}: models.py — {e}")

try:
    from vcf_parser import parse_vcf, validate_vcf_header, extract_diplotype_for_gene
    print(f"{PASS}: vcf_parser.py")
except Exception as e:
    print(f"{FAIL}: vcf_parser.py — {e}")

try:
    from risk_engine import RiskEngine, DRUG_GENE_MAP, SUPPORTED_DRUGS
    print(f"{PASS}: risk_engine.py (RiskEngine, assess_all_genes)")
except Exception as e:
    print(f"{FAIL}: risk_engine.py — {e}")

try:
    from llm_service import generate_explanation, build_explanation_prompt
    print(f"{PASS}: llm_service.py (dual-tier explanation)")
except Exception as e:
    print(f"{FAIL}: llm_service.py — {e}")

try:
    from groq_analyzer import groq_explain
    print(f"{PASS}: groq_analyzer.py (slim wrapper)")
except Exception as e:
    print(f"{FAIL}: groq_analyzer.py — {e}")


# ── 3. CSV Validation ─────────────────────────────────────────────────────────

print("\n[3] CSV Knowledge Base")
import pandas as pd
df = pd.read_csv('../data/pharmacogenomic_rules.csv')
print(f"  Rules: {len(df)}")
required_cols = [
    'gene','drug','diplotype','phenotype','risk_label',
    'severity','cpic_recommendation','alternative_drugs','evidence_level'
]
missing_cols = [c for c in required_cols if c not in df.columns]
if missing_cols:
    print(f"{FAIL}: Missing columns: {missing_cols}")
else:
    print(f"{PASS}: All 9 required columns present")
    print(f"  Genes: {sorted(df['gene'].unique())}")
    print(f"  Drugs: {sorted(df['drug'].unique())}")


# ── 4. Sample VCF Integrity ───────────────────────────────────────────────────

print("\n[4] Sample VCF Files")
for vcf_path in ['../sample_vcfs/sample1_cyp2d6_pm.vcf', '../sample_vcfs/sample2_dpyd_toxic.vcf']:
    if os.path.exists(vcf_path):
        content  = open(vcf_path, encoding='utf-8').read()
        ok_hdr   = content.startswith('##fileformat=VCF')
        has_chrom= '#CHROM' in content
        lines    = [l for l in content.split('\n') if l and not l.startswith('#')]
        tag = PASS if ok_hdr and has_chrom else FAIL
        print(f"{tag}: {os.path.basename(vcf_path)} "
              f"— header={ok_hdr}, #CHROM={has_chrom}, variants={len(lines)}")
    else:
        print(f"{WARN}: Missing: {vcf_path}")


# ── 5. Per-Drug Risk Engine Tests ─────────────────────────────────────────────

print("\n[5] Per-Drug Risk Engine (deterministic)")
engine = RiskEngine()
from vcf_parser import ParsedVariant, VCFParseResult


def quick_test(gene, star, rsid, gt, drug, expected_label, chrom="chr1", pos=100, qual=None):
    v = ParsedVariant(chromosome=chrom, position=pos, ref="C", alt="T",
                      genotype=gt, gene=gene, star_allele=star, rsid=rsid, qual=qual)
    r = VCFParseResult(patient_id="TEST")
    r.variants = [v]
    r.gene_variants = {gene: [v]}
    r.success = True
    result = engine.assess(r, drug)
    label  = result.get("risk_label", result.get("error", "?"))
    match  = result.get("match_type", "-")
    conf   = result.get("confidence_score", "-")
    novel  = result.get("novel_variants_count", 0)
    ambig  = result.get("ambiguity_flag", False)
    tag    = PASS if label == expected_label else WARN
    print(f"{tag}: {gene} {star}({gt}) + {drug}")
    print(f"        → label={label} (expected={expected_label}) | "
          f"match={match} | conf={conf} | novel={novel} | ambig={ambig}")


quick_test("CYP2D6",  "*4",  "rs3892097", "1/1", "CODEINE",      "Ineffective")
quick_test("CYP2C19", "*2",  "rs4244285", "1/1", "CLOPIDOGREL",  "Ineffective")
quick_test("CYP2C9",  "*3",  "rs1057910", "1/1", "WARFARIN",     "Toxic")
quick_test("SLCO1B1", "*5",  "rs4149056", "1/1", "SIMVASTATIN",  "Toxic")
quick_test("TPMT",    "*3A", "rs1142345", "0/1", "AZATHIOPRINE", "Adjust Dosage")
quick_test("DPYD",    "*2A", "rs3918290", "0/1", "FLUOROURACIL", "Toxic")
quick_test("CYP2D6",  "*1",  "rs1065852", "0/0", "CODEINE",      "Safe")


# ── 6. Dynamic Confidence Scoring ─────────────────────────────────────────────

print("\n[6] Dynamic Confidence Scoring")

# High QUAL vs low QUAL for same variant
from vcf_parser import ParsedVariant, VCFParseResult as VCFRes

def make_r(gene, star, rsid, gt, q=None):
    v = ParsedVariant(chromosome="chr1", position=100, ref="C", alt="T",
                      genotype=gt, gene=gene, star_allele=star, rsid=rsid, qual=q)
    r = VCFRes(patient_id="QTEST")
    r.variants = [v]; r.gene_variants = {gene: [v]}; r.success = True
    return r

a_hq = engine.assess(make_r("CYP2D6", "*4", "rs3892097", "1/1", q=80.0), "CODEINE")
a_lq = engine.assess(make_r("CYP2D6", "*4", "rs3892097", "1/1", q=5.0),  "CODEINE")
a_nq = engine.assess(make_r("CYP2D6", "*4", "rs3892097", "1/1"), "CODEINE")

tag = PASS if a_hq["confidence_score"] >= a_lq["confidence_score"] else WARN
print(f"{tag}: QUAL 80={a_hq['confidence_score']} >= QUAL 5={a_lq['confidence_score']} (no QUAL={a_nq['confidence_score']})")


# ── 7. Novel Variant Flagging ─────────────────────────────────────────────────

print("\n[7] Novel Variant Flagging")
v_novel = ParsedVariant(chromosome="chr22", position=99999, ref="A", alt="T",
                        genotype="0/1", gene="CYP2D6", star_allele="*99NOVEL", rsid="rs999NOVEL")
r_novel = VCFParseResult(patient_id="TEST_NOVEL")
r_novel.variants = [v_novel]
r_novel.gene_variants = {"CYP2D6": [v_novel]}
r_novel.success = True
a_novel = engine.assess(r_novel, "CODEINE")

for v in a_novel["detected_variants"]:
    tag = PASS if "is_novel" in v else FAIL
    print(f"{tag}: detected_variants carries is_novel field = {v.get('is_novel')}")
print(f"  novel_variants_count = {a_novel['novel_variants_count']}")


# ── 8. Consolidated Multi-Gene Report ─────────────────────────────────────────

print("\n[8] Consolidated Multi-Gene Report (assess_all_genes)")

# Build parse result with one real CYP2D6 variant + one DPYD variant
v1 = ParsedVariant(chromosome="chr22", position=42130692, ref="C", alt="T",
                   genotype="1/1", gene="CYP2D6", star_allele="*4", rsid="rs3892097")
v2 = ParsedVariant(chromosome="chr1", position=97915614, ref="C", alt="A",
                   genotype="0/1", gene="DPYD", star_allele="*2A", rsid="rs3918290")
r_multi = VCFParseResult(patient_id="MULTI_TEST")
r_multi.variants = [v1, v2]
r_multi.gene_variants = {"CYP2D6": [v1], "DPYD": [v2]}
r_multi.success = True

report = engine.assess_all_genes(r_multi)
gene_names = [g["gene"] for g in report["genes_assessed"]]
expected   = {"CYP2D6", "CYP2C19", "CYP2C9", "SLCO1B1", "TPMT", "DPYD"}

tag = PASS if set(gene_names) == expected else FAIL
print(f"{tag}: Consolidated report covers all 6 genes")
print(f"  overall_severity: {report['overall_severity']}")
print(f"  high_risk_drug_count: {report['high_risk_drug_count']}")
print(f"  safe_drug_count: {report['safe_drug_count']}")
print(f"  novel_variants_count: {report['novel_variants_count']}")
print(f"  vcf_parsing_success: {report['vcf_parsing_success']}")
for g in report["genes_assessed"]:
    print(f"  {g['gene']:10s}  diplotype={g['diplotype']:12s}  "
          f"phenotype={g['phenotype']:7s}  risk={g['risk_label']}")


# ── 9. Dual-Tier LLM Explanation (template path) ─────────────────────────────

print("\n[9] Dual-Tier LLM Explanation (template fallback)")
from llm_service import _template_explanation

variants = [{"rsid": "rs3892097", "chromosome": "chr22", "position": 42130692,
             "genotype": "1/1", "star_allele": "*4", "is_novel": False}]

expl = _template_explanation(
    gene="CYP2D6", diplotype="*4/*4", phenotype="PM",
    drug="CODEINE", risk_label="Ineffective", severity="high",
    detected_variants=variants
)

has_patient  = bool(expl.get("patient_summary"))
has_clinician= bool(expl.get("clinician_mechanism"))
has_legacy   = bool(expl.get("summary")) and bool(expl.get("mechanism"))

tag = PASS if has_patient and has_clinician and has_legacy else FAIL
print(f"{tag}: patient_summary={has_patient}, clinician_mechanism={has_clinician}, legacy_compat={has_legacy}")
print(f"  llm_confidence={expl.get('llm_confidence')}")
print(f"  variant_citations={expl.get('variant_citations')}")


# ── 10. JSON Schema Compliance ────────────────────────────────────────────────

print("\n[10] JSON Schema Compliance (PharmaGuardResponse)")
from datetime import datetime, timezone as tz

resp = PharmaGuardResponse(
    patient_id="TEST_001",
    drug="CODEINE",
    timestamp=datetime.now(tz.utc).isoformat(),
    risk_assessment={
        "risk_label": "Safe", "confidence_score": 0.92,
        "severity": "none", "match_type": "exact_diplotype"
    },
    pharmacogenomic_profile={
        "primary_gene": "CYP2D6", "diplotype": "*1/*1",
        "phenotype": "NM", "detected_variants": [],
        "novel_variants_detected": False, "ambiguity_flag": False
    },
    clinical_recommendation={
        "cpic_guideline": "CPIC Guideline for CODEINE and CYP2D6",
        "dose_adjustment": "Standard dose codeine. No adjustment needed.",
        "alternative_drugs": [], "evidence_level": "A"
    },
    llm_generated_explanation={
        "patient_summary": "Test summary.",
        "clinician_mechanism": "Test mechanism.",
        "variant_citations": [],
        "summary": "Test summary.", "mechanism": "Test mechanism."
    },
    quality_metrics={
        "vcf_parsing_success": True, "guideline_version": "CPIC v2.0",
        "llm_confidence": 0.88, "diplotype_match_quality": "exact",
        "novel_variants_flagged": 0, "vcf_qual_score": None
    }
)

schema_keys = list(resp.model_dump().keys())
expected_keys = [
    "patient_id", "drug", "timestamp", "risk_assessment",
    "pharmacogenomic_profile", "clinical_recommendation",
    "llm_generated_explanation", "quality_metrics"
]
tag = PASS if schema_keys == expected_keys else WARN
print(f"{tag}: Schema has all 8 top-level fields in correct order")
if schema_keys != expected_keys:
    print(f"  Got:      {schema_keys}")
    print(f"  Expected: {expected_keys}")

print("\n" + "=" * 60)
print("  Verification Complete")
print("=" * 60)
