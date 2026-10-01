"""
Deterministic CPIC-aligned risk engine.
Loads pharmacogenomic_rules.csv and applies rule-based logic.

Key responsibilities:
  - assess()           : per-drug diplotype → phenotype → CPIC risk lookup
  - dynamic_confidence(): compute confidence score from match quality + VCF metrics
  - assess_all_genes() : consolidated multi-gene patient risk profile
  LLM does NOT make risk decisions — it only explains them.
"""
import os
import pandas as pd
from typing import Dict, List, Optional, Tuple

from vcf_parser import ParsedVariant, VCFParseResult, extract_diplotype_for_gene

# Path to knowledge base
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
CSV_PATH = os.path.join(DATA_DIR, 'pharmacogenomic_rules.csv')

SUPPORTED_DRUGS = {
    "CODEINE", "WARFARIN", "CLOPIDOGREL",
    "SIMVASTATIN", "AZATHIOPRINE", "FLUOROURACIL"
}

DRUG_GENE_MAP = {
    "CODEINE":      "CYP2D6",
    "WARFARIN":     "CYP2C9",
    "CLOPIDOGREL":  "CYP2C19",
    "SIMVASTATIN":  "SLCO1B1",
    "AZATHIOPRINE": "TPMT",
    "FLUOROURACIL": "DPYD"
}

# Inverse map: gene → list of drugs it governs
GENE_DRUG_MAP: Dict[str, List[str]] = {}
for _drug, _gene in DRUG_GENE_MAP.items():
    GENE_DRUG_MAP.setdefault(_gene, []).append(_drug)

# Severity ordering used to compute worst-case across genes
SEVERITY_ORDER = {"none": 0, "low": 1, "moderate": 2, "high": 3, "critical": 4}

# Base confidence by risk label (deterministic rule match)
_BASE_CONFIDENCE = {
    "Toxic":         0.93,
    "Ineffective":   0.88,
    "Adjust Dosage": 0.80,
    "Safe":          0.92,
    "Unknown":       0.40
}

# Confidence modifier by match type (how precise the rule-match was)
_MATCH_MODIFIER = {
    "exact_diplotype": 1.00,
    "phenotype":       0.90,
    "rsid_special":    0.95,
    "inferred":        0.75,
    "fallback":        0.50
}


class RiskEngine:
    """Loads CSV rules and performs deterministic pharmacogenomic risk assessment."""

    def __init__(self, csv_path: str = CSV_PATH):
        self.csv_path = csv_path
        self._rules_df = None
        self._load_rules()

    # ── Startup ────────────────────────────────────────────────────────────────

    def _load_rules(self):
        """Load and validate the CSV knowledge base."""
        try:
            self._rules_df = pd.read_csv(self.csv_path)
            required_cols = [
                'gene', 'drug', 'diplotype', 'phenotype',
                'risk_label', 'severity', 'cpic_recommendation',
                'alternative_drugs', 'evidence_level'
            ]
            missing = [c for c in required_cols if c not in self._rules_df.columns]
            if missing:
                raise ValueError(f"CSV missing columns: {missing}")
            # Normalise for case-insensitive matching
            self._rules_df['drug_upper'] = self._rules_df['drug'].str.upper()
            self._rules_df['gene_upper'] = self._rules_df['gene'].str.upper()
            print(f"[RiskEngine] Loaded {len(self._rules_df)} rules from {self.csv_path}")
        except Exception as e:
            print(f"[RiskEngine] WARNING: Could not load CSV: {e}")
            self._rules_df = pd.DataFrame()

    # ── Phenotype Inference ────────────────────────────────────────────────────

    def _infer_phenotype(self, gene: str, diplotype: str,
                         gene_variants: List[ParsedVariant]) -> str:
        """
        Infer metabolizer phenotype.
        Priority: exact diplotype match in CSV > genotype-based inference.
        """
        if self._rules_df.empty:
            return "Unknown"

        gene_upper = gene.upper()
        mask = (
            (self._rules_df['gene_upper'] == gene_upper) &
            (self._rules_df['diplotype'] == diplotype)
        )
        matches = self._rules_df[mask]
        if not matches.empty:
            return str(matches.iloc[0]['phenotype'])

        return self._infer_phenotype_from_alleles(gene, gene_variants)

    def _infer_phenotype_from_alleles(self, gene: str,
                                      variants: List[ParsedVariant]) -> str:
        """Infer metabolizer phenotype from observed alleles and genotypes."""
        if not variants:
            return "Unknown"

        hom_alt = [v for v in variants if v.genotype in ("1/1", "1|1")]
        het     = [v for v in variants if v.genotype in ("0/1", "1/0", "0|1", "1|0")]

        # No-function alleles (loss-of-function star alleles)
        nof_stars = {
            "*3", "*4", "*5", "*6", "*7", "*8", "*11", "*12", "*13", "*14",
            "*2A", "*2", "*3A", "*3B", "*3C"
        }
        all_stars = {v.star_allele for v in variants}
        has_nof   = bool(all_stars & nof_stars)

        if hom_alt and has_nof:
            return "PM"
        if het and has_nof:
            return "IM"

        # DPYD special case
        if gene.upper() == "DPYD":
            dpyd_toxic_rs = {"rs3918290", "rs55886062", "rs67376798"}
            for v in variants:
                if v.rsid in dpyd_toxic_rs and v.genotype in ("0/1", "1/0", "0|1", "1|0"):
                    return "IM"
                if v.rsid in dpyd_toxic_rs and v.genotype in ("1/1", "1|1"):
                    return "PM"

        # URM detection (gene duplication)
        for v in variants:
            if "xN" in v.star_allele or "x2" in v.star_allele:
                return "URM"

        # All ref → NM
        all_ref = [v for v in variants if v.genotype in ("0/0", "0|0")]
        if len(all_ref) == len(variants):
            return "NM"

        return "NM"

    # ── Risk Lookup ────────────────────────────────────────────────────────────

    def _lookup_risk(self, gene: str, drug: str, diplotype: str, phenotype: str,
                     variants: List[ParsedVariant]) -> Tuple[Dict, str]:
        """
        Lookup risk using deterministic rules.
        Priority: exact diplotype match > phenotype match > rsID special > fallback.
        Returns (risk_dict, match_type).
        """
        if self._rules_df.empty:
            return self._fallback_rule(gene, drug, diplotype, phenotype), "fallback"

        gene_upper = gene.upper()
        drug_upper = drug.upper()

        # 1. Exact diplotype match
        mask = (
            (self._rules_df['gene_upper'] == gene_upper) &
            (self._rules_df['drug_upper'] == drug_upper) &
            (self._rules_df['diplotype'] == diplotype)
        )
        matches = self._rules_df[mask]
        if not matches.empty:
            return self._row_to_risk(matches.iloc[0], "A"), "exact_diplotype"

        # 2. Phenotype match
        mask2 = (
            (self._rules_df['gene_upper'] == gene_upper) &
            (self._rules_df['drug_upper'] == drug_upper) &
            (self._rules_df['phenotype'] == phenotype)
        )
        matches2 = self._rules_df[mask2]
        if not matches2.empty:
            return self._row_to_risk(matches2.iloc[0], "B"), "phenotype"

        # 3. DPYD rsID special case
        if gene.upper() == "DPYD" and drug_upper == "FLUOROURACIL":
            dpyd_toxic_rs = {"rs3918290", "rs55886062", "rs55939643"}
            for v in variants:
                if v.rsid in dpyd_toxic_rs and v.genotype not in ("0/0", "0|0"):
                    pheno = "PM" if v.genotype in ("1/1", "1|1") else "IM"
                    mask3 = (
                        (self._rules_df['gene_upper'] == "DPYD") &
                        (self._rules_df['drug_upper'] == "FLUOROURACIL") &
                        (self._rules_df['phenotype'] == pheno)
                    )
                    m3 = self._rules_df[mask3]
                    if not m3.empty:
                        return self._row_to_risk(m3.iloc[0], "A"), "rsid_special"

        # 4. Unknown / fallback entry in CSV
        mask4 = (
            (self._rules_df['gene_upper'] == gene_upper) &
            (self._rules_df['drug_upper'] == drug_upper) &
            (self._rules_df['phenotype'] == "Unknown")
        )
        matches4 = self._rules_df[mask4]
        if not matches4.empty:
            return self._row_to_risk(matches4.iloc[0], "C"), "inferred"

        return self._fallback_rule(gene, drug, diplotype, phenotype), "fallback"

    def _row_to_risk(self, row, evidence_override: Optional[str] = None) -> Dict:
        """Convert a CSV row to a risk dictionary."""
        alts_raw = str(row.get('alternative_drugs', 'none'))
        if alts_raw.lower() in ('none', 'nan', ''):
            alternatives = []
        else:
            alternatives = [
                a.strip() for a in alts_raw.split('|')
                if a.strip() and a.strip().lower() != 'none'
            ]

        return {
            "risk_label":         str(row['risk_label']),
            "severity":           str(row['severity']),
            "cpic_recommendation": str(row['cpic_recommendation']),
            "alternative_drugs":  alternatives,
            "phenotype":          str(row['phenotype']),
            "evidence_level":     str(evidence_override or row.get('evidence_level', 'B'))
        }

    def _fallback_rule(self, gene: str, drug: str,
                       diplotype: str, phenotype: str) -> Dict:
        """Default fallback when no rule is matched."""
        return {
            "risk_label":         "Unknown",
            "severity":           "none",
            "cpic_recommendation": f"No CPIC guideline data available for {gene}/{drug}.",
            "alternative_drugs":  [],
            "phenotype":          phenotype,
            "evidence_level":     "D"
        }

    # ── Dynamic Confidence Scoring ─────────────────────────────────────────────

    def _compute_confidence(self, risk_label: str, match_type: str,
                            gene_variants: List[ParsedVariant],
                            vcf_success: bool) -> float:
        """
        Compute a dynamic confidence score based on:
          - Base confidence from risk label
          - Match quality modifier (exact vs inferred)
          - VCF variant quality (QUAL field)
          - Zygosity clarity (homozygous is more certain than heterozygous)
          - Whether parsing succeeded and variants were found
        """
        base  = _BASE_CONFIDENCE.get(risk_label, 0.5)
        mod   = _MATCH_MODIFIER.get(match_type, 0.6)
        score = base * mod

        if not vcf_success or not gene_variants:
            score *= 0.5
            return round(min(score, 1.0), 2)

        # Zygosity boost: homozygous calls are higher certainty
        hom_count = sum(1 for v in gene_variants if v.genotype in ("1/1", "1|1", "0/0", "0|0"))
        het_count  = len(gene_variants) - hom_count
        if hom_count > 0 and het_count == 0:
            score = min(score * 1.05, 0.99)  # All-homozygous: slight boost
        elif het_count > 0 and hom_count == 0:
            score = score * 0.95             # All-heterozygous: slight penalty

        # VCF QUAL score influence (only if available)
        qual_values = [v.qual for v in gene_variants if v.qual is not None]
        if qual_values:
            avg_qual = sum(qual_values) / len(qual_values)
            if avg_qual < 20:
                score *= 0.80   # Low-quality calls reduce confidence
            elif avg_qual >= 50:
                score = min(score * 1.03, 0.99)

        return round(min(score, 0.99), 2)

    # ── Novel Variant Detection ────────────────────────────────────────────────

    def _flag_novel_variants(self, gene: str, drug: str,
                             variants: List[ParsedVariant]) -> List[ParsedVariant]:
        """
        Mark variants as novel if their star allele doesn't appear
        anywhere in the CPIC CSV rules for this gene/drug pair.
        """
        if self._rules_df.empty or not variants:
            return variants

        gene_upper = gene.upper()
        drug_upper = drug.upper()

        # Gather all known diplotype tokens for this gene+drug from CSV
        gene_drug_mask = (
            (self._rules_df['gene_upper'] == gene_upper) &
            (self._rules_df['drug_upper'] == drug_upper)
        )
        known_diplotypes = self._rules_df[gene_drug_mask]['diplotype'].dropna().tolist()

        # Flatten diplotypes into individual star alleles (e.g. "*4/*4" → {"*4"})
        known_stars: set = set()
        for dip in known_diplotypes:
            for part in str(dip).split('/'):
                known_stars.add(part.strip())

        for v in variants:
            if v.star_allele and v.star_allele not in known_stars and v.star_allele != "*1":
                v.is_novel = True

        return variants

    # ── Per-Drug Assessment ────────────────────────────────────────────────────

    def assess(self, parse_result: VCFParseResult, drug: str) -> Dict:
        """
        Perform full pharmacogenomic risk assessment for one drug.
        Returns structured dict matching the PharmaGuardResponse schema.
        """
        drug_upper = drug.upper().strip()

        if drug_upper not in SUPPORTED_DRUGS:
            return {
                "error":  "unsupported_drug",
                "detail": (
                    f"Drug '{drug}' is not supported. "
                    f"Supported: {', '.join(sorted(SUPPORTED_DRUGS))}"
                ),
                "drug": drug
            }

        primary_gene  = DRUG_GENE_MAP[drug_upper]
        gene_variants = parse_result.gene_variants.get(primary_gene, [])

        # Mark novel/uncatalogued variants
        gene_variants = self._flag_novel_variants(primary_gene, drug_upper, gene_variants)

        # Extract diplotype
        diplotype, _alleles = extract_diplotype_for_gene(gene_variants)

        # Infer phenotype
        phenotype = self._infer_phenotype(primary_gene, diplotype, gene_variants)

        # Lookup risk deterministically
        risk_data, match_type = self._lookup_risk(
            primary_gene, drug_upper, diplotype, phenotype, gene_variants
        )

        # Build detected variants list with enriched fields
        seen_rsids: set = set()
        detected_variants = []
        for v in gene_variants:
            if v.rsid not in seen_rsids:
                detected_variants.append({
                    "rsid":        v.rsid,
                    "chromosome":  v.chromosome,
                    "position":    v.position,
                    "genotype":    v.genotype,
                    "star_allele": v.star_allele,
                    "is_novel":    getattr(v, 'is_novel', False)
                })
                seen_rsids.add(v.rsid)

        novel_count = sum(1 for v in gene_variants if getattr(v, 'is_novel', False))

        # Compute dynamic confidence
        risk_label = risk_data.get("risk_label", "Unknown")
        confidence = self._compute_confidence(
            risk_label, match_type, gene_variants,
            parse_result.success and bool(gene_variants)
        )

        # Average VCF QUAL for quality_metrics
        qual_values = [v.qual for v in gene_variants if v.qual is not None]
        avg_qual = round(sum(qual_values) / len(qual_values), 1) if qual_values else None

        diplotype_match_quality = {
            "exact_diplotype": "exact",
            "phenotype":       "inferred",
            "rsid_special":    "exact",
            "inferred":        "inferred",
            "fallback":        "none"
        }.get(match_type, "inferred")

        return {
            "primary_gene":       primary_gene,
            "diplotype":          diplotype,
            "phenotype":          risk_data.get("phenotype", phenotype),
            "risk_label":         risk_label,
            "severity":           risk_data.get("severity", "none"),
            "confidence_score":   confidence,
            "match_type":         match_type,
            "cpic_recommendation": risk_data.get("cpic_recommendation", ""),
            "alternative_drugs":  risk_data.get("alternative_drugs", []),
            "detected_variants":  detected_variants,
            "evidence_level":     risk_data.get("evidence_level", "B"),
            "vcf_parsing_success": parse_result.success and len(parse_result.variants) > 0,
            "novel_variants_count": novel_count,
            "ambiguity_flag":     match_type in ("inferred", "fallback"),
            "diplotype_match_quality": diplotype_match_quality,
            "vcf_qual_score":     avg_qual,
        }

    # ── Consolidated Multi-Gene Assessment ────────────────────────────────────

    def assess_all_genes(self, parse_result: VCFParseResult) -> Dict:
        """
        Produce a consolidated multi-gene patient risk profile.
        Assesses all 6 supported genes/drug pairs from a single VCF result.

        Returns a dict matching the ConsolidatedRiskReport schema.
        """
        from datetime import datetime, timezone
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        genes_assessed = []
        high_risk_drug_count = 0
        safe_drug_count = 0
        total_novel_variants = 0
        worst_severity = "none"
        warnings = list(parse_result.warnings)

        for gene, drug_list in GENE_DRUG_MAP.items():
            gene_variants = parse_result.gene_variants.get(gene, [])

            # Flag novel variants for this gene across its drugs
            for drug in drug_list:
                gene_variants = self._flag_novel_variants(gene, drug, gene_variants)

            novel_count = sum(1 for v in gene_variants if getattr(v, 'is_novel', False))
            total_novel_variants += novel_count

            if not gene_variants:
                # Gene not present in VCF — report as no data
                warnings.append(
                    f"No variants detected for {gene}. "
                    f"Gene may be absent from VCF or use unsupported INFO tags."
                )
                genes_assessed.append({
                    "gene":          gene,
                    "diplotype":     "unknown",
                    "phenotype":     "Unknown",
                    "risk_drugs":    drug_list,
                    "risk_label":    "Unknown",
                    "severity":      "none",
                    "ambiguity_flag": True
                })
                continue

            diplotype, _ = extract_diplotype_for_gene(gene_variants)
            phenotype    = self._infer_phenotype(gene, diplotype, gene_variants)

            # Determine highest risk across all drugs for this gene
            gene_worst_risk = "Safe"
            gene_worst_sev  = "none"
            ambiguous       = False

            for drug in drug_list:
                risk_data, match_type = self._lookup_risk(
                    gene, drug, diplotype, phenotype, gene_variants
                )
                rl  = risk_data.get("risk_label", "Unknown")
                sev = risk_data.get("severity", "none")

                if rl in ("Toxic", "Ineffective"):
                    high_risk_drug_count += 1
                elif rl == "Safe":
                    safe_drug_count += 1

                if SEVERITY_ORDER.get(sev, 0) > SEVERITY_ORDER.get(gene_worst_sev, 0):
                    gene_worst_sev  = sev
                    gene_worst_risk = rl
                if match_type in ("inferred", "fallback"):
                    ambiguous = True

            if SEVERITY_ORDER.get(gene_worst_sev, 0) > SEVERITY_ORDER.get(worst_severity, 0):
                worst_severity = gene_worst_sev

            genes_assessed.append({
                "gene":          gene,
                "diplotype":     diplotype,
                "phenotype":     phenotype,
                "risk_drugs":    drug_list,
                "risk_label":    gene_worst_risk,
                "severity":      gene_worst_sev,
                "ambiguity_flag": ambiguous
            })

        return {
            "patient_id":           parse_result.patient_id,
            "timestamp":            timestamp,
            "overall_severity":     worst_severity,
            "genes_assessed":       genes_assessed,
            "high_risk_drug_count": high_risk_drug_count,
            "safe_drug_count":      safe_drug_count,
            "novel_variants_count": total_novel_variants,
            "vcf_parsing_success":  parse_result.success and len(parse_result.variants) > 0,
            "warnings":             warnings
        }
