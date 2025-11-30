'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Navbar from '@/components/Navbar';
import ImpactCard from '@/components/ImpactCard';
import { Card, Title, Text, Badge, Button } from '@tremor/react';

export default function BillDetailPage() {
    const params = useParams();
    const jurisdiction = params.jurisdiction as string;
    const billNumber = params.billNumber as string;

    const [bill, setBill] = useState<any>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        // TODO: Fetch bill from API
        // For now, use mock data
        setBill({
            bill_number: billNumber,
            title: "Ordinance Amending City Code regarding ADU Heights",
            jurisdiction: jurisdiction,
            status: "Proposed",
            introduced_date: "2025-01-15",
            impacts: [
                {
                    impactNumber: 1,
                    description: "Increased construction costs due to height restrictions",
                    clause: "Section 3.2: Maximum ADU height reduced from 18ft to 16ft",
                    confidence: 0.85,
                    p10: 3200,
                    p25: 4100,
                    p50: 5200,
                    p75: 6800,
                    p90: 8500,
                    evidence: [
                        {
                            source_name: "CA Housing Cost Study 2024",
                            url: "https://example.com/study",
                            excerpt: "Height restrictions increase per-sqft costs by 15-25%"
                        }
                    ],
                    chainOfCausality: "Lower height limit → Smaller buildable area → Higher per-sqft costs → Increased total construction cost"
                }
            ]
        });
        setLoading(false);
    }, [jurisdiction, billNumber]);

    if (loading) {
        return (
            <main className="min-h-screen bg-gray-50">
                <Navbar />
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                    <Text>Loading...</Text>
                </div>
            </main>
        );
    }

    if (!bill) {
        return (
            <main className="min-h-screen bg-gray-50">
                <Navbar />
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                    <Text>Bill not found</Text>
                </div>
            </main>
        );
    }

    const totalImpact = bill.impacts?.reduce((sum: number, imp: any) => sum + imp.p50, 0) || 0;
    const avgConfidence = bill.impacts?.length > 0
        ? bill.impacts.reduce((sum: number, imp: any) => sum + imp.confidence, 0) / bill.impacts.length
        : 0;

    return (
        <main className="min-h-screen bg-gray-50">
            <Navbar />

            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                {/* Header */}
                <div className="mb-8">
                    <div className="flex items-start justify-between">
                        <div>
                            <div className="flex items-center gap-2 mb-2">
                                <Badge color="blue">{bill.jurisdiction}</Badge>
                                <Badge color="gray">{bill.status}</Badge>
                            </div>
                            <Title className="text-3xl font-bold text-gray-900 mb-2">
                                {bill.bill_number}: {bill.title}
                            </Title>
                            <Text className="text-gray-500">
                                Introduced: {new Date(bill.introduced_date).toLocaleDateString()}
                            </Text>
                        </div>
                        <div className="text-right">
                            <Text className="text-sm text-gray-500">Total Annual Impact</Text>
                            <Title className="text-4xl text-tremor-brand-emphasis">
                                ${totalImpact.toLocaleString()}
                            </Title>
                            <Text className="text-xs text-gray-500 mt-1">
                                {Math.round(avgConfidence * 100)}% avg confidence
                            </Text>
                        </div>
                    </div>
                </div>

                {/* Share Buttons */}
                <Card className="mb-6">
                    <div className="flex items-center justify-between">
                        <Text className="font-medium">Share this analysis</Text>
                        <div className="flex gap-2">
                            <Button
                                size="sm"
                                variant="secondary"
                                onClick={() => {
                                    navigator.clipboard.writeText(window.location.href);
                                    alert('Link copied!');
                                }}
                            >
                                📋 Copy Link
                            </Button>
                            <Button
                                size="sm"
                                variant="secondary"
                                onClick={() => {
                                    const text = `Check out this bill analysis: ${bill.bill_number} - $${totalImpact.toLocaleString()}/year impact`;
                                    window.open(`https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${encodeURIComponent(window.location.href)}`, '_blank');
                                }}
                            >
                                🐦 Tweet
                            </Button>
                        </div>
                    </div>
                </Card>

                {/* Impact Cards */}
                <div className="space-y-4">
                    {bill.impacts?.map((impact: any) => (
                        <ImpactCard key={impact.impactNumber} impact={impact} />
                    ))}
                </div>

                {/* Methodology */}
                <Card className="mt-8">
                    <Title>Methodology</Title>
                    <Text className="mt-2">
                        AffordaBot uses AI (GPT-4o/Claude) to analyze legislation text and estimate cost-of-living impacts.
                        All estimates are evidence-based and cite specific sources. Cost distributions (p10-p90) represent
                        uncertainty ranges based on family size, income level, and other factors.
                    </Text>
                    <Text className="mt-2 text-sm text-gray-500">
                        This analysis is for informational purposes only and should not be considered financial or legal advice.
                    </Text>
                </Card>
            </div>
        </main>
    );
}
