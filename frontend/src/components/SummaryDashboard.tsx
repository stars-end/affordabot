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
            {/* Summary Stats */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-6 rounded-2xl bg-white/10 backdrop-blur-md border border-white/20 shadow-xl">
                    <div className="flex items-center gap-3 mb-2">
                        <div className="p-2 rounded-lg bg-purple-100 text-purple-600">
                            <FileText className="w-5 h-5" />
                        </div>
                        <h3 className="text-sm font-medium text-gray-600">Total Bills</h3>
                    </div>
                    <p className="text-3xl font-bold text-gray-800">{bills.length}</p>
                </div>

                <div className="p-6 rounded-2xl bg-white/10 backdrop-blur-md border border-white/20 shadow-xl">
                    <div className="flex items-center gap-3 mb-2">
                        <div className="p-2 rounded-lg bg-green-100 text-green-600">
                            <TrendingUp className="w-5 h-5" />
                        </div>
                        <h3 className="text-sm font-medium text-gray-600">Annual Impact (Total)</h3>
                    </div>
                    <p className="text-3xl font-bold text-gray-800">${totalImpact.toLocaleString()}</p>
                    <p className="text-xs text-gray-500 mt-1">Per typical family</p>
                </div>

                <div className="p-6 rounded-2xl bg-white/10 backdrop-blur-md border border-white/20 shadow-xl">
                    <div className="flex items-center gap-3 mb-2">
                        <div className="p-2 rounded-lg bg-blue-100 text-blue-600">
                            <AlertCircle className="w-5 h-5" />
                        </div>
                        <h3 className="text-sm font-medium text-gray-600">Avg Confidence</h3>
                    </div>
                    <p className="text-3xl font-bold text-gray-800">{safeConfidencePercent(avgConfidence)}</p>
                </div>
            </div>

            {/* Scatter Plot */}
            <div className="p-6 rounded-2xl bg-white/10 backdrop-blur-md border border-white/20 shadow-xl">
                <h3 className="text-lg font-bold text-gray-800 mb-2">Impact vs Confidence Analysis</h3>
                <p className="text-sm text-gray-600 mb-6">
                    Each point represents a bill. Size indicates number of identified impacts.
                </p>

                {bills.length > 0 ? (
                    <div className="h-80 w-full">
                        <ResponsiveContainer width="100%" height="100%">
                            <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                                <XAxis type="number" dataKey="confidence" name="Confidence" unit="%" domain={[0, 100]} />
                                <YAxis type="number" dataKey="impact" name="Impact" unit="$" />
                                <ZAxis type="number" dataKey="impacts" range={[60, 400]} name="Impacts" />
                                <Tooltip cursor={{ strokeDasharray: '3 3' }} content={({ active, payload }) => {
                                    if (active && payload && payload.length) {
                                        const data = payload[0].payload;
                                        return (
                                            <div className="bg-white p-3 border border-gray-200 shadow-lg rounded-lg">
                                                <p className="font-bold text-sm">{data.name}</p>
                                                <p className="text-xs text-gray-600 mb-2">{data.title}</p>
                                                <p className="text-xs">Impact: ${data.impact}</p>
                                                <p className="text-xs">Confidence: {data.confidence}%</p>
                                                <p className="text-xs">Impacts found: {data.impacts}</p>
                                            </div>
                                        );
                                    }
                                    return null;
                                }} />
                                <Scatter name="Bills" data={chartData} fill="#8884d8">
                                    {chartData.map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={entry.impact > 1000 ? '#ef4444' : '#3b82f6'} />
                                    ))}
                                </Scatter>
                            </ScatterChart>
                        </ResponsiveContainer>
                    </div>
                ) : (
                    <div className="h-80 flex items-center justify-center text-gray-400 bg-white/5 rounded-xl border border-white/10">
                        No bills analyzed yet. Run a scrape to populate data.
                    </div>
                )}
            </div>

            {/* Bill List */}
            <div className="p-6 rounded-2xl bg-white/10 backdrop-blur-md border border-white/20 shadow-xl">
                <h3 className="text-lg font-bold text-gray-800 mb-6">Bills by Impact (Highest First)</h3>
                <div className="space-y-3">
                    {[...bills]
                        .sort((a, b) => b.total_impact - a.total_impact)
                        .map((bill) => (
                            <div
                                key={bill.id}
                                onClick={() => onSelectBill(bill.id)}
                                className="group flex items-center justify-between p-4 bg-white/40 hover:bg-white/60 border border-white/40 rounded-xl transition-all cursor-pointer shadow-sm hover:shadow-md"
                            >
                                <div className="flex-1 min-w-0 mr-4">
                                    <div className="flex items-center gap-3 mb-1">
                                        <span className="font-mono text-sm font-bold text-purple-700 bg-purple-100 px-2 py-0.5 rounded-md">
                                            {bill.bill_number}
                                        </span>
                                        <span className="text-xs px-2 py-0.5 bg-gray-100 text-gray-600 rounded-full border border-gray-200">
                                            {bill.impact_count} impacts
                                        </span>
                                    </div>
                                    <p className="text-sm font-medium text-gray-800 truncate">{bill.title}</p>
                                </div>
                                <div className="text-right flex items-center gap-4">
                                    <div>
                                        <div className="text-lg font-bold text-gray-900">
                                            ${bill.total_impact.toLocaleString()}
                                        </div>
                                        <p className="text-xs text-gray-500">
                                            {safeConfidencePercent(bill.avg_confidence)} confidence
                                        </p>
                                    </div>
                                    <ArrowRight className="w-5 h-5 text-gray-400 group-hover:text-purple-600 transition-colors" />
                                </div>
                            </div>
                        ))}
                </div>
            </div>
        </div>
    );
}

