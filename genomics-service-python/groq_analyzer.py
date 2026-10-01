"""
Groq Fallback Wrapper.
Only used when the main deterministic pipeline needs an LLM explanation
and the primary llm_service call fails entirely.

NOTE: Groq no longer decides risk. The deterministic risk_engine.py is the
sole decision authority. This module only wraps the explanation call with
a clean error boundary.
"""
import os
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))


def groq_explain(
    gene: str,
    diplotype: str,
    phenotype: str,
    drug: str,
    risk_label: str,
    severity: str,
    detected_variants: List[Dict],
    cpic_recommendation: str,
    match_type: str = "unknown"
) -> Dict:
    """
    Thin wrapper around llm_service.generate_explanation.
    Provides a consistent error boundary so callers never crash.
    """
    try:
        from llm_service import generate_explanation
        return generate_explanation(
            gene=gene,
            diplotype=diplotype,
            phenotype=phenotype,
            drug=drug,
            risk_label=risk_label,
            severity=severity,
            detected_variants=detected_variants,
            cpic_recommendation=cpic_recommendation,
            match_type=match_type
        )
    except Exception as e:
        print(f"[GroqWrapper] Explanation call failed for {drug}/{gene}: {e}")
        rsids = [v.get('rsid', '') for v in detected_variants if v.get('rsid')]
        fallback_text = (
            f"Your {gene} genetic profile ({diplotype}, {phenotype}) affects how your "
            f"body processes {drug}. Risk classification: {risk_label} (severity: {severity}). "
            f"Consult your healthcare provider for personalised recommendations."
        )
        return {
            "patient_summary":     fallback_text,
            "clinician_mechanism": (
                f"{gene} ({diplotype}) confers {phenotype} phenotype for {drug}. "
                f"Risk: {risk_label}. CPIC: {cpic_recommendation} "
                f"Variants: {', '.join(rsids) or 'none'}."
            ),
            "variant_citations":   rsids,
            "summary":   fallback_text,
            "mechanism": f"{gene} ({diplotype}) — {risk_label} risk for {drug}.",
            "llm_confidence": 0.40
        }
