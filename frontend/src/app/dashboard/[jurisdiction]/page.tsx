'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { Sidebar } from '@/components/Sidebar';
import SummaryDashboard from '@/components/SummaryDashboard';
import ImpactCard from '@/components/ImpactCard';
import { Title, Text, Button, Card } from '@tremor/react';
import { getLegislation, scrapeJurisdiction } from '@/lib/api';

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
        id: leg.id,
        bill_number: leg.bill_number,
        title: leg.title,
        total_impact: leg.impacts?.reduce((sum: number, imp: any) => sum + (imp.p50 || 0), 0) || 0,
        avg_confidence: leg.impacts?.length > 0
            ? leg.impacts.reduce((sum: number, imp: any) => sum + (imp.confidence_factor || 0), 0) / leg.impacts.length
            : 0,
        impact_count: leg.impacts?.length || 0,
    }));

    return (
        <div className="flex min-h-screen bg-gray-50">
            <Sidebar />

            <main className="flex-1 p-8">
                <div className="max-w-7xl mx-auto">
                    {/* Header */}
                    <div className="mb-8">
                        <Title className="text-3xl font-bold text-gray-900">{jurisdictionName} Dashboard</Title>
                        <Text className="mt-1">Real-time affordability impact analysis</Text>
                    </div>

                    {/* Action Bar */}
                    <Card className="mb-6">
                        <div className="flex items-center justify-between">
                            <div>
                                <Text className="font-medium">Status</Text>
                                <Text className="text-sm text-gray-500">
                                    {legislation.length} bills analyzed
                                </Text>
                            </div>
                            <div className="flex gap-2">
                                <Button
                                    size="sm"
                                    variant={view === 'summary' ? 'primary' : 'secondary'}
                                    onClick={() => setView('summary')}
                                >
                                    Summary View
                                </Button>
                                <Button
                                    size="sm"
                                    variant="secondary"
                                    onClick={handleScrape}
                                    loading={scraping}
                                >
                                    {scraping ? 'Scraping...' : 'Scrape & Analyze'}
                                </Button>
                            </div>
                        </div>
                    </Card>

                    {/* Content */}
                    {loading ? (
                        <Card className="text-center py-12">
                            <Text>Loading legislation...</Text>
                        </Card>
                    ) : view === 'summary' ? (
                        <SummaryDashboard bills={billsSummary} jurisdiction={jurisdictionName} />
                    ) : selectedBill ? (
                        <div>
                            <Button size="sm" variant="secondary" onClick={() => setSelectedBill(null)} className="mb-4">
                                ← Back to Summary
                            </Button>
                            <div className="mb-6">
                                <Title className="text-2xl">{selectedBill.title}</Title>
                                <Text className="text-gray-500">Bill #{selectedBill.bill_number}</Text>
                            </div>
                            {selectedBill.impacts?.map((impact: any) => (
                                <ImpactCard
                                    key={impact.id}
                                    impact={{
                                        impactNumber: impact.impact_number,
                                        description: impact.description,
                                        clause: impact.relevant_clause,
                                        confidence: impact.confidence_factor,
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
                    ) : null}
                </div>
            </main>
        </div>
    );
}
