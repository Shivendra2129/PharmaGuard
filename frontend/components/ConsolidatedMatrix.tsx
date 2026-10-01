'use client';

import React from 'react';
import { ConsolidatedRiskReport, GeneRiskEntry } from '@/lib/types';

interface ConsolidatedMatrixProps {
  report: ConsolidatedRiskReport;
}

// ── Static metadata for each gene ────────────────────────────────────────────

const GENE_META: Record<string, { drug: string; enzyme: string }> = {
  CYP2D6:  { drug: 'CODEINE',      enzyme: 'CYP2D6 enzyme' },
  CYP2C19: { drug: 'CLOPIDOGREL',  enzyme: 'CYP2C19 enzyme' },
  CYP2C9:  { drug: 'WARFARIN',     enzyme: 'CYP2C9 enzyme' },
  SLCO1B1: { drug: 'SIMVASTATIN',  enzyme: 'OATP1B1 transporter' },
  TPMT:    { drug: 'AZATHIOPRINE', enzyme: 'TPMT enzyme' },
  DPYD:    { drug: 'FLUOROURACIL', enzyme: 'DPD enzyme' },
};

// ── Risk colour mapping ───────────────────────────────────────────────────────

function riskCellClass(riskLabel: string): string {
  if (riskLabel === 'Safe')          return 'gene-cell-safe';
  if (riskLabel === 'Adjust Dosage') return 'gene-cell-adjust';
  if (riskLabel === 'Toxic' || riskLabel === 'Ineffective') return 'gene-cell-danger';
  return 'gene-cell-unknown';
}

function riskTextColor(riskLabel: string): string {
  if (riskLabel === 'Safe')          return 'text-emerald-400';
  if (riskLabel === 'Adjust Dosage') return 'text-amber-400';
  if (riskLabel === 'Toxic' || riskLabel === 'Ineffective') return 'text-red-400';
  return 'text-gray-400';
}

function riskEmoji(riskLabel: string): string {
  if (riskLabel === 'Safe')          return '✅';
  if (riskLabel === 'Adjust Dosage') return '⚠️';
  if (riskLabel === 'Toxic')         return '☠️';
  if (riskLabel === 'Ineffective')   return '🚫';
  return '❓';
}

function phenotypeColor(phenotype: string): string {
  if (phenotype === 'PM')  return 'text-red-400';
  if (phenotype === 'IM')  return 'text-amber-400';
  if (phenotype === 'NM')  return 'text-emerald-400';
  if (phenotype === 'RM')  return 'text-blue-400';
  if (phenotype === 'URM') return 'text-purple-400';
  return 'text-gray-400';
}

// ── Overall severity banner ───────────────────────────────────────────────────

const OVERALL_SEV_CONFIG: Record<string, {
  bg: string; border: string; text: string; icon: string; label: string;
}> = {
  none:     { bg: 'rgba(16,185,129,0.08)',  border: 'rgba(16,185,129,0.3)',  text: '#10b981', icon: '🟢', label: 'All Clear' },
  low:      { bg: 'rgba(96,165,250,0.08)',  border: 'rgba(96,165,250,0.3)',  text: '#60a5fa', icon: '🔵', label: 'Low Risk' },
  moderate: { bg: 'rgba(245,158,11,0.08)',  border: 'rgba(245,158,11,0.3)',  text: '#f59e0b', icon: '🟡', label: 'Moderate Risk' },
  high:     { bg: 'rgba(249,115,22,0.08)',  border: 'rgba(249,115,22,0.3)',  text: '#f97316', icon: '🟠', label: 'High Risk' },
  critical: { bg: 'rgba(239,68,68,0.08)',   border: 'rgba(239,68,68,0.3)',   text: '#ef4444', icon: '🔴', label: 'Critical Risk' },
};

// ── Sub-components ────────────────────────────────────────────────────────────

const Pill: React.FC<{ children: React.ReactNode; className?: string }> = ({ children, className = '' }) => (
  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${className}`}>
    {children}
  </span>
);

const GeneCellComponent: React.FC<{ entry: GeneRiskEntry }> = ({ entry }) => {
  const cellClass = riskCellClass(entry.risk_label);
  const textColor = riskTextColor(entry.risk_label);
  const phColor   = phenotypeColor(entry.phenotype);
  const emoji     = riskEmoji(entry.risk_label);

  return (
    <div className={`gene-cell ${cellClass} fade-in`}>
      {/* Gene name */}
      <p className="text-xs font-bold text-gray-300 mb-1 tracking-wide">{entry.gene}</p>

      {/* Risk emoji */}
      <div className="text-2xl mb-2">{emoji}</div>

      {/* Diplotype */}
      <p className="font-mono text-xs text-gray-400 mb-1">{entry.diplotype}</p>

      {/* Phenotype */}
      <p className={`text-xs font-bold mb-2 ${phColor}`}>{entry.phenotype}</p>

      {/* Risk label */}
      <Pill className={`text-[10px] ${textColor} bg-black/20 border border-current/30 mb-1`}>
        {entry.risk_label}
      </Pill>

      {/* Ambiguity flag */}
      {entry.ambiguity_flag && (
        <div className="mt-1">
          <span className="ambiguity-flag text-[9px]">
            ~ inferred
          </span>
        </div>
      )}
    </div>
  );
};

// ── Main ConsolidatedMatrix Component ────────────────────────────────────────

const ConsolidatedMatrix: React.FC<ConsolidatedMatrixProps> = ({ report }) => {
  const sevCfg = OVERALL_SEV_CONFIG[report.overall_severity] || OVERALL_SEV_CONFIG.none;

  const highRisk = report.genes_assessed.filter(
    g => g.risk_label === 'Toxic' || g.risk_label === 'Ineffective'
  );
  const adjustRisk = report.genes_assessed.filter(g => g.risk_label === 'Adjust Dosage');
  const safeGenes  = report.genes_assessed.filter(g => g.risk_label === 'Safe');

  return (
    <div className="glass-card rounded-2xl overflow-hidden fade-in"
         style={{ border: `1px solid ${sevCfg.border}` }}>

      {/* ── Banner ───────────────────────────────────────────────────────────── */}
      <div className="px-6 py-5 border-b border-white/5"
           style={{ background: sevCfg.bg }}>
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-4">
            <div className="text-4xl">{sevCfg.icon}</div>
            <div>
              <h3 className="text-xl font-extrabold text-white leading-none mb-1">
                Multi-Gene Risk Overview
              </h3>
              <p className="text-sm" style={{ color: sevCfg.text }}>
                Overall Severity: <strong>{sevCfg.label}</strong>
                {' '}· Patient: <span className="font-mono">{report.patient_id}</span>
              </p>
            </div>
          </div>

          {/* Summary counts */}
          <div className="flex items-center gap-3 flex-wrap">
            {highRisk.length > 0 && (
              <div className="text-center px-4 py-2 rounded-xl risk-toxic">
                <p className="text-2xl font-extrabold">{highRisk.length}</p>
                <p className="text-xs font-bold">High Risk</p>
              </div>
            )}
            {adjustRisk.length > 0 && (
              <div className="text-center px-4 py-2 rounded-xl risk-adjust">
                <p className="text-2xl font-extrabold">{adjustRisk.length}</p>
                <p className="text-xs font-bold">Adjust</p>
              </div>
            )}
            {safeGenes.length > 0 && (
              <div className="text-center px-4 py-2 rounded-xl risk-safe">
                <p className="text-2xl font-extrabold">{safeGenes.length}</p>
                <p className="text-xs font-bold">Safe</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Gene Matrix Grid ─────────────────────────────────────────────────── */}
      <div className="p-5">
        <p className="text-xs text-gray-500 uppercase tracking-widest mb-4">
          Pharmacogenomic Profile — All 6 Genes
        </p>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {report.genes_assessed.map(entry => (
            <GeneCellComponent key={entry.gene} entry={entry} />
          ))}
        </div>
      </div>

      {/* ── High-Risk Drug Alerts ────────────────────────────────────────────── */}
      {highRisk.length > 0 && (
        <div className="px-5 pb-5">
          <div className="rounded-xl border border-red-500/20 bg-red-950/20 p-4">
            <div className="flex items-start gap-3">
              <span className="text-red-400 text-xl mt-0.5">⚠</span>
              <div>
                <p className="text-red-400 font-bold text-sm mb-2">Drugs Requiring Immediate Attention</p>
                <div className="flex flex-wrap gap-2">
                  {highRisk.map(g => g.risk_drugs.map(drug => (
                    <span key={`${g.gene}-${drug}`}
                          className="px-3 py-1 text-xs font-bold rounded-lg risk-toxic">
                      {drug} ({g.gene})
                    </span>
                  )))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Footer Metrics ───────────────────────────────────────────────────── */}
      <div className="px-5 pb-5 border-t border-white/5 pt-4">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            {
              label: 'Genes Assessed',
              value: `${report.genes_assessed.length} / 6`,
              ok: true
            },
            {
              label: 'VCF Parsed',
              value: report.vcf_parsing_success ? '✓ Success' : '✗ Failed',
              ok: report.vcf_parsing_success
            },
            {
              label: 'Novel Variants',
              value: report.novel_variants_count > 0
                ? `${report.novel_variants_count} Flagged`
                : 'None',
              ok: report.novel_variants_count === 0
            },
            {
              label: 'Guideline',
              value: 'CPIC v2.0',
              ok: true
            },
          ].map(({ label, value, ok }) => (
            <div key={label} className="bg-gray-900/50 rounded-lg p-3 text-center">
              <p className="text-xs text-gray-500 mb-1">{label}</p>
              <p className={`text-sm font-bold ${ok ? 'text-emerald-400' : 'text-red-400'}`}>
                {value}
              </p>
            </div>
          ))}
        </div>

        {/* Warnings */}
        {report.warnings && report.warnings.length > 0 && (
          <div className="mt-3 space-y-1">
            {report.warnings.slice(0, 3).map((w, i) => (
              <p key={i} className="text-xs text-amber-400/70 flex items-start gap-1">
                <span className="mt-0.5 flex-shrink-0">⚠</span>
                <span>{w}</span>
              </p>
            ))}
            {report.warnings.length > 3 && (
              <p className="text-xs text-gray-600">
                +{report.warnings.length - 3} more warnings
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default ConsolidatedMatrix;
