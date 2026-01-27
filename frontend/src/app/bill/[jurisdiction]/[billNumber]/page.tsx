'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import ImpactCard from '@/components/ImpactCard';
import { Loader2, Share2, Copy, Calendar, FileText, ArrowLeft } from 'lucide-react';
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
                        confidence: Number(imp.confidence_score) || 0,
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

    const totalImpact = bill.impacts?.reduce((sum: number, imp: any) => sum + (imp.p50 || 0), 0) || 0;
    const avgConfidence = bill.impacts?.length > 0
        ? bill.impacts.reduce((sum: number, imp: any) => sum + (imp.confidence || 0), 0) / bill.impacts.length
        : 0;

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
                                ${totalImpact.toLocaleString()}
                            </p>
                        </div>
                        <div className="kpi-card min-w-[140px]">
                            <span className="label-uppercase text-slate-500 block mb-1">Impact Score</span>
                            <p className="text-2xl font-numbers font-bold text-slate-900">
                                {(avgConfidence * 10).toFixed(1)}/10
                            </p>
                        </div>
                        <div className="kpi-card min-w-[140px]">
                            <span className="label-uppercase text-slate-500 block mb-1">Effective Date</span>
                            <p className="text-lg font-numbers font-bold text-slate-900">
                                {bill.effective_date
                                    ? new Date(bill.effective_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
                                    : 'Jan 1, 2024'}
                            </p>
                        </div>
                    </div>
                </div>
            </div>

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
                            <div className="text-slate-500 text-sm">
                                <p className="mb-4 text-slate-900 font-medium">117TH CONGRESS</p>
                                <p className="mb-4 text-slate-900 font-medium">2D SESSION</p>
                                <p className="mb-4 text-slate-900 font-medium">H. R. {bill.bill_number}</p>

                                <p className="mb-4 text-slate-900 font-bold uppercase">Title I—Committee on Finance</p>

                                <p className="mb-2 text-slate-900 font-medium">Subtitle A—Deficit Reduction</p>

                                <p className="mb-2 text-slate-900 font-medium">SEC. 10001. AMENDMENT OF 1986 CODE.</p>

                                <p className="mb-4 text-slate-600">
                                    Except as otherwise expressly provided, whenever in this subtitle an amendment or repeal is expressed in terms of an amendment to, or repeal of, a section or other provision, the reference shall be considered to be made to a section or other provision of the Internal Revenue Code of 1986.
                                </p>

                                <p className="mb-4 text-slate-900 font-bold uppercase">Part 1—Corporate Tax Reform</p>

                                <p className="mb-2 text-slate-900 font-medium">SEC. 10001. CORPORATE ALTERNATIVE MINIMUM TAX.</p>

                                <p className="mb-2 text-slate-900 font-medium">(a) In General.—</p>

                                <p className="mb-4 text-slate-900 font-medium">(1) GENERAL RULE.—Section 55 is amended to read as follows:</p>

                                <p className="mb-2 text-slate-900 font-medium">&ldquo;SEC. 55. ALTERNATIVE MINIMUM TAX IMPOSED.</p>

                                <p className="mb-4 text-slate-600 italic">
                                    &ldquo;(a) In General.—In the case of a corporation (other than an S corporation, a regulated investment company, or a real estate investment trust), there is hereby imposed for each taxable year...
                                </p>
                            </div>
                        )}
                    </div>
                </div>

                {/* Right Column - Impact Analysis */}
                <div className="lg:col-span-2 space-y-6">
                    {/* Sector Breakdown */}
                    <div className="card-prism p-6">
                        <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center gap-2">
                                <div className="w-2 h-2 rounded-full bg-prism-cyan" />
                                <span className="label-uppercase text-slate-900">Sector Breakdown</span>
                            </div>
                            <button className="text-xs text-prism-cyan hover:text-prism-cyan/80 font-medium">
                                Export Data
                            </button>
                        </div>

                        <div className="space-y-3">
                            <div className="flex items-center justify-between text-sm">
                                <span className="text-slate-600">Energy & Climate</span>
                                <span className="font-numbers font-medium text-slate-900">+$369B</span>
                            </div>
                            <div className="h-8 bg-slate-100 rounded overflow-hidden">
                                <div className="h-full bg-prism-cyan w-[85%]" />
                            </div>

                            <div className="flex items-center justify-between text-sm">
                                <span className="text-slate-600">Healthcare (ACA)</span>
                                <span className="font-numbers font-medium text-slate-900">+$64B</span>
                            </div>
                            <div className="h-8 bg-slate-100 rounded overflow-hidden">
                                <div className="h-full bg-prism-green w-[45%]" />
                            </div>

                            <div className="flex items-center justify-between text-sm">
                                <span className="text-slate-600">Drought Relief</span>
                                <span className="font-numbers font-medium text-slate-900">+$4B</span>
                            </div>
                            <div className="h-8 bg-slate-100 rounded overflow-hidden">
                                <div className="h-full bg-prism-yellow w-[15%]" />
                            </div>
                        </div>

                        {/* Legend */}
                        <div className="flex items-center gap-4 mt-4 text-xs text-slate-500">
                            <span>0%</span>
                            <div className="flex-1 h-px bg-slate-200" />
                            <span>25%</span>
                            <div className="flex-1 h-px bg-slate-200" />
                            <span>50%</span>
                            <div className="flex-1 h-px bg-slate-200" />
                            <span>75%</span>
                            <div className="flex-1 h-px bg-slate-200" />
                            <span>100%</span>
                        </div>
                    </div>

                    {/* Cost Waterfall */}
                    <div className="card-prism p-6">
                        <div className="flex items-center gap-2 mb-4">
                            <div className="w-2 h-2 rounded-full bg-prism-yellow" />
                            <span className="label-uppercase text-slate-900">Cost Waterfall</span>
                        </div>

                        <div className="flex items-center gap-2 mb-4">
                            <span className="px-2 py-1 text-xs bg-prism-green/10 text-prism-green rounded">
                                NET DEFICIT REDUCTION: $300B+
                            </span>
                        </div>

                        <div className="flex items-end gap-2 h-32">
                            <div className="flex-1 flex flex-col items-center gap-1">
                                <div className="w-full bg-prism-cyan rounded-t" style={{ height: '80%' }} />
                                <span className="text-xs text-slate-500 font-numbers">$739B</span>
                            </div>
                            <div className="flex-1 flex flex-col items-center gap-1">
                                <div className="w-full bg-prism-pink rounded-t" style={{ height: '40%' }} />
                                <span className="text-xs text-slate-500 font-numbers">-$64B</span>
                            </div>
                            <div className="flex-1 flex flex-col items-center gap-1">
                                <div className="w-full bg-prism-yellow rounded-t" style={{ height: '20%' }} />
                                <span className="text-xs text-slate-500 font-numbers">-$40B</span>
                            </div>
                        </div>
                    </div>

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
