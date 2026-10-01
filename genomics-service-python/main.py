"""
PharmaGuard - FastAPI Genomics Microservice
Main application entry point.

Pipeline (strictly enforced):
  1. VCF upload  →  vcf_parser.py  →  ParsedVariant list
  2. ParsedVariant  →  risk_engine.RiskEngine.assess()  →  deterministic CPIC risk
  3. Deterministic risk  →  llm_service.generate_explanation()  →  dual-tier LLM explanation
  4. Assemble PharmaGuardResponse  →  return JSON

The LLM is NEVER used to decide risk; only to explain a pre-computed result.
"""
import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

import sys
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    try: sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass

# Load environment
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from models import (
    PharmaGuardResponse, ErrorResponse,
    DetectedVariant, RiskAssessment, PharmacogenomicProfile,
    ClinicalRecommendation, LLMGeneratedExplanation, QualityMetrics,
    ConsolidatedRiskReport
)
from vcf_parser import parse_vcf, validate_vcf_header, SUPPORTED_GENES
from risk_engine import RiskEngine, DRUG_GENE_MAP, SUPPORTED_DRUGS
from llm_service import generate_explanation
from groq_analyzer import groq_explain

app = FastAPI(
    title="PharmaGuard Genomics API",
    description=(
        "Pharmacogenomic Risk Prediction Microservice — "
        "Deterministic CPIC rules engine + Dual-tier LLM explainability"
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# ── CORS ──────────────────────────────────────────────────────────────────────
cors_origins = os.getenv(
    "CORS_ORIGINS", "http://localhost:3000,http://localhost:3001"
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Initialise Risk Engine (loads CSV once at startup) ────────────────────────
risk_engine = RiskEngine()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _error(error: str, detail: str, patient_id: str = None,
           drug: str = None, status_code: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error":      error,
            "detail":     detail,
            "patient_id": patient_id,
            "drug":       drug,
            "timestamp":  _now()
        }
    )


async def _read_vcf(vcf_file: UploadFile) -> tuple[str, JSONResponse | None]:
    """Read uploaded VCF and return (vcf_content, error_response_or_None)."""
    try:
        content_bytes = await vcf_file.read()
        try:
            return content_bytes.decode('utf-8'), None
        except UnicodeDecodeError:
            try:
                return content_bytes.decode('latin-1'), None
            except Exception:
                return "", _error(
                    "invalid_file_encoding",
                    "VCF file must be UTF-8 or ASCII encoded",
                    status_code=422
                )
    except Exception as e:
        return "", _error(
            "file_read_error",
            f"Could not read uploaded file: {str(e)}",
            status_code=422
        )


# ── Health Check ──────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    return {
        "status":    "healthy",
        "service":   "PharmaGuard Genomics API",
        "version":   "2.0.0",
        "timestamp": _now(),
        "pipeline":  "deterministic_cpic_rules + dual_tier_llm_explanation"
    }


# ── Per-Drug Analysis ─────────────────────────────────────────────────────────

@app.post("/analyze", response_model=List[PharmaGuardResponse])
@app.post("/api/analyze", response_model=List[PharmaGuardResponse])
async def analyze_vcf(
    vcf_file: UploadFile = File(..., description="VCF v4.2 file"),
    drugs: str = Form(..., description="Comma-separated drug names"),
    patient_id: Optional[str] = Form(None, description="Patient identifier")
):
    """
    Analyze a VCF file for pharmacogenomic risk for one or more drugs.

    Pipeline per drug:
      VCF parse → diplotype extraction → CPIC risk (deterministic) → LLM explanation
    Returns list of PharmaGuardResponse objects (one per drug).
    """
    # ── Patient ID
    if not patient_id or patient_id.strip() == "":
        patient_id = f"PATIENT_{uuid.uuid4().hex[:6].upper()}"
    else:
        patient_id = patient_id.strip()

    # ── Drug list
    drug_list = [d.strip().upper() for d in drugs.split(',') if d.strip()]
    if not drug_list:
        return _error("invalid_drugs", "No valid drug names provided",
                      patient_id=patient_id, status_code=400)

    # ── Read VCF
    vcf_content, err = await _read_vcf(vcf_file)
    if err:
        return err

    # ── Validate VCF header
    valid, msg = validate_vcf_header(vcf_content)
    if not valid:
        return _error("invalid_vcf_format", msg,
                      patient_id=patient_id, status_code=422)

    # ── Parse VCF (cyvcf2 or manual fallback)
    parse_result = parse_vcf(vcf_content, patient_id)

    timestamp = _now()
    results   = []

    for drug in drug_list:
        drug_upper = drug.upper()
        print(f"[Analyze] {drug_upper}: running deterministic CPIC risk engine…")

        # ── Step 1: Deterministic CPIC Risk Assessment
        assessment = risk_engine.assess(parse_result, drug_upper)

        if "error" in assessment and "risk_label" not in assessment:
            results.append({
                "patient_id": patient_id,
                "drug":       drug_upper,
                "timestamp":  timestamp,
                "error":      assessment["error"],
                "detail":     assessment.get("detail", "Risk engine returned an error")
            })
            continue

        # ── Step 2: LLM Dual-Tier Explanation (explains, never decides)
        print(f"[Analyze] {drug_upper}: generating LLM explanation (match_type={assessment['match_type']})…")
        explanation = groq_explain(
            gene=assessment["primary_gene"],
            diplotype=assessment["diplotype"],
            phenotype=assessment["phenotype"],
            drug=drug_upper,
            risk_label=assessment["risk_label"],
            severity=assessment["severity"],
            detected_variants=assessment["detected_variants"],
            cpic_recommendation=assessment["cpic_recommendation"],
            match_type=assessment["match_type"]
        )

        # ── Step 3: Assemble PharmaGuardResponse
        try:
            response = PharmaGuardResponse(
                patient_id=patient_id,
                drug=drug_upper,
                timestamp=timestamp,
                risk_assessment=RiskAssessment(
                    risk_label=assessment["risk_label"],
                    confidence_score=assessment["confidence_score"],
                    severity=assessment["severity"],
                    match_type=assessment["match_type"]
                ),
                pharmacogenomic_profile=PharmacogenomicProfile(
                    primary_gene=assessment["primary_gene"],
                    diplotype=assessment["diplotype"],
                    phenotype=assessment["phenotype"],
                    novel_variants_detected=assessment["novel_variants_count"] > 0,
                    ambiguity_flag=assessment["ambiguity_flag"],
                    detected_variants=[
                        DetectedVariant(
                            rsid=v.get("rsid", ""),
                            chromosome=v.get("chromosome", ""),
                            position=int(v.get("position", 0)),
                            genotype=v.get("genotype"),
                            star_allele=v.get("star_allele"),
                            is_novel=v.get("is_novel", False)
                        )
                        for v in assessment["detected_variants"]
                    ]
                ),
                clinical_recommendation=ClinicalRecommendation(
                    cpic_guideline=f"CPIC Guideline for {drug_upper} and {assessment['primary_gene']}",
                    dose_adjustment=assessment["cpic_recommendation"],
                    alternative_drugs=assessment["alternative_drugs"],
                    evidence_level=assessment["evidence_level"]
                ),
                llm_generated_explanation=LLMGeneratedExplanation(
                    patient_summary=explanation.get("patient_summary", ""),
                    clinician_mechanism=explanation.get("clinician_mechanism", ""),
                    variant_citations=explanation.get("variant_citations", []),
                    # Legacy compat
                    summary=explanation.get("patient_summary", ""),
                    mechanism=explanation.get("clinician_mechanism", "")
                ),
                quality_metrics=QualityMetrics(
                    vcf_parsing_success=assessment["vcf_parsing_success"],
                    guideline_version="CPIC v2.0",
                    llm_confidence=float(explanation.get("llm_confidence", 0.75)),
                    diplotype_match_quality=assessment["diplotype_match_quality"],
                    novel_variants_flagged=assessment["novel_variants_count"],
                    vcf_qual_score=assessment.get("vcf_qual_score")
                )
            )
            results.append(response.model_dump())
            print(f"[Analyze] [OK] {drug_upper}: risk={assessment['risk_label']} "
                  f"confidence={assessment['confidence_score']} match={assessment['match_type']}")

        except Exception as e:
            print(f"[Analyze] Schema assembly error for {drug_upper}: {e}")
            results.append({
                "patient_id": patient_id,
                "drug":       drug_upper,
                "timestamp":  timestamp,
                "error":      "schema_error",
                "detail":     str(e)
            })

    return JSONResponse(content=results)


# ── Consolidated Multi-Gene Report ────────────────────────────────────────────

@app.post("/analyze/consolidated")
@app.post("/api/analyze/consolidated")
async def analyze_vcf_consolidated(
    vcf_file: UploadFile = File(..., description="VCF v4.2 file"),
    patient_id: Optional[str] = Form(None, description="Patient identifier")
):
    """
    Produce a unified multi-gene patient risk report from a single VCF upload.
    Assesses all 6 supported genes simultaneously without requiring drug selection.
    Returns a ConsolidatedRiskReport.
    """
    if not patient_id or patient_id.strip() == "":
        patient_id = f"PATIENT_{uuid.uuid4().hex[:6].upper()}"
    else:
        patient_id = patient_id.strip()

    vcf_content, err = await _read_vcf(vcf_file)
    if err:
        return err

    valid, msg = validate_vcf_header(vcf_content)
    if not valid:
        return _error("invalid_vcf_format", msg, patient_id=patient_id, status_code=422)

    parse_result = parse_vcf(vcf_content, patient_id)

    print(f"[Consolidated] {patient_id}: running multi-gene assessment…")
    report = risk_engine.assess_all_genes(parse_result)

    print(
        f"[Consolidated] [OK] {patient_id}: "
        f"overall_severity={report['overall_severity']} "
        f"high_risk_drugs={report['high_risk_drug_count']}"
    )
    return JSONResponse(content=report)


# ── Reference Endpoints ───────────────────────────────────────────────────────

@app.get("/supported-drugs")
async def get_supported_drugs():
    """Return list of supported drugs and their associated genes."""
    return {
        "supported_drugs": sorted(list(SUPPORTED_DRUGS)),
        "drug_gene_map":   DRUG_GENE_MAP
    }


@app.get("/supported-genes")
async def get_supported_genes():
    """Return list of supported pharmacogenomic genes."""
    return {
        "supported_genes": sorted(list(SUPPORTED_GENES))
    }


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    host    = os.getenv("PYTHON_HOST", "0.0.0.0")
    port    = int(os.getenv("PORT", os.getenv("PYTHON_PORT", "8000")))
    is_prod = os.getenv("PYTHON_ENV", "development") == "production"
    uvicorn.run("main:app", host=host, port=port, reload=not is_prod)
