'use client';

import { Card, Text, Metric, Flex, Badge, Accordion, AccordionHeader, AccordionBody } from '@tremor/react';
import { useState } from 'react';

interface Evidence {
    source_name: string;
    url: string;
    excerpt: string;
}

interface ImpactProps {
    impactNumber: number;
    description: string;
    clause: string;
    confidence: number;
    p10: number;
    p25: number;
    p50: number;
    p75: number;
    p90: number;
    evidence?: Evidence[];
    chainOfCausality?: string;
}

export default function ImpactCard({ impact }: { impact: ImpactProps }) {
    const [selectedPercentile, setSelectedPercentile] = useState(50);
    const [currentCost, setCurrentCost] = useState(impact.p50);

    const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const val = parseInt(e.target.value);
        setSelectedPercentile(val);

        // Linear interpolation
        if (val <= 10) setCurrentCost(impact.p10);
        else if (val <= 25) {
            const ratio = (val - 10) / 15;
            setCurrentCost(impact.p10 + ratio * (impact.p25 - impact.p10));
        } else if (val <= 50) {
            const ratio = (val - 25) / 25;
            setCurrentCost(impact.p25 + ratio * (impact.p50 - impact.p25));
        } else if (val <= 75) {
            const ratio = (val - 50) / 25;
            setCurrentCost(impact.p50 + ratio * (impact.p75 - impact.p50));
        } else if (val <= 90) {
            const ratio = (val - 75) / 15;
            setCurrentCost(impact.p75 + ratio * (impact.p90 - impact.p75));
        } else {
            setCurrentCost(impact.p90);
        }
    };

    return (
        <Card className="max-w-3xl mx-auto my-4 ring-1 ring-tremor-ring shadow-tremor-card">
            <Flex alignItems="start">
                <div>
                    <Text className="font-bold text-tremor-brand-emphasis">Impact #{impact.impactNumber}</Text>
                    <Metric className="mt-1">
                        ${Math.round(currentCost).toLocaleString()}
                        <span className="text-sm text-gray-500 font-normal">/year</span>
                    </Metric>
                </div>
                <Badge color={impact.confidence > 0.8 ? "emerald" : impact.confidence > 0.6 ? "yellow" : "orange"}>
                    {Math.round(impact.confidence * 100)}% Confidence
                </Badge>
            </Flex>

            <div className="mt-4">
                <Text className="text-gray-700 font-medium">Description</Text>
                <Text className="mt-1">{impact.description}</Text>
            </div>

            <div className="mt-4 bg-gray-50 p-3 rounded-md border border-gray-200">
                <Text className="text-xs text-gray-500 uppercase tracking-wide">Relevant Clause</Text>
                <Text className="mt-1 italic text-gray-600 text-sm">"{impact.clause}"</Text>
            </div>

            {/* Chain of Causality */}
            {impact.chainOfCausality && (
                <div className="mt-4">
                    <Accordion>
                        <AccordionHeader>
                            <Text className="font-medium">Chain of Causality</Text>
                        </AccordionHeader>
                        <AccordionBody>
                            <Text className="text-sm text-gray-600">{impact.chainOfCausality}</Text>
                        </AccordionBody>
                    </Accordion>
                </div>
            )}

            {/* Evidence */}
            {impact.evidence && impact.evidence.length > 0 && (
                <div className="mt-4">
                    <Accordion>
                        <AccordionHeader>
                            <Text className="font-medium">Evidence ({impact.evidence.length} sources)</Text>
                        </AccordionHeader>
                        <AccordionBody>
                            <div className="space-y-3">
                                {impact.evidence.map((ev, idx) => (
                                    <div key={idx} className="border-l-2 border-tremor-brand pl-3">
                                        <a
                                            href={ev.url}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="text-sm font-medium text-tremor-brand hover:text-tremor-brand-emphasis"
                                        >
                                            {ev.source_name} ↗
                                        </a>
                                        <Text className="text-xs text-gray-600 mt-1">"{ev.excerpt}"</Text>
                                    </div>
                                ))}
                            </div>
                        </AccordionBody>
                    </Accordion>
                </div>
            )}

            {/* Percentile Slider */}
            <div className="mt-6">
                <Flex>
                    <Text>Conservative Estimate (10%)</Text>
                    <Text>Worst Case (90%)</Text>
                </Flex>
                <input
                    type="range"
                    min="10"
                    max="90"
                    step="1"
                    value={selectedPercentile}
                    onChange={handleSliderChange}
                    className="w-full mt-2 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-tremor-brand"
                />
                <div className="flex justify-between text-xs text-gray-500 mt-1">
                    <span>${impact.p10.toLocaleString()}</span>
                    <span className="font-bold text-tremor-brand-emphasis">${impact.p50.toLocaleString()}</span>
                    <span>${impact.p90.toLocaleString()}</span>
                </div>
                <Text className="text-center mt-2 text-sm text-gray-600">
                    Selected: <span className="font-bold">{selectedPercentile}th Percentile</span>
                </Text>
            </div>
        </Card>
    );
}
