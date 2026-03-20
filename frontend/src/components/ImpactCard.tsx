'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp, ExternalLink, Quote } from 'lucide-react';

interface Evidence {
    source_name: string;
    url: string;
    excerpt: string;
}

interface ImpactProps {
    impactNumber: number;
    description: string;
    clause: string;
    confidence: number | null;
    p10: number | null;
    p25: number | null;
    p50: number | null;
    p75: number | null;
    p90: number | null;
    isQuantified?: boolean;
    evidence?: Evidence[];
    chainOfCausality?: string;
}

export default function ImpactCard({ impact }: { impact: ImpactProps }) {
    const isQuantified = impact.isQuantified ?? (impact.p50 != null);
    const [selectedPercentile, setSelectedPercentile] = useState(50);
    const [currentCost, setCurrentCost] = useState(isQuantified ? (impact.p50 ?? 0) : 0);
    const [isChainOpen, setIsChainOpen] = useState(false);
    const [isEvidenceOpen, setIsEvidenceOpen] = useState(false);

    const safeP = (v: number | null) => (v != null && !isNaN(v) ? v : 0);

    const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const val = parseInt(e.target.value);
        setSelectedPercentile(val);

        if (!isQuantified) return;
        const p10 = safeP(impact.p10), p25 = safeP(impact.p25), p50 = safeP(impact.p50), p75 = safeP(impact.p75), p90 = safeP(impact.p90);
        if (val <= 10) setCurrentCost(p10);
        else if (val <= 25) {
            const ratio = (val - 10) / 15;
            setCurrentCost(p10 + ratio * (p25 - p10));
        } else if (val <= 50) {
            const ratio = (val - 25) / 25;
            setCurrentCost(p25 + ratio * (p50 - p25));
        } else if (val <= 75) {
            const ratio = (val - 50) / 25;
            setCurrentCost(p50 + ratio * (p75 - p50));
        } else if (val <= 90) {
            const ratio = (val - 75) / 15;
            setCurrentCost(p75 + ratio * (p90 - p75));
        } else {
            setCurrentCost(p90);
        }
    };

    const getConfidenceColor = (conf: number | null) => {
        if (conf == null || isNaN(conf)) return 'bg-slate-100 text-slate-500 border-slate-200';
        if (conf > 0.8) return 'bg-prism-green/10 text-prism-green border-prism-green/30';
        if (conf > 0.6) return 'bg-prism-yellow/10 text-prism-yellow border-prism-yellow/30';
        return 'bg-prism-pink/10 text-prism-pink border-prism-pink/30';
    };

    const formatConfidence = (conf: number | null): string => {
        if (conf == null || isNaN(conf) || conf === 0) return 'N/A';
        return `${Math.round(conf * 100)}%`;
    };

    return (
        <div className="card-prism p-6 transition-all hover:shadow-md">
            {/* Header */}
            <div className="flex justify-between items-start mb-4">
                <div>
                    <div className="flex items-center gap-2 mb-1">
                        <span className="label-uppercase text-slate-500">Impact #{impact.impactNumber}</span>
                    </div>
                    <div className="flex items-baseline gap-2">
                        {isQuantified ? (
                            <>
                                <span className="text-3xl font-numbers font-bold text-slate-900">
                                    ${Math.round(currentCost).toLocaleString()}
                                </span>
                                <span className="text-sm text-slate-500">/year</span>
                            </>
                        ) : (
                            <span className="text-lg font-medium text-slate-400 italic">
                                Qualitative only
                            </span>
                        )}
                    </div>
                </div>
                <span className={`px-3 py-1 rounded text-xs font-semibold border ${getConfidenceColor(impact.confidence)}`}>
                    {formatConfidence(impact.confidence)} Confidence
                </span>
            </div>

            {/* Description */}
            <div className="mb-4">
                <p className="text-slate-700 leading-relaxed">{impact.description}</p>
            </div>

            {/* Relevant Clause */}
            <div className="mb-4 p-4 bg-slate-50 border border-slate-200 rounded">
                <div className="flex items-center gap-2 mb-2">
                    <Quote className="w-4 h-4 text-prism-cyan" />
                    <span className="label-uppercase text-slate-500">Relevant Clause</span>
                </div>
                <p className="italic text-slate-600 text-sm leading-relaxed">&ldquo;{impact.clause}&rdquo;</p>
            </div>

            {/* Chain of Causality */}
            {impact.chainOfCausality && (
                <div className="mb-4 border border-slate-200 rounded overflow-hidden">
                    <button
                        onClick={() => setIsChainOpen(!isChainOpen)}
                        className="w-full flex items-center justify-between p-3 bg-slate-50 hover:bg-slate-100 transition-colors text-left"
                    >
                        <span className="font-medium text-slate-700 text-sm">Chain of Causality</span>
                        {isChainOpen ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
                    </button>
                    {isChainOpen && (
                        <div className="p-3 text-sm text-slate-600 border-t border-slate-200">
                            {impact.chainOfCausality}
                        </div>
                    )}
                </div>
            )}

            {/* Evidence */}
            {impact.evidence && impact.evidence.length > 0 && (
                <div className="mb-4 border border-slate-200 rounded overflow-hidden">
                    <button
                        onClick={() => setIsEvidenceOpen(!isEvidenceOpen)}
                        className="w-full flex items-center justify-between p-3 bg-slate-50 hover:bg-slate-100 transition-colors text-left"
                    >
                        <span className="font-medium text-slate-700 text-sm">Evidence ({impact.evidence.length} sources)</span>
                        {isEvidenceOpen ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
                    </button>
                    {isEvidenceOpen && (
                        <div className="p-3 space-y-3 border-t border-slate-200">
                            {impact.evidence.map((ev, idx) => {
                                const hasValidUrl = ev.url && ev.url.startsWith('http');
                                return (
                                    <div key={idx} className="pl-3 border-l-2 border-prism-cyan">
                                        {hasValidUrl ? (
                                            <a
                                                href={ev.url}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="flex items-center gap-1 text-sm font-medium text-prism-cyan hover:text-prism-cyan/80 transition-colors"
                                            >
                                                {ev.source_name || 'Source'} <ExternalLink className="w-3 h-3" />
                                            </a>
                                        ) : (
                                            <span className="text-sm font-medium text-slate-600">
                                                {ev.source_name || 'Source unavailable'}
                                            </span>
                                        )}
                                        {ev.excerpt && (
                                            <p className="text-xs text-slate-500 mt-1 italic">&ldquo;{ev.excerpt}&rdquo;</p>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>
            )}

            {/* Percentile Slider - only when quantified */}
            {isQuantified && (
                <div className="pt-4 border-t border-slate-200">
                    <div className="flex justify-between text-xs font-medium text-slate-500 mb-2">
                        <span>Conservative (10%)</span>
                        <span>Worst Case (90%)</span>
                    </div>
                    <input
                        type="range"
                        min="10"
                        max="90"
                        step="1"
                        value={selectedPercentile}
                        onChange={handleSliderChange}
                        className="w-full h-2 bg-slate-200 rounded appearance-none cursor-pointer accent-prism-cyan"
                    />
                    <div className="flex justify-between text-xs text-slate-400 mt-2 font-numbers">
                        <span>${safeP(impact.p10).toLocaleString()}</span>
                        <span className="font-semibold text-prism-cyan">${safeP(impact.p50).toLocaleString()}</span>
                        <span>${safeP(impact.p90).toLocaleString()}</span>
                    </div>
                    <p className="text-center mt-3 text-sm text-slate-600">
                        Selected: <span className="font-semibold text-prism-cyan">{selectedPercentile}th Percentile</span>
                    </p>
                </div>
            )}
            {!isQuantified && (
                <div className="pt-4 border-t border-slate-200">
                    <p className="text-sm text-slate-400 italic">
                        Insufficient evidence for cost quantification. This analysis is qualitative only.
                    </p>
                </div>
            )}
        </div>
    );
}
