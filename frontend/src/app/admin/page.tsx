'use client';

import { useState, useEffect } from 'react';
import { Card, Title, Text, Metric, Grid, BarChart, DonutChart } from '@tremor/react';

export default function AdminDashboard() {
    const [stats, setStats] = useState({
        totalBills: 0,
        totalImpacts: 0,
        avgConfidence: 0,
        totalCost: 0,
        byJurisdiction: [],
        recentScrapes: []
    });

    useEffect(() => {
        // TODO: Fetch from /admin/stats endpoint
        setStats({
            totalBills: 47,
            totalImpacts: 132,
            avgConfidence: 0.78,
            totalCost: 125000,
            byJurisdiction: [
                { name: 'Saratoga', bills: 12, impact: 45000 },
                { name: 'San Jose', bills: 18, impact: 52000 },
                { name: 'Santa Clara County', bills: 10, impact: 18000 },
                { name: 'California State', bills: 7, impact: 10000 }
            ],
            recentScrapes: [
                { jurisdiction: 'San Jose', timestamp: '2025-11-29 06:00', bills: 3, status: 'success' },
                { jurisdiction: 'Saratoga', timestamp: '2025-11-29 06:05', bills: 2, status: 'success' },
                { jurisdiction: 'California', timestamp: '2025-11-29 06:10', bills: 1, status: 'success' }
            ]
        });
    }, []);

    return (
        <main className="min-h-screen bg-gray-50 p-8">
            <div className="max-w-7xl mx-auto">
                <Title className="text-3xl mb-8">AffordaBot Admin Dashboard</Title>

                {/* Summary Stats */}
                <Grid numItems={1} numItemsSm={2} numItemsLg={4} className="gap-6 mb-8">
                    <Card>
                        <Text>Total Bills Analyzed</Text>
                        <Metric>{stats.totalBills}</Metric>
                    </Card>
                    <Card>
                        <Text>Total Impacts Identified</Text>
                        <Metric>{stats.totalImpacts}</Metric>
                    </Card>
                    <Card>
                        <Text>Average Confidence</Text>
                        <Metric>{Math.round(stats.avgConfidence * 100)}%</Metric>
                    </Card>
                    <Card>
                        <Text>Total Estimated Cost</Text>
                        <Metric>${(stats.totalCost / 1000).toFixed(0)}K</Metric>
                        <Text className="text-xs text-gray-500 mt-1">LLM API costs</Text>
                    </Card>
                </Grid>

                {/* Charts */}
                <Grid numItems={1} numItemsLg={2} className="gap-6 mb-8">
                    <Card>
                        <Title>Bills by Jurisdiction</Title>
                        <BarChart
                            className="mt-4 h-72"
                            data={stats.byJurisdiction}
                            index="name"
                            categories={["bills"]}
                            colors={["blue"]}
                            yAxisWidth={40}
                        />
                    </Card>
                    <Card>
                        <Title>Impact Distribution</Title>
                        <DonutChart
                            className="mt-4 h-72"
                            data={stats.byJurisdiction}
                            category="impact"
                            index="name"
                            colors={["blue", "cyan", "indigo", "violet"]}
                            valueFormatter={(value) => `$${(value / 1000).toFixed(0)}K`}
                        />
                    </Card>
                </Grid>

                {/* Recent Scrapes */}
                <Card>
                    <Title>Recent Scrapes</Title>
                    <div className="mt-4 space-y-2">
                        {stats.recentScrapes.map((scrape, idx) => (
                            <div key={idx} className="flex items-center justify-between p-3 bg-gray-50 rounded">
                                <div>
                                    <Text className="font-medium">{scrape.jurisdiction}</Text>
                                    <Text className="text-xs text-gray-500">{scrape.timestamp}</Text>
                                </div>
                                <div className="text-right">
                                    <Text className="font-medium">{scrape.bills} bills</Text>
                                    <Text className="text-xs text-green-600">{scrape.status}</Text>
                                </div>
                            </div>
                        ))}
                    </div>
                </Card>
            </div>
        </main>
    );
}
