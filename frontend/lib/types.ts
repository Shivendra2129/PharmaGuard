/**
 * TypeScript types for PharmaGuard API v2 responses.
 * Matches the strict JSON schema from models.py exactly.
 * Includes dual-tier LLM explanation, dynamic quality metrics,
 * novel variant flagging, and consolidated multi-gene report types.
 */

// ── Core sub-types ────────────────────────────────────────────────────────────

export interface DetectedVariant {
  rsid: string;
  chromosome: string;
  position: number;
  genotype?: string;        // e.g. "0/1", "1/1"
  star_allele?: string;     // e.g. "*4"
  is_novel?: boolean;       // True if star allele not in CPIC CSV
}

export interface RiskAssessment {
  risk_label: 'Safe' | 'Adjust Dosage' | 'Toxic' | 'Ineffective' | 'Unknown';
  confidence_score: number;
  severity: 'none' | 'low' | 'moderate' | 'high' | 'critical';
  match_type?: 'exact_diplotype' | 'phenotype' | 'rsid_special' | 'inferred' | 'fallback';
}

export interface PharmacogenomicProfile {
  primary_gene: string;
  diplotype: string;
  phenotype: 'PM' | 'IM' | 'NM' | 'RM' | 'URM' | 'Unknown';
  detected_variants: DetectedVariant[];
  novel_variants_detected?: boolean;
  ambiguity_flag?: boolean;
}

export interface ClinicalRecommendation {
  cpic_guideline: string;
  dose_adjustment: string;
  alternative_drugs: string[];
  evidence_level?: string;   // A | B | C | D
}

export interface LLMGeneratedExplanation {
  // v2 dual-tier fields
  patient_summary?: string;
  clinician_mechanism?: string;
  // Legacy backward-compat fields
  summary?: string;
  mechanism?: string;
  variant_citations: string[];
}

export interface QualityMetrics {
  vcf_parsing_success: boolean;
  guideline_version: string;
  llm_confidence: number;
  diplotype_match_quality?: 'exact' | 'inferred' | 'none' | 'unknown';
  novel_variants_flagged?: number;
  vcf_qual_score?: number | null;
}

export interface PharmaGuardResult {
  patient_id: string;
  drug: string;
  timestamp: string;
  risk_assessment: RiskAssessment;
  pharmacogenomic_profile: PharmacogenomicProfile;
  clinical_recommendation: ClinicalRecommendation;
  llm_generated_explanation: LLMGeneratedExplanation;
  quality_metrics: QualityMetrics;
  // Error fields (present only on failure)
  error?: string;
  detail?: string;
}

export interface AnalysisResponse {
  success: boolean;
  request_id: string;
  results: PharmaGuardResult[];
  total_drugs_analyzed: number;
  timestamp: string;
}

export interface AnalysisError {
  error: string;
  detail: string;
  patient_id?: string;
  request_id?: string;
  timestamp: string;
}

// ── Consolidated Multi-Gene Report ────────────────────────────────────────────

export interface GeneRiskEntry {
  gene: string;
  diplotype: string;
  phenotype: string;
  risk_drugs: string[];
  risk_label: string;
  severity: string;
  ambiguity_flag: boolean;
}

export interface ConsolidatedRiskReport {
  patient_id: string;
  timestamp: string;
  overall_severity: 'none' | 'low' | 'moderate' | 'high' | 'critical';
  genes_assessed: GeneRiskEntry[];
  high_risk_drug_count: number;
  safe_drug_count: number;
  novel_variants_count: number;
  vcf_parsing_success: boolean;
  warnings: string[];
}

// ── Utility types ─────────────────────────────────────────────────────────────

export type RiskLabel = 'Safe' | 'Adjust Dosage' | 'Toxic' | 'Ineffective' | 'Unknown';
export type Severity  = 'none' | 'low' | 'moderate' | 'high' | 'critical';
export type Phenotype = 'PM' | 'IM' | 'NM' | 'RM' | 'URM' | 'Unknown';
export type MatchType = 'exact_diplotype' | 'phenotype' | 'rsid_special' | 'inferred' | 'fallback';
