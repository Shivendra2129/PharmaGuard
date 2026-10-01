'use client';

import React, { useState } from 'react';

interface JsonViewerProps {
    data: object;
    title?: string;
}

function syntaxHighlight(json: string): string {
    return json
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(
            /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g,
            (match) => {
                let cls = 'text-amber-300'; // number
                if (/^"/.test(match)) {
                    if (/:$/.test(match)) {
                        cls = 'text-sky-400'; // key
                    } else {
                        cls = 'text-emerald-300'; // string
                    }
                } else if (/true|false/.test(match)) {
                    cls = 'text-indigo-400'; // boolean
                } else if (/null/.test(match)) {
                    cls = 'text-gray-500'; // null
                }
                return `<span class="${cls}">${match}</span>`;
            }
        );
}

const JsonViewer: React.FC<JsonViewerProps> = ({ data, title = 'JSON Output' }) => {
    const [copied, setCopied] = useState(false);

    const jsonString = JSON.stringify(data, null, 2);
    const highlighted = syntaxHighlight(jsonString);

    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(jsonString);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch {
            // Fallback
            const ta = document.createElement('textarea');
            ta.value = jsonString;
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        }
    };

    const handleDownload = () => {
        const blob = new Blob([jsonString], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'report.json';
        a.click();
        URL.revokeObjectURL(url);
    };

    return (
        <div className="glass-card rounded-2xl overflow-hidden border border-white/5">
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-white/5 bg-gray-900/40">
                <div className="flex items-center gap-3">
                    <div className="flex gap-1.5">
                        <div className="w-3 h-3 rounded-full bg-red-500/70"></div>
                        <div className="w-3 h-3 rounded-full bg-yellow-500/70"></div>
                        <div className="w-3 h-3 rounded-full bg-green-500/70"></div>
                    </div>
                    <span className="text-sm font-mono text-gray-400">{title}</span>
                </div>
                <div className="flex gap-2">
                    <button
                        id="copy-json-btn"
                        onClick={handleCopy}
                        className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all duration-200
              bg-indigo-600/20 hover:bg-indigo-600/40 border border-indigo-500/30 text-indigo-300"
                    >
                        {copied ? (
                            <>
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                </svg>
                                Copied!
                            </>
                        ) : (
                            <>
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                                </svg>
                                Copy JSON
                            </>
                        )}
                    </button>
                    <button
                        id="download-json-btn"
                        onClick={handleDownload}
                        className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all duration-200
              bg-emerald-600/20 hover:bg-emerald-600/40 border border-emerald-500/30 text-emerald-300"
                    >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        Download report.json
                    </button>
                </div>
            </div>

            {/* JSON Content */}
            <div className="overflow-auto max-h-96 p-5 bg-gray-950/60">
                <pre
                    className="text-xs font-mono leading-relaxed whitespace-pre"
                    dangerouslySetInnerHTML={{ __html: highlighted }}
                />
            </div>

            {/* Footer */}
            <div className="px-5 py-3 bg-gray-900/30 border-t border-white/5 flex justify-between items-center">
                <span className="text-xs text-gray-600 font-mono">
                    {jsonString.length.toLocaleString()} characters
                </span>
                <span className="text-xs text-gray-600 font-mono">
                    Pharmacogenomics Schema v2.0
                </span>
            </div>
        </div>
    );
};

export default JsonViewer;
