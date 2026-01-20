'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { useUser } from '@clerk/nextjs';
import { Sidebar } from '@/components/Sidebar';
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
        id: leg.bill_number, // Use bill_number as ID to prevent duplicate key issues
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
            {/* Header */}
            <div className="mb-8 flex justify-between items-end">
                <div>
                    <h1 className="text-3xl font-bold text-gray-800">{jurisdictionName} Dashboard</h1>
                    <p className="mt-1 text-gray-600">Real-time affordability impact analysis</p>
                </div>

                <div className="flex gap-3">
                    <button
                        onClick={() => setView('summary')}
                        className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${view === 'summary'
                            ? 'bg-purple-600 text-white shadow-lg shadow-purple-500/30'
                            : 'bg-white/50 text-gray-600 hover:bg-white/80'
                            }`}
                    >
                        Summary View
                    </button>
                    {/* P0 Security: Only show scrape button to authenticated users */}
                    {isSignedIn && (
                        <button
                            onClick={handleScrape}
                            disabled={scraping}
                            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-white/50 text-gray-600 hover:bg-white/80 transition-colors disabled:opacity-50"
                        >
                            {scraping ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                            {scraping ? 'Scraping...' : 'Scrape & Analyze'}
                        </button>
                    )}
                </div>
            </div>

            {/* Stats Card */}
            <div className="mb-8 p-6 rounded-2xl bg-white/10 backdrop-blur-md border border-white/20 shadow-xl">
                <div className="flex items-center gap-4">
                    <div className="p-3 rounded-xl bg-blue-100 text-blue-600">
                        <FileText className="w-6 h-6" />
                    </div>
                    <div>
                        <p className="text-sm font-medium text-gray-500">Analyzed Bills</p>
                        <p className="text-2xl font-bold text-gray-800">{legislation.length}</p>
                    </div>
                </div>
            </div>

            {/* Content */}
            {loading ? (
                <div className="flex flex-col items-center justify-center py-20 rounded-2xl bg-white/10 backdrop-blur-md border border-white/20">
                    <Loader2 className="w-10 h-10 text-purple-500 animate-spin mb-4" />
                    <p className="text-gray-500">Loading legislation data...</p>
                </div>
            ) : view === 'summary' ? (
                <SummaryDashboard
                    bills={billsSummary}
                    jurisdiction={jurisdictionName}
                    onSelectBill={(billId) => {
                        // billId is now bill_number
                        const bill = legislation.find(l => l.bill_number === billId);
                        if (bill) {
                            setSelectedBill(bill);
                            setView('detail');
                        }
                    }}
                />
            ) : selectedBill ? (
                <div className="space-y-6">
                    <button
                        onClick={() => {
                            setSelectedBill(null);
                            setView('summary');
                        }}
                        className="flex items-center gap-2 text-sm text-gray-600 hover:text-purple-600 transition-colors"
                    >
                        <ArrowLeft className="w-4 h-4" />
                        Back to Summary
                    </button>

                    <div className="p-6 rounded-2xl bg-white/10 backdrop-blur-md border border-white/20 shadow-xl">
                        <h2 className="text-2xl font-bold text-gray-800 mb-2">{selectedBill.title}</h2>
                        <div className="flex items-center gap-3">
                            <span className="px-3 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-700">
                                Bill #{selectedBill.bill_number}
                            </span>
                            <span className="text-sm text-gray-500">
                                Last updated: {new Date().toLocaleDateString()}
                            </span>
                        </div>
                    </div>

                    <div className="grid gap-6">
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

