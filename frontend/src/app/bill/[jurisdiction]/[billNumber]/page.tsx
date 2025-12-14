'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { Sidebar } from '@/components/Sidebar';
import ImpactCard from '@/components/ImpactCard';
import { Loader2, Share2, Copy, Twitter, Calendar, FileText, ArrowLeft } from 'lucide-react';
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
                        confidence: imp.confidence_factor,
                        chainOfCausality: imp.chain_of_causality
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
            <div className="flex min-h-screen bg-gradient-to-br from-purple-50 via-blue-50 to-teal-50">
                <Sidebar />
                <main className="flex-1 p-8 flex items-center justify-center">
                    <div className="flex flex-col items-center">
                        <Loader2 className="w-10 h-10 text-purple-500 animate-spin mb-4" />
                        <p className="text-gray-500">Loading bill details...</p>
                    </div>
                </main>
            </div>
        );
    }

    if (!bill) {
        return (
            <div className="flex min-h-screen bg-gradient-to-br from-purple-50 via-blue-50 to-teal-50">
                <Sidebar />
                <main className="flex-1 p-8">
                    <div className="max-w-7xl mx-auto">
                        <p className="text-gray-500">Bill not found</p>
                    </div>
                </main>
            </div>
        );
    }

    const totalImpact = bill.impacts?.reduce((sum: number, imp: any) => sum + imp.p50, 0) || 0;
    const avgConfidence = bill.impacts?.length > 0
        ? bill.impacts.reduce((sum: number, imp: any) => sum + imp.confidence, 0) / bill.impacts.length
        : 0;

    return (
        <div className="max-w-7xl mx-auto">
            <Link
                href={`/dashboard/${jurisdiction}`}
                className="inline-flex items-center gap-2 text-sm text-gray-600 hover:text-purple-600 transition-colors mb-6"
            >
                <ArrowLeft className="w-4 h-4" />
                Back to Dashboard
            </Link>

            {/* Header */}
            <div className="mb-8 p-8 rounded-2xl bg-white/10 backdrop-blur-md border border-white/20 shadow-xl">
                <div className="flex flex-col md:flex-row md:items-start justify-between gap-6">
                    <div className="flex-1">
                        <div className="flex items-center gap-3 mb-4">
                            <span className="px-3 py-1 rounded-full text-xs font-bold bg-blue-100 text-blue-700 uppercase tracking-wide">
                                {bill.jurisdiction}
                            </span>
                            <span className="px-3 py-1 rounded-full text-xs font-bold bg-gray-100 text-gray-700 uppercase tracking-wide">
                                {bill.status}
                            </span>
                        </div>
                        <h1 className="text-3xl font-bold text-gray-900 mb-3 leading-tight">
                            <span className="text-purple-700 mr-3">{bill.bill_number}:</span>
                            {bill.title}
                        </h1>
                        <div className="flex items-center gap-2 text-gray-500 text-sm">
                            <Calendar className="w-4 h-4" />
                            <span>Introduced: {new Date(bill.introduced_date).toLocaleDateString()}</span>
                        </div>
                    </div>

                    <div className="text-left md:text-right bg-white/30 p-4 rounded-xl border border-white/20 md:bg-transparent md:p-0 md:border-0">
                        <p className="text-sm font-medium text-gray-500 mb-1">Total Annual Impact</p>
                        <p className="text-4xl font-bold text-gray-900 mb-1">
                            ${totalImpact.toLocaleString()}
                        </p>
                        <div className="flex items-center md:justify-end gap-1.5">
                            <div className={`w-2 h-2 rounded-full ${avgConfidence > 0.8 ? 'bg-green-500' : 'bg-yellow-500'}`}></div>
                            <p className="text-xs font-medium text-gray-600">
                                {Math.round(avgConfidence * 100)}% confidence
                            </p>
                        </div>
                    </div>
                </div>
            </div>

            {/* Share Buttons */}
            <div className="mb-8 p-4 rounded-xl bg-white/40 border border-white/20 flex items-center justify-between">
                <p className="font-medium text-gray-700 flex items-center gap-2">
                    <Share2 className="w-4 h-4" />
                    Share this analysis
                </p>
                <div className="flex gap-3">
                    <button
                        onClick={() => {
                            navigator.clipboard.writeText(window.location.href);
                            alert('Link copied!');
                        }}
                        className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-white text-gray-700 hover:bg-gray-50 border border-gray-200 transition-colors shadow-sm"
                    >
                        <Copy className="w-4 h-4" />
                        Copy Link
                    </button>
                    <button
                        onClick={() => {
                            const text = `Check out this bill analysis: ${bill.bill_number} - $${totalImpact.toLocaleString()}/year impact`;
                            window.open(`https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${encodeURIComponent(window.location.href)}`, '_blank');
                        }}
                        className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-[#1DA1F2] text-white hover:bg-[#1a91da] transition-colors shadow-sm"
                    >
                        <Twitter className="w-4 h-4" />
                        Tweet
                    </button>
                </div>
            </div>

            {/* Impact Cards */}
            <div className="space-y-6 mb-12">
                <h2 className="text-xl font-bold text-gray-800 flex items-center gap-2">
                    <FileText className="w-5 h-5 text-purple-600" />
                    Detailed Impacts
                </h2>
                {bill.impacts?.map((impact: any) => (
                    <ImpactCard key={impact.impactNumber} impact={impact} />
                ))}
            </div>

            {/* Methodology */}
            <div className="p-8 rounded-2xl bg-gray-50 border border-gray-200">
                <h3 className="text-lg font-bold text-gray-900 mb-3">Methodology</h3>
                <p className="text-gray-600 leading-relaxed mb-4">
                    AffordaBot uses AI (GPT-4o/Claude) to analyze legislation text and estimate cost-of-living impacts.
                    All estimates are evidence-based and cite specific sources. Cost distributions (p10-p90) represent
                    uncertainty ranges based on family size, income level, and other factors.
                </p>
                <p className="text-sm text-gray-500 italic">
                    This analysis is for informational purposes only and should not be considered financial or legal advice.
                </p>
            </div>
        </div>
    );
}

