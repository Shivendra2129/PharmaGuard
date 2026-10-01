"""
LLM Explainability Service — Dual-Tier.
Uses Groq API (OpenAI-compatible) to generate clinical explanations ONLY.

Risk is pre-determined by the deterministic CPIC rule engine.
The LLM produces two distinct outputs:
  1. patient_summary   — plain-language, jargon-free (2-3 sentences)
  2. clinician_mechanism — detailed enzyme kinetics + CPIC guideline reference (3-4 sentences)
"""
import os
import json
from typing import Dict, List
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

GROQ_API_KEY  = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL    = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# ── System Prompt ──────────────────────────────────────────────────────────────

CLINICAL_SYSTEM_PROMPT = """You are a senior clinical pharmacogenomics expert with deep knowledge of CPIC guidelines, pharmacokinetics, and precision medicine.

Your ONLY role is to EXPLAIN a pre-determined drug risk assessment. You must:
1. NEVER modify the genotype, phenotype, risk label, or confidence — these are already determined by a deterministic rules engine.
2. Write a patient_summary: 2-3 plain-language sentences with NO medical jargon. Explain what the result means for everyday medication safety.
3. Write a clinician_mechanism: 3-4 technical sentences covering enzyme/transporter biology, pathway kinetics, and CPIC guideline implications.
4. Cite all provided rsIDs explicitly in clinician_mechanism.
5. Respond ONLY with a valid JSON object — no other text, no markdown fences.
"""


# ── Prompt Builder ─────────────────────────────────────────────────────────────

def build_explanation_prompt(
    gene: str, diplotype: str, phenotype: str, drug: str,
    risk_label: str, severity: str,
    detected_variants: List[Dict], cpic_recommendation: str,
    match_type: str = "unknown"
) -> str:
    """Build the structured dual-tier explanation prompt."""
    variant_lines = "\n".join(
        f"  - {v.get('rsid','?')} at {v.get('chromosome','')}:{v.get('position','')} "
        f"| GT: {v.get('genotype','?')} | Star: {v.get('star_allele','?')}"
        f"{'  ⚠ NOVEL/UNCATALOGUED' if v.get('is_novel') else ''}"
        for v in detected_variants
    ) or "  - No specific variants detected (phenotype inferred)"

    rsids = [v.get('rsid', '') for v in detected_variants if v.get('rsid')]
    rsids_str = ", ".join(rsids) if rsids else "none"

    return f"""A pharmacogenomic risk assessment has been completed by a deterministic CPIC rules engine. Your task is to EXPLAIN it.

PRE-DETERMINED ASSESSMENT (do NOT change these values):
  Gene:            {gene}
  Diplotype:       {diplotype}
  Phenotype:       {phenotype}
  Drug:            {drug}
  Risk Label:      {risk_label}
  Severity:        {severity}
  CPIC Recommendation: {cpic_recommendation}
  Match Type:      {match_type}  (exact_diplotype=high certainty, inferred=lower certainty)

DETECTED VARIANTS:
{variant_lines}

INSTRUCTIONS:
  - patient_summary: Explain what {phenotype} phenotype + {risk_label} risk means for a patient taking {drug}. No jargon. 2-3 sentences.
  - clinician_mechanism: Explain how {gene} enzyme/transporter activity is altered by {diplotype}, why it causes {risk_label} risk for {drug}, cite rsIDs {rsids_str}, and what CPIC recommends. 3-4 sentences.
  - variant_citations: List the cited rsIDs as a JSON array.

Return ONLY this JSON (no extra text):
{{
  "patient_summary": "...",
  "clinician_mechanism": "...",
  "variant_citations": ["{rsids_str.replace(', ', '", "')}"]
}}"""


# ── Main Entry Point ───────────────────────────────────────────────────────────

def generate_explanation(
    gene: str,
    diplotype: str,
    phenotype: str,
    drug: str,
    risk_label: str,
    severity: str,
    detected_variants: List[Dict],
    cpic_recommendation: str,
    match_type: str = "unknown"
) -> Dict[str, object]:
    """
    Generate dual-tier LLM explanation for a pre-determined pharmacogenomic risk.
    Returns dict with patient_summary, clinician_mechanism, variant_citations, llm_confidence.
    Falls back to rich template-based explanation if Groq API is unavailable.
    """
    if not GROQ_API_KEY or GROQ_API_KEY.startswith("gsk_your"):
        print("[LLMService] No Groq API key configured — using template explanation.")
        return _template_explanation(
            gene, diplotype, phenotype, drug, risk_label, severity, detected_variants
        )

    try:
        client = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)
        prompt = build_explanation_prompt(
            gene, diplotype, phenotype, drug, risk_label,
            severity, detected_variants, cpic_recommendation, match_type
        )

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": CLINICAL_SYSTEM_PROMPT},
                {"role": "user",   "content": prompt}
            ],
            temperature=0.15,    # Low temperature for factual clinical content
            max_tokens=700
        )

        raw = (response.choices[0].message.content or "").strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        parsed = json.loads(raw)

        patient_summary      = str(parsed.get("patient_summary", ""))
        clinician_mechanism  = str(parsed.get("clinician_mechanism", ""))
        citations_raw        = parsed.get("variant_citations", [])

        if isinstance(citations_raw, str):
            citations = [s.strip() for s in citations_raw.split(',') if s.strip()]
        elif isinstance(citations_raw, list):
            citations = [str(c) for c in citations_raw]
        else:
            citations = []

        llm_confidence = 0.88 if patient_summary and clinician_mechanism else 0.40
        print(f"[LLMService] [OK] Dual-tier explanation generated via {GROQ_MODEL} for {drug}/{gene}")

        return {
            "patient_summary":     patient_summary,
            "clinician_mechanism": clinician_mechanism,
            "variant_citations":   citations,
            # Legacy compat fields
            "summary":   patient_summary,
            "mechanism": clinician_mechanism,
            "llm_confidence": llm_confidence
        }

    except json.JSONDecodeError as je:
        print(f"[LLMService] JSON parse error: {je}")
        return _template_explanation(
            gene, diplotype, phenotype, drug, risk_label, severity, detected_variants
        )
    except Exception as e:
        print(f"[LLMService] Groq call failed: {e}")
        return _template_explanation(
            gene, diplotype, phenotype, drug, risk_label, severity, detected_variants
        )


# ── Template Fallback ──────────────────────────────────────────────────────────

def _template_explanation(
    gene: str, diplotype: str, phenotype: str, drug: str,
    risk_label: str, severity: str, detected_variants: List[Dict]
) -> Dict:
    """
    Rich template-based dual-tier explanation.
    Used when Groq API key is absent or call fails.
    Medically accurate, deterministic, and jargon-segregated by audience.
    """
    rsids = [v.get('rsid', '') for v in detected_variants if v.get('rsid')]
    rsids_str = ", ".join(rsids) if rsids else "no specific variants"

    ph_map = {
        "PM":  "poor metabolizer",
        "IM":  "intermediate metabolizer",
        "NM":  "normal metabolizer",
        "RM":  "rapid metabolizer",
        "URM": "ultrarapid metabolizer",
        "Unknown": "metabolizer status unknown"
    }
    ph_desc = ph_map.get(phenotype, phenotype.lower())

    # ─ Patient Summaries ─
    _patient_summaries: Dict[tuple, str] = {
        ("CYP2D6", "CODEINE"): (
            f"Your genetic profile shows you are a {ph_desc} for the CYP2D6 gene, which controls how your body converts codeine into morphine. "
            f"{'Codeine may be ineffective for you as your body cannot make the conversion adequately.' if risk_label == 'Ineffective' else 'Your body may convert codeine too quickly, causing dangerous morphine build-up.' if risk_label == 'Toxic' else 'You may need a dose adjustment to use codeine safely.'} "
            f"Please inform your doctor of this genetic finding before any prescription."
        ),
        ("CYP2C19", "CLOPIDOGREL"): (
            f"You carry a genetic variant in CYP2C19 making you a {ph_desc} for clopidogrel (a blood thinner). "
            f"{'This means clopidogrel may not work properly for you, raising your risk of heart attack or stroke.' if risk_label in ('Ineffective', 'Adjust Dosage') else 'Standard clopidogrel should work well for your genetic profile.'} "
            f"Discuss alternative antiplatelet medications with your cardiologist."
        ),
        ("CYP2C9", "WARFARIN"): (
            f"Your CYP2C9 gene makes you a {ph_desc} for warfarin, meaning your body breaks it down more slowly than average. "
            f"{'This significantly increases your bleeding risk at standard doses — a reduced dose and closer monitoring are needed.' if risk_label in ('Toxic', 'Adjust Dosage') else 'Standard warfarin dosing appears suitable based on your CYP2C9 genetics.'} "
            f"Ensure your doctor knows this before starting or adjusting warfarin therapy."
        ),
        ("SLCO1B1", "SIMVASTATIN"): (
            f"Your SLCO1B1 gene affects how well your liver absorbs simvastatin. As a {ph_desc}, "
            f"{'simvastatin may accumulate in your bloodstream, increasing muscle damage (myopathy) risk. A lower dose or different statin is recommended.' if risk_label in ('Toxic', 'Adjust Dosage') else 'simvastatin at standard doses is appropriate based on your SLCO1B1 genetics.'} "
            f"Report any muscle pain or weakness to your doctor immediately."
        ),
        ("TPMT", "AZATHIOPRINE"): (
            f"Your TPMT gene profile shows you are a {ph_desc}, meaning your body cannot process azathioprine at normal speed. "
            f"{'This creates a serious risk of bone marrow toxicity — significantly reduced doses or a different medication is essential.' if risk_label in ('Toxic', 'Adjust Dosage') else 'Standard azathioprine dosing is appropriate based on your TPMT genetics.'} "
            f"Blood count monitoring is critical if this medication is prescribed."
        ),
        ("DPYD", "FLUOROURACIL"): (
            f"Your DPYD gene shows you are a {ph_desc} for fluorouracil (5-FU), meaning your body cannot break it down quickly enough. "
            f"{'This puts you at life-threatening risk of severe side effects — dose reduction or an alternative chemotherapy is mandatory.' if risk_label in ('Toxic', 'Adjust Dosage') else 'Standard fluorouracil dosing appears appropriate based on your DPYD genetics.'} "
            f"Discuss this finding with your oncologist immediately."
        ),
    }

    # ─ Clinician Mechanisms ─
    _clinician_mechanisms: Dict[tuple, str] = {
        ("CYP2D6", "CODEINE"): (
            f"CYP2D6 encodes a hepatic cytochrome P450 enzyme responsible for O-demethylation of codeine to its active metabolite, morphine (approximately 10% of ingested codeine). "
            f"The {diplotype} diplotype confers {ph_desc} status; in poor metabolizers, this conversion is virtually absent, resulting in negligible analgesic effect (risk label: {risk_label}). "
            f"In ultrarapid metabolizers (*1xN/*1xN), excess morphine accumulation causes opioid toxicity and respiratory depression. "
            f"Variants {rsids_str} disrupt CYP2D6 enzyme function. CPIC strongly recommends avoiding codeine in PM and URM phenotypes in favour of non-CYP2D6-metabolised opioids."
        ),
        ("CYP2C19", "CLOPIDOGREL"): (
            f"CYP2C19 is the principal enzyme converting clopidogrel (a prodrug) to its active thiol metabolite, which irreversibly inhibits platelet P2Y12 ADP receptors. "
            f"The {diplotype} diplotype confers {ph_desc} status. Poor metabolizers generate insufficient active metabolite, leading to inadequate platelet inhibition and elevated major adverse cardiovascular event (MACE) risk. "
            f"Variants {rsids_str} reduce CYP2C19 catalytic activity via loss-of-function allele effects. "
            f"CPIC (Evidence Level A) recommends prasugrel or ticagrelor as therapeutic alternatives for PM/IM phenotypes."
        ),
        ("CYP2C9", "WARFARIN"): (
            f"CYP2C9 is the primary enzyme metabolising S-warfarin, the more pharmacologically potent enantiomer (~3–5× more active than R-warfarin). "
            f"The {diplotype} genotype ({ph_desc}) reduces S-warfarin clearance, causing drug accumulation and supratherapeutic anticoagulation with elevated haemorrhagic risk. "
            f"Variants {rsids_str} reduce CYP2C9 enzyme activity via altered enzyme kinetics (increased Km, decreased Vmax). "
            f"CPIC recommends dose reduction proportional to activity loss (e.g. *2: 10–25%; *3: 25–50%) with increased INR monitoring frequency during initiation."
        ),
        ("SLCO1B1", "SIMVASTATIN"): (
            f"SLCO1B1 encodes the OATP1B1 hepatic uptake transporter, which mediates active hepatocellular influx of simvastatin acid (the pharmacologically active hydroxy-acid form). "
            f"The {diplotype} genotype impairs OATP1B1 activity, reducing hepatic first-pass extraction and elevating systemic simvastatin acid plasma AUC by 120–220%. "
            f"Elevated skeletal muscle exposure via variants {rsids_str} (rs4149056: SLCO1B1 c.521T>C) significantly increases statin-associated myopathy (SAM) and rhabdomyolysis risk. "
            f"CPIC recommends maximum simvastatin 20 mg/day for *1/*5 IM or switching to rosuvastatin/pravastatin for *5/*5 PM phenotypes."
        ),
        ("TPMT", "AZATHIOPRINE"): (
            f"TPMT (thiopurine S-methyltransferase) catalyses S-methylation of 6-mercaptopurine (6-MP), the primary active metabolite of azathioprine, competing with the pathway producing cytotoxic thioguanine nucleotides (TGN). "
            f"In {ph_desc} patients ({diplotype}), markedly reduced TPMT activity shifts metabolic flux toward TGN accumulation in haematopoietic cells, causing severe myelosuppression and pancytopenia. "
            f"Variants {rsids_str} encode non-functional or reduced-activity TPMT enzymes via amino acid substitutions (e.g. *3A: G238C + A719G). "
            f"CPIC mandates 10-fold dose reduction (to ~10% of standard dose) for PM patients or substitution with mycophenolate mofetil/ciclosporin."
        ),
        ("DPYD", "FLUOROURACIL"): (
            f"DPYD (dihydropyrimidine dehydrogenase) mediates the rate-limiting first step in fluorouracil (5-FU) catabolism, accounting for >80% of systemic 5-FU elimination via dihydrofluorouracil formation. "
            f"The {diplotype} diplotype causes {ph_desc} DPD enzyme status, dramatically reducing 5-FU clearance and causing drug accumulation with life-threatening toxicities: grade ≥3 mucositis, neutropenia, hand-foot syndrome, and neurotoxicity. "
            f"Variants {rsids_str} include DPYD*2A (c.1905+1G>A splice-site), abolishing or severely impairing DPD activity. "
            f"CPIC requires 50% starting dose reduction for heterozygous IM patients (one non-functional allele) and absolute contraindication for homozygous PM patients."
        ),
    }

    key = (gene.upper(), drug.upper())

    patient_summary = _patient_summaries.get(
        key,
        (
            f"Your {gene} genetic profile shows you are a {ph_desc} for {drug}, resulting in a {risk_label.lower()} risk classification. "
            f"This means {'your body processes this medication differently from most people.' if risk_label != 'Safe' else 'standard dosing should be appropriate for you.'} "
            f"Discuss this result with your healthcare provider before starting or continuing this medication."
        )
    )

    clinician_mechanism = _clinician_mechanisms.get(
        key,
        (
            f"The {gene} gene ({diplotype}, {ph_desc}) governs {drug} pharmacokinetics through enzyme or transporter activity. "
            f"The identified diplotype results in {risk_label.lower()} risk; variants {rsids_str} alter gene product function, leading to altered drug exposure. "
            f"Consult current CPIC guidelines for {gene}/{drug} (evidence level dependent on diplotype match) for specific dosing adjustments and therapeutic alternatives."
        )
    )

    return {
        "patient_summary":     patient_summary,
        "clinician_mechanism": clinician_mechanism,
        "variant_citations":   rsids,
        # Legacy compat
        "summary":   patient_summary,
        "mechanism": clinician_mechanism,
        "llm_confidence": 0.75
    }
