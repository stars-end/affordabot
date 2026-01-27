'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { useUser } from '@clerk/nextjs';
import SummaryDashboard from '@/components/SummaryDashboard';
import ImpactCard from '@/components/ImpactCard';
import { getLegislation, scrapeJurisdiction } from '@/lib/api';
import { Loader2, RefreshCw, ArrowLeft, FileText } from 'lucide-react';

const JURISDICTION_NAMES: Record<string, string> = {
    'california': 'California State',
    'santa-clara-county': 'Santa Clara County',
    'san-jose': 'San Jose City',
    'saratoga': 'Saratoga City'
};

export default function DashboardPage() {
    const params = useParams();
    const jurisdictionId = params.jurisdiction as string;
    const jurisdictionName = JURISDICTION_NAMES[jurisdictionId] || jurisdictionId;
    const { isSignedIn } = useUser();

    const [loading, setLoading] = useState(false);
    const [scraping, setScraping] = useState(false);
    const [legislation, setLegislation] = useState<any[]>([]);
    const [selectedBill, setSelectedBill] = useState<any | null>(null);
    const [view, setView] = useState<'summary' | 'detail'>('summary');

    useEffect(() => {
        loadLegislation();
    }, [jurisdictionId]);

    const loadLegislation = async () => {
        setLoading(true);
        try {
            const data = await getLegislation(jurisdictionId as any);
            setLegislation(data.legislation || []);
        } catch (err) {
            console.error('Failed to load legislation:', err);
            setLegislation([]);
        } finally {
            setLoading(false);
        }
    };

    const handleScrape = async () => {
        setScraping(true);
        try {
            await scrapeJurisdiction(jurisdictionId as any);
            await loadLegislation();
        } catch (err) {
            console.error('Scraping failed:', err);
        } finally {
            setScraping(false);
        }
    };

    const billsSummary = legislation.map((leg) => ({
        id: leg.bill_number,
        bill_number: leg.bill_number,
        title: leg.title,
        total_impact: leg.impacts?.reduce((sum: number, imp: any) => sum + (imp.p50 || 0), 0) || 0,
        avg_confidence: leg.impacts?.length > 0
            ? leg.impacts.reduce((sum: number, imp: any) => sum + (Number(imp.confidence_score) || 0), 0) / leg.impacts.length
            : 0,
        impact_count: leg.impacts?.length || 0,
    }));

    return (
        <div className="max-w-7xl mx-auto">
            {/* Breadcrumb */}
            <div className="flex items-center gap-2 text-sm text-slate-500 mb-4">
                <span>TOOLS</span>
                <span>/</span>
                <span className="text-slate-900 font-medium">MAIN DASHBOARD</span>
                <span>/</span>
                <span className="text-slate-900 font-medium uppercase">{jurisdictionId.replace(/-/g, '_')}_ANALYSIS_V1</span>
            </div>

            {/* Header */}
            <div className="mb-8 flex justify-between items-end">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900">{jurisdictionName} Dashboard</h1>
                    <p className="mt-1 text-slate-500">Real-time affordability impact analysis</p>
                </div>

                <div className="flex items-center gap-4">
                    {/* System Status */}
                    <div className="flex items-center gap-2 px-3 py-1.5 bg-prism-green/10 border border-prism-green/30 rounded">
                        <div className="w-2 h-2 rounded-full bg-prism-green animate-pulse" />
                        <span className="text-xs font-medium text-prism-green uppercase tracking-wider">System Online</span>
                    </div>

                    {/* Export Button */}
                    <button className="btn-primary">
                        Export Analysis
                    </button>
                </div>
            </div>

            {/* Content */}
            {loading ? (
                <div className="flex flex-col items-center justify-center py-20 card-prism">
                    <Loader2 className="w-10 h-10 text-prism-cyan animate-spin mb-4" />
                    <p className="text-slate-500">Loading legislation data...</p>
                </div>
            ) : view === 'summary' ? (
                <SummaryDashboard
                    bills={billsSummary}
                    jurisdiction={jurisdictionName}
                    onSelectBill={(billId) => {
                        const bill = legislation.find(l => l.bill_number === billId);
                        if (bill) {
                            setSelectedBill(bill);
                            setView('detail');
                        }
                    }}
                />
            ) : selectedBill ? (
                <div className="space-y-6">
                    {/* Back button */}
                    <button
                        onClick={() => {
                            setSelectedBill(null);
                            setView('summary');
                        }}
                        className="flex items-center gap-2 text-sm text-slate-600 hover:text-slate-900 transition-colors"
                    >
                        <ArrowLeft className="w-4 h-4" />
                        Back to Summary
                    </button>

                    {/* Bill Header */}
                    <div className="card-prism p-6">
                        <div className="flex items-start justify-between gap-6">
                            <div className="flex-1">
                                <div className="flex items-center gap-3 mb-3">
                                    <span className="px-2 py-1 text-xs font-medium bg-prism-cyan/10 text-prism-cyan rounded">
                                        {jurisdictionId}
                                    </span>
                                    <span className="px-2 py-1 text-xs font-medium bg-slate-100 text-slate-600 rounded">
                                        {selectedBill.status || 'Active'}
                                    </span>
                                </div>
                                <h2 className="text-xl font-bold text-slate-900 mb-2">{selectedBill.title}</h2>
                                <p className="text-sm text-slate-500">
                                    Bill #{selectedBill.bill_number} • Last updated: {new Date().toLocaleDateString()}
                                </p>
                            </div>

                            {/* Stats */}
                            <div className="flex gap-6">
                                <div className="text-right">
                                    <p className="label-uppercase text-slate-500 mb-1">Total Annual Cost</p>
                                    <p className="text-2xl font-numbers font-bold text-slate-900">
                                        ${selectedBill.impacts?.reduce((sum: number, imp: any) => sum + (imp.p50 || 0), 0).toLocaleString() || 0}
                                    </p>
                                </div>
                                <div className="text-right">
                                    <p className="label-uppercase text-slate-500 mb-1">Impact Score</p>
                                    <p className="text-2xl font-numbers font-bold text-slate-900">
                                        {selectedBill.impacts?.length > 0
                                            ? (selectedBill.impacts.reduce((sum: number, imp: any) => sum + (Number(imp.confidence_score) || 0), 0) / selectedBill.impacts.length * 10).toFixed(1)
                                            : '0.0'}/10
                                    </p>
                                </div>
                                <div className="text-right">
                                    <p className="label-uppercase text-slate-500 mb-1">Effective Date</p>
                                    <p className="text-2xl font-numbers font-bold text-slate-900">
                                        {selectedBill.effective_date
                                            ? new Date(selectedBill.effective_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
                                            : 'TBD'}
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Legislative Text Section */}
                    {selectedBill.full_text && (
                        <div className="card-prism p-6">
                            <div className="flex items-center justify-between mb-4">
                                <div className="flex items-center gap-2">
                                    <FileText className="w-4 h-4 text-prism-cyan" />
                                    <span className="label-uppercase text-slate-900">Legislative Text</span>
                                </div>
                            </div>
                            <div className="prose prose-sm max-w-none text-slate-700 max-h-96 overflow-y-auto pr-4">
                                <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed">{selectedBill.full_text}</pre>
                            </div>
                        </div>
                    )}

                    {/* Impact Cards */}
                    <div className="grid gap-4">
                        <h3 className="label-uppercase text-slate-900">Impact Analysis</h3>
                        {selectedBill.impacts?.map((impact: any) => (
                            <ImpactCard
                                key={impact.id}
                                impact={{
                                    impactNumber: impact.impact_number,
                                    description: impact.description,
                                    clause: impact.relevant_clause,
                                    confidence: Number(impact.confidence_score) || 0,
                                    p10: impact.p10,
                                    p25: impact.p25,
                                    p50: impact.p50,
                                    p75: impact.p75,
                                    p90: impact.p90,
                                    evidence: impact.evidence,
                                    chainOfCausality: impact.chain_of_causality,
                                }}
                            />
                        ))}
                    </div>
                </div>
            ) : null}
        </div>
    );
}
