"""
Pydantic models for strict JSON schema enforcement.
Supports dual-tier LLM explanation (patient summary + clinician mechanism),
dynamic quality confidence metrics, novel variant flagging, and
consolidated multi-gene patient risk reporting.
"""
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from datetime import datetime


class DetectedVariant(BaseModel):
    rsid: str
    chromosome: str
    position: int
    genotype: Optional[str] = None       # e.g. "0/1", "1/1"
    star_allele: Optional[str] = None    # e.g. "*4"
    is_novel: Optional[bool] = False     # True if not catalogued in CPIC rules


class RiskAssessment(BaseModel):
    risk_label: str              # Safe | Adjust Dosage | Toxic | Ineffective | Unknown
    confidence_score: float      # 0.0 – 1.0, computed dynamically
    severity: str                # none | low | moderate | high | critical
    match_type: Optional[str] = None  # "exact_diplotype" | "phenotype" | "rsid_special" | "inferred" | "fallback"


class PharmacogenomicProfile(BaseModel):
    primary_gene: str
    diplotype: str
    phenotype: str               # PM | IM | NM | RM | URM | Unknown
    detected_variants: List[DetectedVariant]
    novel_variants_detected: Optional[bool] = False
    ambiguity_flag: Optional[bool] = False  # True when diplotype inferred, not exact match


class ClinicalRecommendation(BaseModel):
    cpic_guideline: str
    dose_adjustment: str
    alternative_drugs: List[str]
    evidence_level: Optional[str] = "B"   # A | B | C | D


class LLMGeneratedExplanation(BaseModel):
    # Patient-facing plain-language summary (no jargon)
    patient_summary: str
    # Clinician-facing detailed mechanism with enzyme kinetics, CPIC refs
    clinician_mechanism: str
    # rsIDs explicitly cited in the explanation
    variant_citations: List[str]
    # Legacy field kept for schema backward compat
    summary: Optional[str] = ""
    mechanism: Optional[str] = ""


class QualityMetrics(BaseModel):
    vcf_parsing_success: bool
    guideline_version: str
    llm_confidence: float
    # Dynamic quality flags
    diplotype_match_quality: Optional[str] = "unknown"   # "exact" | "inferred" | "none"
    novel_variants_flagged: Optional[int] = 0
    vcf_qual_score: Optional[float] = None               # Average QUAL from VCF variants


class PharmaGuardResponse(BaseModel):
    patient_id: str
    drug: str
    timestamp: str
    risk_assessment: RiskAssessment
    pharmacogenomic_profile: PharmacogenomicProfile
    clinical_recommendation: ClinicalRecommendation
    llm_generated_explanation: LLMGeneratedExplanation
    quality_metrics: QualityMetrics


# ── Consolidated Multi-Gene Report ───────────────────────────────────────────

class GeneRiskEntry(BaseModel):
    """Single gene's pharmacogenomic status within a consolidated report."""
    gene: str
    diplotype: str
    phenotype: str
    risk_drugs: List[str]           # Drugs affected by this gene's phenotype
    risk_label: str                 # Highest risk label across all affected drugs
    severity: str
    ambiguity_flag: bool = False


class ConsolidatedRiskReport(BaseModel):
    """
    Unified multi-gene patient risk profile.
    Covers all 6 supported genes across a single VCF upload.
    """
    patient_id: str
    timestamp: str
    overall_severity: str           # Worst-case severity across all genes
    genes_assessed: List[GeneRiskEntry]
    high_risk_drug_count: int
    safe_drug_count: int
    novel_variants_count: int
    vcf_parsing_success: bool
    warnings: List[str]


class ErrorResponse(BaseModel):
    error: str
    detail: str
    patient_id: Optional[str] = None
    drug: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class AnalysisRequest(BaseModel):
    patient_id: str
    drugs: List[str]
