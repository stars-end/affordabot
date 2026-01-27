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
    confidence: number;
    p10: number;
    p25: number;
    p50: number;
    p75: number;
    p90: number;
    evidence?: Evidence[];
    chainOfCausality?: string;
}

export default function ImpactCard({ impact }: { impact: ImpactProps }) {
    const [selectedPercentile, setSelectedPercentile] = useState(50);
    const [currentCost, setCurrentCost] = useState(impact.p50);
    const [isChainOpen, setIsChainOpen] = useState(false);
    const [isEvidenceOpen, setIsEvidenceOpen] = useState(false);

    const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const val = parseInt(e.target.value);
        setSelectedPercentile(val);

        // Linear interpolation
        if (val <= 10) setCurrentCost(impact.p10);
        else if (val <= 25) {
            const ratio = (val - 10) / 15;
            setCurrentCost(impact.p10 + ratio * (impact.p25 - impact.p10));
        } else if (val <= 50) {
            const ratio = (val - 25) / 25;
            setCurrentCost(impact.p25 + ratio * (impact.p50 - impact.p25));
        } else if (val <= 75) {
            const ratio = (val - 50) / 25;
            setCurrentCost(impact.p50 + ratio * (impact.p75 - impact.p50));
        } else if (val <= 90) {
            const ratio = (val - 75) / 15;
            setCurrentCost(impact.p75 + ratio * (impact.p90 - impact.p75));
        } else {
            setCurrentCost(impact.p90);
        }
    };

    const getConfidenceColor = (conf: number) => {
        if (isNaN(conf) || conf === null || conf === undefined) return 'bg-slate-100 text-slate-500 border-slate-200';
        if (conf > 0.8) return 'bg-prism-green/10 text-prism-green border-prism-green/30';
        if (conf > 0.6) return 'bg-prism-yellow/10 text-prism-yellow border-prism-yellow/30';
        return 'bg-prism-pink/10 text-prism-pink border-prism-pink/30';
    };

    // Safe confidence display helper
    const formatConfidence = (conf: number): string => {
        if (isNaN(conf) || conf === null || conf === undefined || conf === 0) return 'N/A';
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
                        <span className="text-3xl font-numbers font-bold text-slate-900">
                            ${Math.round(currentCost).toLocaleString()}
                        </span>
                        <span className="text-sm text-slate-500">/year</span>
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

            {/* Percentile Slider */}
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
                    <span>${impact.p10.toLocaleString()}</span>
                    <span className="font-semibold text-prism-cyan">${impact.p50.toLocaleString()}</span>
                    <span>${impact.p90.toLocaleString()}</span>
                </div>
                <p className="text-center mt-3 text-sm text-slate-600">
                    Selected: <span className="font-semibold text-prism-cyan">{selectedPercentile}th Percentile</span>
                </p>
            </div>
        </div>
    );
}
