'use client';

import { Card, Title, Text, ScatterChart } from '@tremor/react';

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
}

export default function SummaryDashboard({ bills, jurisdiction }: SummaryDashboardProps) {
    // Transform data for scatter plot
    const chartData = bills.map((bill) => ({
        name: bill.bill_number,
        "Confidence (%)": Math.round(bill.avg_confidence * 100),
        "Annual Impact ($)": bill.total_impact,
        impacts: bill.impact_count,
    }));

    const totalImpact = bills.reduce((sum, bill) => sum + bill.total_impact, 0);
    const avgConfidence = bills.length > 0
        ? bills.reduce((sum, bill) => sum + bill.avg_confidence, 0) / bills.length
        : 0;

    return (
        <div className="space-y-6">
            {/* Summary Stats */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Card>
                    <Text>Total Bills Analyzed</Text>
                    <Title className="text-3xl mt-2">{bills.length}</Title>
                </Card>
                <Card>
                    <Text>Total Annual Impact (Median)</Text>
                    <Title className="text-3xl mt-2 text-tremor-brand-emphasis">
                        ${totalImpact.toLocaleString()}
                    </Title>
                    <Text className="text-xs text-gray-500 mt-1">Per typical family</Text>
                </Card>
                <Card>
                    <Text>Average Confidence</Text>
                    <Title className="text-3xl mt-2">
                        {Math.round(avgConfidence * 100)}%
                    </Title>
                </Card>
            </div>

            {/* Scatter Plot */}
            <Card>
                <Title>Impact vs Confidence Analysis</Title>
                <Text className="mb-4">
                    Each point represents a bill. Size indicates number of identified impacts.
                </Text>
                {bills.length > 0 ? (
                    <ScatterChart
                        className="h-80 mt-4"
                        data={chartData}
                        category="name"
                        x="Confidence (%)"
                        y="Annual Impact ($)"
                        size="impacts"
                        showLegend={false}
                        colors={["blue"]}
                    />
                ) : (
                    <div className="h-80 flex items-center justify-center text-gray-400">
                        No bills analyzed yet. Run a scrape to populate data.
                    </div>
                )}
            </Card>

            {/* Bill List */}
            <Card>
                <Title>Bills by Impact (Highest First)</Title>
                <div className="mt-4 space-y-2">
                    {bills
                        .sort((a, b) => b.total_impact - a.total_impact)
                        .map((bill) => (
                            <div
                                key={bill.id}
                                className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors cursor-pointer"
                            >
                                <div className="flex-1">
                                    <div className="flex items-center gap-2">
                                        <span className="font-mono text-sm font-medium text-tremor-brand">
                                            {bill.bill_number}
                                        </span>
                                        <span className="text-xs px-2 py-0.5 bg-gray-200 rounded-full">
                                            {bill.impact_count} impacts
                                        </span>
                                    </div>
                                    <Text className="mt-1 text-sm line-clamp-1">{bill.title}</Text>
                                </div>
                                <div className="text-right ml-4">
                                    <div className="text-lg font-bold text-tremor-brand-emphasis">
                                        ${bill.total_impact.toLocaleString()}
                                    </div>
                                    <Text className="text-xs text-gray-500">
                                        {Math.round(bill.avg_confidence * 100)}% confidence
                                    </Text>
                                </div>
                            </div>
                        ))}
                </div>
            </Card>
        </div>
    );
}
