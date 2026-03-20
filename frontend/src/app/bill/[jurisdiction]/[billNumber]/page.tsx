'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import ImpactCard from '@/components/ImpactCard';
import { Loader2, Calendar, FileText, ArrowLeft } from 'lucide-react';
import Link from 'next/link';
import { getBill } from '@/lib/api';

export default function BillDetailPage() {
    const params = useParams();
    const jurisdiction = params.jurisdiction as string;
    const billNumber = params.billNumber as string;

    const [bill, setBill] = useState<any>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const loadBill = async () => {
            try {
                const data = await getBill(jurisdiction, billNumber);
                // Map backend snake_case to frontend camelCase if needed
                const mappedBill = {
                    ...data,
                    impacts: data.impacts?.map((imp: any) => ({
                        ...imp,
                        impactNumber: imp.impact_number,
                        clause: imp.relevant_clause,
                        description: imp.description || imp.impact_description,
                        confidence: imp.confidence_score != null ? Number(imp.confidence_score) : null,
                        p10: imp.p10 != null ? Number(imp.p10) : null,
                        p25: imp.p25 != null ? Number(imp.p25) : null,
                        p50: imp.p50 != null ? Number(imp.p50) : null,
                        p75: imp.p75 != null ? Number(imp.p75) : null,
                        p90: imp.p90 != null ? Number(imp.p90) : null,
                        isQuantified: imp.p50 != null,
                        chainOfCausality: imp.chain_of_causality,
                    }))
                };
                setBill(mappedBill);
            } catch (err) {
                console.error("Failed to load bill:", err);
                setBill(null);
            } finally {
                setLoading(false);
            }
        };

        if (jurisdiction && billNumber) {
            loadBill();
        }
    }, [jurisdiction, billNumber]);

    if (loading) {
        return (
            <div className="flex min-h-screen bg-white">
                <main className="flex-1 p-8 flex items-center justify-center">
                    <div className="flex flex-col items-center">
                        <Loader2 className="w-10 h-10 text-prism-cyan animate-spin mb-4" />
                        <p className="text-slate-500">Loading bill details...</p>
                    </div>
                </main>
            </div>
        );
    }

    if (!bill) {
        return (
            <div className="flex min-h-screen bg-white">
                <main className="flex-1 p-8">
                    <div className="max-w-7xl mx-auto">
                        <p className="text-slate-500">Bill not found</p>
                    </div>
                </main>
            </div>
        );
    }

    const quantifiedImpacts = bill.impacts?.filter((imp: any) => imp.p50 != null) || [];
    const totalImpact = quantifiedImpacts.reduce((sum: number, imp: any) => sum + (imp.p50 || 0), 0);
    const allConfidences = bill.impacts?.filter((imp: any) => imp.confidence != null).map((imp: any) => imp.confidence) || [];
    const avgConfidence = allConfidences.length > 0
        ? allConfidences.reduce((sum: number, c: number) => sum + c, 0) / allConfidences.length
        : 0;
    const isQuantified = quantifiedImpacts.length > 0;
    const sufficiencyState = bill.sufficiency_state || bill.sufficiencyState;
    const insufficiencyReason = bill.insufficiency_reason || bill.insufficiencyReason;

    return (
        <div className="max-w-7xl mx-auto">
            {/* Breadcrumb */}
            <div className="flex items-center gap-2 text-sm text-slate-500 mb-4">
                <Link href={`/dashboard/${jurisdiction}`} className="hover:text-slate-900 flex items-center gap-1">
                    <ArrowLeft className="w-3 h-3" />
                    Back to Search
                </Link>
                <span>/</span>
                <span className="text-prism-cyan font-medium">{bill.bill_number} Analysis</span>
            </div>

            {/* Header */}
            <div className="card-prism p-6 mb-6">
                <div className="flex flex-col md:flex-row md:items-start justify-between gap-6">
                    <div className="flex-1">
                        <div className="flex items-center gap-3 mb-4">
                            <span className="px-2 py-1 text-xs font-medium bg-prism-cyan/10 text-prism-cyan rounded uppercase">
                                {bill.jurisdiction}
                            </span>
                            <span className="px-2 py-1 text-xs font-medium bg-slate-100 text-slate-600 rounded uppercase">
                                {bill.status || 'Active'}
                            </span>
                        </div>
                        <h1 className="text-2xl font-bold text-slate-900 mb-3 leading-tight">
                            {bill.title}
                        </h1>
                        <div className="flex items-center gap-2 text-slate-500 text-sm">
                            <Calendar className="w-4 h-4" />
                            <span>Introduced: {bill.introduced_date ? new Date(bill.introduced_date).toLocaleDateString() : 'N/A'}</span>
                        </div>
                    </div>

                    {/* Stats Cards */}
                    <div className="flex gap-4">
                        <div className="kpi-card min-w-[140px]">
                            <span className="label-uppercase text-slate-500 block mb-1">Total Annual Cost</span>
                            <p className="text-2xl font-numbers font-bold text-slate-900">
                                {isQuantified ? `$${totalImpact.toLocaleString()}` : 'N/A'}
                            </p>
                        </div>
                        <div className="kpi-card min-w-[140px]">
                            <span className="label-uppercase text-slate-500 block mb-1">Confidence</span>
                            <p className="text-2xl font-numbers font-bold text-slate-900">
                                {avgConfidence > 0 ? `${Math.round(avgConfidence * 100)}%` : 'N/A'}
                            </p>
                        </div>
                        {bill.effective_date && (
                            <div className="kpi-card min-w-[140px]">
                                <span className="label-uppercase text-slate-500 block mb-1">Effective Date</span>
                                <p className="text-lg font-numbers font-bold text-slate-900">
                                    {new Date(bill.effective_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                                </p>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Insufficiency Banner */}
            {!isQuantified && (sufficiencyState === 'research_incomplete' || sufficiencyState === 'insufficient_evidence') && (
                <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded-lg">
                    <p className="text-sm font-medium text-amber-800">
                        {sufficiencyState === 'research_incomplete' ? 'Research Incomplete' : 'Insufficient Evidence'}
                    </p>
                    {insufficiencyReason && (
                        <p className="text-sm text-amber-700 mt-1">{insufficiencyReason}</p>
                    )}
                </div>
            )}
            {!isQuantified && sufficiencyState === 'qualitative_only' && (
                <div className="mb-6 p-4 bg-slate-50 border border-slate-200 rounded-lg">
                    <p className="text-sm font-medium text-slate-700">Qualitative Analysis Only</p>
                    <p className="text-sm text-slate-500 mt-1">
                        {insufficiencyReason || 'This bill has not been quantified due to insufficient Tier A (official) evidence sources.'}
                    </p>
                </div>
            )}
            {isQuantified && sufficiencyState && (
                <div className="mb-6 p-3 bg-prism-green/5 border border-prism-green/20 rounded-lg">
                    <p className="text-sm font-medium text-prism-green">Quantified</p>
                    <p className="text-xs text-slate-500 mt-1">Cost estimates derived from official evidence sources with confidence scoring.</p>
                </div>
            )}

            {/* Main Content Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Left Column - Legislative Text */}
                <div className="lg:col-span-1">
                    <div className="card-prism p-6 sticky top-6">
                        <div className="flex items-center gap-2 mb-4">
                            <FileText className="w-4 h-4 text-prism-cyan" />
                            <span className="label-uppercase text-slate-900">Legislative Text</span>
                        </div>

                        {bill.full_text ? (
                            <div className="prose prose-sm max-w-none text-slate-700 max-h-[600px] overflow-y-auto pr-2">
                                <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed">{bill.full_text}</pre>
                            </div>
                        ) : (
                            <div className="text-slate-400 text-sm py-8 text-center">
                                <FileText className="w-8 h-8 mx-auto mb-2 opacity-50" />
                                <p>No bill text available</p>
                            </div>
                        )}
                    </div>
                </div>

                {/* Right Column - Impact Analysis */}
                <div className="lg:col-span-2 space-y-6">
                    {/* Sector Breakdown — only when quantified */}
                    {isQuantified && (
                    <div className="card-prism p-6">
                        <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center gap-2">
                                <div className="w-2 h-2 rounded-full bg-prism-cyan" />
                                <span className="label-uppercase text-slate-900">Impact Summary</span>
                            </div>
                        </div>

                        <div className="space-y-3">
                            {quantifiedImpacts.map((imp: any) => {
                                const maxP50 = Math.max(...quantifiedImpacts.map((i: any) => Math.abs(i.p50 || 0)), 1);
                                const widthPct = Math.round((Math.abs(imp.p50 || 0) / maxP50) * 100);
                                const barColor = (imp.p50 || 0) >= 0 ? 'bg-prism-cyan' : 'bg-prism-pink';
                                return (
                                    <div key={imp.impactNumber}>
                                        <div className="flex items-center justify-between text-sm">
                                            <span className="text-slate-600 truncate max-w-[70%]">{imp.description || `Impact #${imp.impactNumber}`}</span>
                                            <span className={`font-numbers font-medium text-slate-900 ${(imp.p50 || 0) >= 0 ? '' : 'text-prism-pink'}`}>
                                                {imp.p50 >= 0 ? '+' : ''}${(imp.p50 || 0).toLocaleString()}
                                            </span>
                                        </div>
                                        <div className="h-6 bg-slate-100 rounded overflow-hidden mt-1">
                                            <div className={`h-full ${barColor}`} style={{ width: `${widthPct}%` }} />
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                    )}

                    {/* Impact Cards */}
                    <div>
                        <h3 className="label-uppercase text-slate-900 mb-4">Detailed Impacts</h3>
                        <div className="space-y-4">
                            {bill.impacts?.map((impact: any) => (
                                <ImpactCard key={impact.impactNumber} impact={impact} />
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
