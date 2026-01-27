'use client';

import { ResponsiveContainer, ScatterChart, Scatter, XAxis, YAxis, ZAxis, Tooltip, Cell } from 'recharts';
import { FileText, TrendingUp, AlertCircle, ArrowRight } from 'lucide-react';

interface Bill {
    id: string;
    bill_number: string;
    title: string;
    total_impact: number;
    avg_confidence: number;
    impact_count: number;
}

interface SummaryDashboardProps {
    bills: Bill[];
    jurisdiction: string;
    onSelectBill: (billId: string) => void;
}

export default function SummaryDashboard({ bills, jurisdiction, onSelectBill }: SummaryDashboardProps) {
    // Safe confidence display helper - handles NaN/undefined/null
    const safeConfidencePercent = (conf: number): string => {
        if (isNaN(conf) || conf === null || conf === undefined || conf === 0) return 'N/A';
        return `${Math.round(conf * 100)}%`;
    };

    // Transform data for scatter plot
    const chartData = bills.map((bill) => ({
        name: bill.bill_number,
        confidence: isNaN(bill.avg_confidence) ? 0 : Math.round(bill.avg_confidence * 100),
        impact: bill.total_impact,
        impacts: bill.impact_count,
        id: bill.id,
        title: bill.title
    }));

    const totalImpact = bills.reduce((sum, bill) => sum + bill.total_impact, 0);
    const avgConfidence = bills.length > 0
        ? bills.reduce((sum, bill) => sum + bill.avg_confidence, 0) / bills.length
        : 0;

    return (
        <div className="space-y-6">
            {/* Summary Stats - KPI Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Total Bills Card */}
                <div className="kpi-card">
                    <div className="flex items-center gap-2 mb-3">
                        <div className="w-2 h-2 rounded-full bg-prism-cyan" />
                        <span className="label-uppercase text-slate-500">Total Tracked Bills</span>
                    </div>
                    <p className="text-4xl font-numbers font-bold text-slate-900">{bills.length.toLocaleString()}</p>
                </div>

                {/* Annual Impact Card */}
                <div className="kpi-card">
                    <div className="flex items-center gap-2 mb-3">
                        <div className="w-2 h-2 rounded-full bg-prism-yellow" />
                        <span className="label-uppercase text-slate-500">Avg. Household Impact</span>
                    </div>
                    <p className="text-4xl font-numbers font-bold text-slate-900">
                        ${totalImpact.toLocaleString()}
                    </p>
                    <p className="text-xs text-slate-500 mt-1">Per typical family</p>
                </div>

                {/* Confidence Card */}
                <div className="kpi-card">
                    <div className="flex items-center gap-2 mb-3">
                        <div className="w-2 h-2 rounded-full bg-prism-pink" />
                        <span className="label-uppercase text-slate-500">Confidence Index</span>
                    </div>
                    <p className="text-4xl font-numbers font-bold text-slate-900">{safeConfidencePercent(avgConfidence)}</p>
                    <div className="flex items-center gap-2 mt-2">
                        <div className="h-1 flex-1 bg-slate-100 rounded-full overflow-hidden">
                            <div
                                className="h-full bg-gradient-to-r from-prism-cyan via-prism-yellow to-prism-pink"
                                style={{ width: `${Math.round(avgConfidence * 100)}%` }}
                            />
                        </div>
                        <span className="text-xs text-slate-500">High Precision</span>
                    </div>
                </div>
            </div>

            {/* Main Content Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Impact Heatmap */}
                <div className="lg:col-span-2 card-prism p-6">
                    <div className="flex items-center justify-between mb-4">
                        <div>
                            <h3 className="label-uppercase text-slate-900">Impact Heatmap</h3>
                            <p className="text-sm text-slate-500">Geospatial cost distribution analysis (State Level)</p>
                        </div>
                        <div className="flex gap-2">
                            <span className="px-2 py-1 text-xs font-medium border border-slate-200 rounded">FILTER: URBAN</span>
                            <span className="px-2 py-1 text-xs font-medium border border-slate-200 rounded text-slate-400">FILTER: RURAL</span>
                        </div>
                    </div>

                    {/* Heatmap Grid */}
                    <div className="grid grid-cols-5 gap-1 aspect-video">
                        {Array.from({ length: 25 }).map((_, i) => {
                            // Generate varied colors based on position for visual effect
                            const colors = [
                                'bg-prism-cyan/20', 'bg-prism-cyan/30', 'bg-prism-cyan/40',
                                'bg-prism-yellow/20', 'bg-prism-yellow/30', 'bg-prism-yellow/40',
                                'bg-prism-pink/20', 'bg-prism-pink/30', 'bg-prism-pink/40',
                                'bg-prism-green/20', 'bg-prism-green/30',
                            ];
                            const colorClass = colors[i % colors.length];
                            return (
                                <div
                                    key={i}
                                    className={`${colorClass} rounded-sm transition-all hover:opacity-80 cursor-pointer`}
                                />
                            );
                        })}
                    </div>

                    {/* Legend */}
                    <div className="flex items-center gap-4 mt-4 text-xs">
                        <div className="flex items-center gap-1">
                            <div className="w-3 h-3 rounded-sm bg-prism-cyan/30" />
                            <span className="text-slate-500">Low Impact</span>
                        </div>
                        <div className="flex items-center gap-1">
                            <div className="w-3 h-3 rounded-sm bg-prism-yellow/30" />
                            <span className="text-slate-500">Moderate</span>
                        </div>
                        <div className="flex items-center gap-1">
                            <div className="w-3 h-3 rounded-sm bg-prism-pink/30" />
                            <span className="text-slate-500">High Impact</span>
                        </div>
                        <div className="flex items-center gap-1">
                            <div className="w-3 h-3 rounded-sm bg-prism-pink/60" />
                            <span className="text-slate-500">Critical</span>
                        </div>
                    </div>
                </div>

                {/* Legislative Feed */}
                <div className="card-prism p-6">
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="label-uppercase text-slate-900">Legislative Feed</h3>
                        <div className="w-2 h-2 rounded-full bg-prism-cyan animate-pulse" />
                    </div>

                    <div className="space-y-4">
                        <div className="border-l-2 border-prism-cyan pl-3">
                            <div className="flex items-center gap-2 text-xs text-slate-400 mb-1">
                                <span>TODAY, 09:42 AM</span>
                            </div>
                            <h4 className="text-sm font-medium text-slate-900">SB-104 Amendment Proposed</h4>
                            <p className="text-xs text-slate-500 mt-1">Committee revised housing density requirements. Projected cost impact increased by 1.2%.</p>
                            <div className="flex gap-2 mt-2">
                                <span className="px-1.5 py-0.5 text-xs bg-prism-cyan/10 text-prism-cyan rounded">HOUSING</span>
                                <span className="px-1.5 py-0.5 text-xs bg-prism-pink/10 text-prism-pink rounded">ALERT</span>
                            </div>
                        </div>

                        <div className="border-l-2 border-slate-200 pl-3">
                            <div className="flex items-center gap-2 text-xs text-slate-400 mb-1">
                                <span>YESTERDAY, 4:15 PM</span>
                            </div>
                            <h4 className="text-sm font-medium text-slate-900">AB-209 Fiscal Note Released</h4>
                            <p className="text-xs text-slate-500 mt-1">Official analysis confirms energy subsidy reductions for Tier 2 consumers.</p>
                            <div className="flex gap-2 mt-2">
                                <span className="px-1.5 py-0.5 text-xs bg-prism-yellow/10 text-prism-yellow rounded">ENERGY</span>
                            </div>
                        </div>

                        <div className="border-l-2 border-slate-200 pl-3">
                            <div className="flex items-center gap-2 text-xs text-slate-400 mb-1">
                                <span>OCT 24, 11:00 AM</span>
                            </div>
                            <h4 className="text-sm font-medium text-slate-900">New Bill Tracked: SB-882</h4>
                            <p className="text-xs text-slate-500 mt-1">AI Framework legislation added to tracking. Initial impact assessment pending.</p>
                            <div className="flex gap-2 mt-2">
                                <span className="px-1.5 py-0.5 text-xs bg-prism-purple/10 text-prism-purple rounded">TECH</span>
                                <span className="px-1.5 py-0.5 text-xs bg-slate-100 text-slate-600 rounded">NEW</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Bills Table */}
            <div className="card-prism p-6">
                <h3 className="label-uppercase text-slate-900 mb-4">Bills by Impact (Highest First)</h3>
                <div className="overflow-x-auto">
                    <table className="table-prism">
                        <thead>
                            <tr>
                                <th>Bill</th>
                                <th>Title</th>
                                <th>Impacts</th>
                                <th>Total Impact</th>
                                <th>Confidence</th>
                                <th></th>
                            </tr>
                        </thead>
                        <tbody>
                            {[...bills]
                                .sort((a, b) => b.total_impact - a.total_impact)
                                .map((bill) => (
                                    <tr
                                        key={bill.id}
                                        onClick={() => onSelectBill(bill.id)}
                                        className="cursor-pointer"
                                    >
                                        <td>
                                            <span className="font-numbers font-medium text-prism-cyan">{bill.bill_number}</span>
                                        </td>
                                        <td className="max-w-xs truncate">{bill.title}</td>
                                        <td>
                                            <span className="px-2 py-0.5 text-xs bg-slate-100 text-slate-600 rounded">
                                                {bill.impact_count} impacts
                                            </span>
                                        </td>
                                        <td className="font-numbers font-medium">${bill.total_impact.toLocaleString()}</td>
                                        <td>{safeConfidencePercent(bill.avg_confidence)}</td>
                                        <td>
                                            <ArrowRight className="w-4 h-4 text-slate-400" />
                                        </td>
                                    </tr>
                                ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
