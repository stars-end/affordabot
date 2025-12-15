'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp, ExternalLink, Info, Quote } from 'lucide-react';

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
        if (conf > 0.8) return 'bg-emerald-100 text-emerald-700 border-emerald-200';
        if (conf > 0.6) return 'bg-yellow-100 text-yellow-700 border-yellow-200';
        return 'bg-orange-100 text-orange-700 border-orange-200';
    };

    return (
        <div className="max-w-3xl mx-auto my-4 p-6 rounded-2xl bg-white/10 backdrop-blur-md border border-white/20 shadow-xl transition-all hover:shadow-2xl hover:bg-white/20">
            <div className="flex justify-between items-start mb-4">
                <div>
                    <h3 className="text-lg font-bold text-purple-900">Impact #{impact.impactNumber}</h3>
                    <div className="mt-1 flex items-baseline gap-2">
                        <span className="text-3xl font-bold text-gray-900">
                            ${Math.round(currentCost).toLocaleString()}
                        </span>
                        <span className="text-sm text-gray-500 font-normal">/year</span>
                    </div>
                </div>
                <span className={`px-3 py-1 rounded-full text-xs font-bold border ${getConfidenceColor(impact.confidence)}`}>
                    {Math.round(impact.confidence * 100)}% Confidence
                </span>
            </div>

            <div className="mb-6">
                <h4 className="text-sm font-medium text-gray-500 mb-1">Description</h4>
                <p className="text-gray-800 leading-relaxed">{impact.description}</p>
            </div>

            <div className="mb-6 bg-white/30 p-4 rounded-xl border border-white/20">
                <div className="flex items-center gap-2 mb-2">
                    <Quote className="w-4 h-4 text-purple-500" />
                    <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wide">Relevant Clause</h4>
                </div>
                <p className="italic text-gray-700 text-sm leading-relaxed">&quot;{impact.clause}&quot;</p>
            </div>

            {/* Chain of Causality */}
            {impact.chainOfCausality && (
                <div className="mb-4 border border-white/20 rounded-xl overflow-hidden bg-white/5">
                    <button
                        onClick={() => setIsChainOpen(!isChainOpen)}
                        className="w-full flex items-center justify-between p-4 hover:bg-white/10 transition-colors text-left"
                    >
                        <span className="font-medium text-gray-800">Chain of Causality</span>
                        {isChainOpen ? <ChevronUp className="w-4 h-4 text-gray-500" /> : <ChevronDown className="w-4 h-4 text-gray-500" />}
                    </button>
                    {isChainOpen && (
                        <div className="p-4 pt-0 text-sm text-gray-600 border-t border-white/10">
                            {impact.chainOfCausality}
                        </div>
                    )}
                </div>
            )}

            {/* Evidence */}
            {impact.evidence && impact.evidence.length > 0 && (
                <div className="mb-6 border border-white/20 rounded-xl overflow-hidden bg-white/5">
                    <button
                        onClick={() => setIsEvidenceOpen(!isEvidenceOpen)}
                        className="w-full flex items-center justify-between p-4 hover:bg-white/10 transition-colors text-left"
                    >
                        <span className="font-medium text-gray-800">Evidence ({impact.evidence.length} sources)</span>
                        {isEvidenceOpen ? <ChevronUp className="w-4 h-4 text-gray-500" /> : <ChevronDown className="w-4 h-4 text-gray-500" />}
                    </button>
                    {isEvidenceOpen && (
                        <div className="p-4 pt-0 space-y-4 border-t border-white/10">
                            {impact.evidence.map((ev, idx) => (
                                <div key={idx} className="pl-4 border-l-2 border-purple-400">
                                    <a
                                        href={ev.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="flex items-center gap-1 text-sm font-bold text-purple-600 hover:text-purple-800 transition-colors"
                                    >
                                        {ev.source_name} <ExternalLink className="w-3 h-3" />
                                    </a>
                                    <p className="text-xs text-gray-600 mt-1 italic">&quot;{ev.excerpt}&quot;</p>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* Percentile Slider */}
            <div className="mt-6 pt-6 border-t border-white/20">
                <div className="flex justify-between text-sm font-medium text-gray-600 mb-2">
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
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-purple-600"
                />
                <div className="flex justify-between text-xs text-gray-500 mt-2">
                    <span>${impact.p10.toLocaleString()}</span>
                    <span className="font-bold text-purple-700 text-sm">${impact.p50.toLocaleString()}</span>
                    <span>${impact.p90.toLocaleString()}</span>
                </div>
                <p className="text-center mt-3 text-sm text-gray-600">
                    Selected: <span className="font-bold text-purple-700">{selectedPercentile}th Percentile</span>
                </p>
            </div>
        </div>
    );
}

