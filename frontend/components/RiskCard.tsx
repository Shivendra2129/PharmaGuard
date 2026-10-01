'use client';

import React, { useState } from 'react';
import { PharmaGuardResult } from '@/lib/types';

interface RiskCardProps {
  result: PharmaGuardResult;
}

// ── Static config ─────────────────────────────────────────────────────────────

const RISK_CONFIG: Record<string, { cssClass: string; emoji: string; bgGradient: string }> = {
  'Safe':          { cssClass: 'risk-safe',        emoji: '✅', bgGradient: 'from-emerald-950/50 to-gray-900/60 border-emerald-700/30' },
  'Adjust Dosage': { cssClass: 'risk-adjust',      emoji: '⚠️', bgGradient: 'from-amber-950/50 to-gray-900/60 border-amber-700/30' },
  'Toxic':         { cssClass: 'risk-toxic',        emoji: '☠️', bgGradient: 'from-red-950/50 to-gray-900/60 border-red-700/30' },
  'Ineffective':   { cssClass: 'risk-ineffective',  emoji: '🚫', bgGradient: 'from-red-950/50 to-gray-900/60 border-red-700/30' },
  'Unknown':       { cssClass: 'risk-unknown',      emoji: '❓', bgGradient: 'from-gray-900/50 to-gray-950/60 border-gray-700/30' },
};

const SEVERITY_COLORS: Record<string, string> = {
  none:     'text-gray-400',
  low:      'text-blue-400',
  moderate: 'text-amber-400',
  high:     'text-orange-400',
  critical: 'text-red-400',
};

const PHENOTYPE_LABELS: Record<string, string> = {
  PM:      'Poor Metabolizer',
  IM:      'Intermediate Metabolizer',
  NM:      'Normal Metabolizer',
  RM:      'Rapid Metabolizer',
  URM:     'Ultrarapid Metabolizer',
  Unknown: 'Unknown',
};

const MATCH_TYPE_LABELS: Record<string, { label: string; cssClass: string }> = {
  exact_diplotype: { label: 'Exact Diplotype Match', cssClass: 'match-exact' },
  phenotype:       { label: 'Phenotype Match',        cssClass: 'match-inferred' },
  rsid_special:    { label: 'rsID-Specific Rule',     cssClass: 'match-exact' },
  inferred:        { label: 'Inferred',               cssClass: 'match-inferred' },
  fallback:        { label: 'Fallback Rule',           cssClass: 'match-fallback' },
};

type TabId = 'patient' | 'clinician' | 'variants' | 'quality';

const TABS: { id: TabId; label: string; icon: string }[] = [
  { id: 'patient',   label: 'Patient View',   icon: '🗣️' },
  { id: 'clinician', label: 'Clinician View', icon: '🩺' },
  { id: 'variants',  label: 'Variants',       icon: '🧬' },
  { id: 'quality',   label: 'Quality',        icon: '📊' },
];

// ── Sub-components ────────────────────────────────────────────────────────────

const ConfidenceBar = ({ score, label }: { score: number; label?: string }) => {
  const pct   = Math.round(score * 100);
  const color = pct >= 85 ? '#10b981' : pct >= 70 ? '#f59e0b' : '#ef4444';
  return (
    <div>
      {label && (
        <div className="flex justify-between text-xs text-gray-500 mb-1.5">
          <span>{label}</span>
          <span className="font-mono font-semibold" style={{ color }}>{pct}%</span>
        </div>
      )}
      <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
    </div>
  );
};

const InfoGrid = ({ items }: { items: { label: string; value: string | undefined; mono?: boolean }[] }) => (
  <div className="grid grid-cols-2 gap-2">
    {items.map(({ label, value, mono }) => (
      <div key={label} className="bg-gray-900/50 rounded-xl p-3">
        <p className="text-xs text-gray-500 mb-1">{label}</p>
        <p className={`text-sm font-semibold text-gray-200 ${mono ? 'font-mono' : ''}`}>
          {value || '—'}
        </p>
      </div>
    ))}
  </div>
);

// ── Tab: Patient View ─────────────────────────────────────────────────────────

const PatientTab: React.FC<{ result: PharmaGuardResult }> = ({ result }) => {
  const expl    = result.llm_generated_explanation;
  const profile = result.pharmacogenomic_profile;
  const summary = expl?.patient_summary || expl?.summary || 'No patient summary available.';

  return (
    <div className="space-y-4">
      {/* Plain-language patient summary */}
      <div className="rounded-xl bg-indigo-950/30 border border-indigo-500/15 p-4">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-base">🗣️</span>
          <p className="text-xs font-bold text-indigo-300 uppercase tracking-wider">
            Plain-Language Summary
          </p>
        </div>
        <p className="text-gray-200 text-sm leading-relaxed">{summary}</p>
      </div>

      {/* What this means for you */}
      <div className="rounded-xl bg-gray-900/40 p-4 space-y-3">
        <p className="text-xs text-gray-500 uppercase tracking-wider font-semibold">
          What This Means For You
        </p>
        <div className="grid grid-cols-2 gap-2">
          <div className="bg-gray-900/60 rounded-lg p-3">
            <p className="text-xs text-gray-500 mb-1">Your Gene</p>
            <p className="text-sm font-bold text-gray-200 font-mono">{profile?.primary_gene}</p>
          </div>
          <div className="bg-gray-900/60 rounded-lg p-3">
            <p className="text-xs text-gray-500 mb-1">Metabolizer Type</p>
            <p className="text-sm font-bold text-gray-200">
              {PHENOTYPE_LABELS[profile?.phenotype] || profile?.phenotype}
            </p>
          </div>
        </div>
      </div>

      {/* Dose recommendation in plain language */}
      {result.clinical_recommendation?.dose_adjustment && (
        <div className="rounded-xl bg-gray-900/40 p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wider font-semibold mb-2">
            What Your Doctor Should Know
          </p>
          <p className="text-gray-300 text-sm leading-relaxed">
            {result.clinical_recommendation.dose_adjustment}
          </p>
        </div>
      )}

      {/* Variant citations */}
      {expl?.variant_citations && expl.variant_citations.length > 0 && (
        <div>
          <p className="text-xs text-gray-500 uppercase tracking-wider font-semibold mb-2">
            Genetic Variants Found
          </p>
          <div className="flex flex-wrap gap-2">
            {expl.variant_citations.map(rs => (
              <span key={rs}
                    className="px-2.5 py-1 text-xs font-mono font-semibold
                               bg-purple-900/30 border border-purple-500/30 text-purple-300 rounded-lg">
                {rs}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

// ── Tab: Clinician View ───────────────────────────────────────────────────────

const ClinicianTab: React.FC<{ result: PharmaGuardResult }> = ({ result }) => {
  const expl       = result.llm_generated_explanation;
  const profile    = result.pharmacogenomic_profile;
  const rec        = result.clinical_recommendation;
  const ra         = result.risk_assessment;
  const mechanism  = expl?.clinician_mechanism || expl?.mechanism || 'No mechanism available.';
  const matchInfo  = MATCH_TYPE_LABELS[ra?.match_type || ''] || MATCH_TYPE_LABELS.fallback;

  return (
    <div className="space-y-4">
      {/* CPIC Pharmacogenomic Profile */}
      <InfoGrid items={[
        { label: 'Primary Gene',      value: profile?.primary_gene, mono: true },
        { label: 'Diplotype',         value: profile?.diplotype, mono: true },
        { label: 'Phenotype',         value: profile?.phenotype },
        { label: 'Evidence Level',    value: rec?.evidence_level || 'B' },
      ]} />

      {/* Rule match type */}
      <div className="flex items-center gap-2">
        <p className="text-xs text-gray-500">Rule Match:</p>
        <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${matchInfo.cssClass}`}>
          {matchInfo.label}
        </span>
        {profile?.ambiguity_flag && (
          <span className="ambiguity-flag">~ inferred</span>
        )}
      </div>

      {/* Biochemical mechanism */}
      <div className="rounded-xl bg-gray-900/40 border border-gray-700/30 p-4">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-base">⚗️</span>
          <p className="text-xs font-bold text-emerald-400 uppercase tracking-wider">
            Biochemical Mechanism
          </p>
        </div>
        <p className="text-gray-300 text-sm leading-relaxed">{mechanism}</p>
      </div>

      {/* CPIC guideline */}
      <div className="rounded-xl bg-gray-900/40 p-4 space-y-3">
        <p className="text-xs font-bold text-amber-400 uppercase tracking-wider">
          CPIC Clinical Recommendation
        </p>
        <div className="space-y-2">
          <div className="bg-gray-900/60 rounded-lg p-3">
            <p className="text-xs text-gray-500 mb-1">Guideline</p>
            <p className="text-gray-300 text-sm">{rec?.cpic_guideline}</p>
          </div>
          <div className="bg-gray-900/60 rounded-lg p-3">
            <p className="text-xs text-gray-500 mb-1">Dose Adjustment</p>
            <p className="text-gray-300 text-sm">{rec?.dose_adjustment}</p>
          </div>
        </div>
      </div>

      {/* Alternative drugs */}
      {rec?.alternative_drugs && rec.alternative_drugs.length > 0 && (
        <div>
          <p className="text-xs text-gray-500 uppercase tracking-wider font-semibold mb-2">
            CPIC Alternative Drugs
          </p>
          <div className="flex flex-wrap gap-2">
            {rec.alternative_drugs.map(d => (
              <span key={d}
                    className="px-3 py-1 text-xs font-bold
                               bg-indigo-900/30 border border-indigo-500/30 text-indigo-300 rounded-lg">
                {d}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

// ── Tab: Variants ─────────────────────────────────────────────────────────────

const VariantsTab: React.FC<{ result: PharmaGuardResult }> = ({ result }) => {
  const variants = result.pharmacogenomic_profile?.detected_variants || [];

  if (variants.length === 0) {
    return (
      <div className="text-center py-8">
        <div className="text-4xl mb-3">🧬</div>
        <p className="text-gray-400 text-sm">No specific variants detected.</p>
        <p className="text-gray-600 text-xs mt-1">
          Risk was inferred from gene-level phenotype data.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-gray-500 uppercase tracking-wider font-semibold">
        {variants.length} Variant{variants.length > 1 ? 's' : ''} Detected
      </p>
      {variants.map((v, i) => (
        <div key={i}
             className="bg-gray-900/50 rounded-xl p-4 border border-white/5
                        hover:border-indigo-500/20 transition-colors duration-200">
          <div className="flex items-start justify-between flex-wrap gap-2 mb-3">
            <div className="flex items-center gap-2">
              <span className="text-lg font-mono font-bold text-indigo-400">{v.rsid}</span>
              {v.is_novel && <span className="novel-badge">⚠ Novel</span>}
            </div>
            {v.star_allele && v.star_allele !== '*1' && (
              <span className="px-2 py-0.5 text-xs font-mono font-bold
                               bg-purple-900/30 border border-purple-500/30 text-purple-300 rounded-md">
                {v.star_allele}
              </span>
            )}
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="bg-gray-900/40 rounded-lg p-2">
              <p className="text-gray-500 mb-0.5">Location</p>
              <p className="font-mono text-gray-300">
                {v.chromosome}:{v.position?.toLocaleString()}
              </p>
            </div>
            <div className="bg-gray-900/40 rounded-lg p-2">
              <p className="text-gray-500 mb-0.5">Genotype</p>
              <p className="font-mono text-gray-300">{v.genotype || '—'}</p>
            </div>
          </div>
          {v.is_novel && (
            <p className="text-amber-400/70 text-xs mt-2 flex items-center gap-1">
              <span>⚠</span>
              This star allele is not catalogued in our CPIC knowledge base.
              Risk assessment used phenotype inference.
            </p>
          )}
        </div>
      ))}

      {result.pharmacogenomic_profile?.novel_variants_detected && (
        <div className="rounded-xl border border-amber-500/20 bg-amber-950/20 p-3">
          <p className="text-amber-400 text-xs font-semibold">
            ⚠ Novel/uncatalogued variants detected. Diplotype inference was used for risk assessment.
            Confidence score may be reduced.
          </p>
        </div>
      )}
    </div>
  );
};

// ── Tab: Quality Metrics ──────────────────────────────────────────────────────

const QualityTab: React.FC<{ result: PharmaGuardResult }> = ({ result }) => {
  const q  = result.quality_metrics;
  const ra = result.risk_assessment;
  const matchInfo = MATCH_TYPE_LABELS[ra?.match_type || ''] || MATCH_TYPE_LABELS.fallback;

  return (
    <div className="space-y-4">
      {/* Confidence scores */}
      <div className="space-y-3">
        <p className="text-xs text-gray-500 uppercase tracking-wider font-semibold">
          Confidence Scores
        </p>
        <ConfidenceBar score={ra?.confidence_score || 0} label="CPIC Risk Confidence" />
        <ConfidenceBar score={q?.llm_confidence || 0}    label="LLM Explanation Confidence" />
      </div>

      {/* Quality grid */}
      <div className="grid grid-cols-2 gap-2">
        {[
          {
            label: 'VCF Parsing',
            value: q?.vcf_parsing_success ? '✓ Success' : '✗ Failed',
            ok:    q?.vcf_parsing_success
          },
          {
            label: 'CPIC Guideline',
            value: q?.guideline_version || 'CPIC v2.0',
            ok:    true
          },
          {
            label: 'Match Quality',
            value: q?.diplotype_match_quality === 'exact'    ? '✓ Exact'
                 : q?.diplotype_match_quality === 'inferred' ? '~ Inferred'
                 : '— None',
            ok: q?.diplotype_match_quality === 'exact'
          },
          {
            label: 'Novel Variants',
            value: (q?.novel_variants_flagged ?? 0) > 0
                    ? `${q!.novel_variants_flagged} Flagged`
                    : '✓ None',
            ok: (q?.novel_variants_flagged ?? 0) === 0
          },
        ].map(({ label, value, ok }) => (
          <div key={label} className="bg-gray-900/50 rounded-xl p-3">
            <p className="text-xs text-gray-500 mb-1">{label}</p>
            <p className={`text-sm font-semibold ${ok ? 'text-emerald-400' : 'text-amber-400'}`}>
              {value}
            </p>
          </div>
        ))}
      </div>

      {/* VCF qual score */}
      {q?.vcf_qual_score != null && (
        <div className="bg-gray-900/40 rounded-xl p-3">
          <p className="text-xs text-gray-500 mb-1">Average VCF QUAL Score</p>
          <p className={`text-sm font-bold font-mono ${
            q.vcf_qual_score >= 30 ? 'text-emerald-400'
            : q.vcf_qual_score >= 10 ? 'text-amber-400'
            : 'text-red-400'
          }`}>
            {q.vcf_qual_score.toFixed(1)}
            {q.vcf_qual_score < 20 && (
              <span className="text-xs font-normal text-amber-400 ml-2">
                ⚠ Low quality may reduce confidence
              </span>
            )}
          </p>
        </div>
      )}

      {/* Rule match type */}
      <div className="bg-gray-900/40 rounded-xl p-3">
        <p className="text-xs text-gray-500 mb-2">Risk Rule Match Type</p>
        <span className={`text-xs font-bold px-3 py-1.5 rounded-full ${matchInfo.cssClass}`}>
          {matchInfo.label}
        </span>
        <p className="text-xs text-gray-600 mt-2">
          {ra?.match_type === 'exact_diplotype' &&
            'Diplotype found verbatim in CPIC CSV — highest confidence.'}
          {ra?.match_type === 'phenotype' &&
            'No exact diplotype match; phenotype-level rule applied.'}
          {ra?.match_type === 'rsid_special' &&
            'Risk determined via specific rsID lookup (e.g. DPYD toxic sites).'}
          {ra?.match_type === 'inferred' &&
            'No direct match; risk inferred from closest available rule.'}
          {ra?.match_type === 'fallback' &&
            'No rule found; generic fallback applied. Lowest confidence.'}
        </p>
      </div>
    </div>
  );
};

// ── Main RiskCard ─────────────────────────────────────────────────────────────

const RiskCard: React.FC<RiskCardProps> = ({ result }) => {
  const [activeTab, setActiveTab] = useState<TabId>('patient');

  const riskLabel = result.risk_assessment?.risk_label || 'Unknown';
  const config    = RISK_CONFIG[riskLabel] || RISK_CONFIG['Unknown'];
  const profile   = result.pharmacogenomic_profile;

  // Error state
  if (result.error) {
    return (
      <div className="glass-card rounded-2xl p-6 border border-red-700/30
                      bg-gradient-to-br from-red-950/50 to-gray-900/60 fade-in">
        <div className="flex items-center gap-3 mb-3">
          <span className="text-2xl">❌</span>
          <div>
            <h3 className="font-bold text-red-400 text-lg">{result.drug}</h3>
            <p className="text-red-300/70 text-sm font-mono">{result.error}</p>
          </div>
        </div>
        <p className="text-gray-400 text-sm bg-red-950/40 rounded-xl p-3">{result.detail}</p>
      </div>
    );
  }

  return (
    <div className={`glass-card rounded-2xl overflow-hidden border
                     bg-gradient-to-br ${config.bgGradient} fade-in`}>

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="px-6 py-5 border-b border-white/5">
        <div className="flex items-start justify-between flex-wrap gap-3 mb-4">
          <div className="flex items-center gap-3">
            <span className="text-3xl">{config.emoji}</span>
            <div>
              <h3 className="text-xl font-extrabold text-white">{result.drug}</h3>
              <p className="text-gray-400 text-sm font-mono">
                {profile?.primary_gene}
                {profile?.diplotype && profile.diplotype !== 'unknown'
                  ? ` · ${profile.diplotype}` : ''}
              </p>
            </div>
          </div>
          <div className="flex flex-col items-end gap-1.5">
            <span className={`px-4 py-1.5 rounded-full text-sm font-bold ${config.cssClass}`}>
              {riskLabel}
            </span>
            <span className={`text-xs font-semibold uppercase tracking-wider
                              ${SEVERITY_COLORS[result.risk_assessment?.severity] || 'text-gray-400'}`}>
              {result.risk_assessment?.severity} severity
            </span>
          </div>
        </div>

        {/* Confidence bar */}
        <ConfidenceBar
          score={result.risk_assessment?.confidence_score || 0}
          label={`Confidence · ${PHENOTYPE_LABELS[profile?.phenotype] || profile?.phenotype || ''}`}
        />
      </div>

      {/* ── Tab Bar ────────────────────────────────────────────────────────── */}
      <div className="px-4 pt-4">
        <div className="tab-bar">
          {TABS.map(tab => (
            <button
              key={tab.id}
              id={`tab-${result.drug.toLowerCase()}-${tab.id}`}
              className={`tab-btn ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              <span className="mr-1">{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Tab Content ────────────────────────────────────────────────────── */}
      <div className="p-4 pt-3">
        {activeTab === 'patient'   && <PatientTab    result={result} />}
        {activeTab === 'clinician' && <ClinicianTab  result={result} />}
        {activeTab === 'variants'  && <VariantsTab   result={result} />}
        {activeTab === 'quality'   && <QualityTab    result={result} />}
      </div>
    </div>
  );
};

export default RiskCard;
