'use client';

import { useState, useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, LineChart, Line, PieChart, Pie, Cell } from 'recharts';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';

const billsPerMonthData = [
    { name: 'Jan', count: 42 },
    { name: 'Feb', count: 55 },
    { name: 'Mar', count: 78 },
    { name: 'Apr', count: 62 },
    { name: 'May', count: 88 },
    { name: 'Jun', count: 95 },
];

const highImpactBillsData = [
    { id: 'HB-101', title: 'Healthcare Reform Act', impactScore: 92 },
    { id: 'SB-203', title: 'Clean Energy Initiative', impactScore: 88 },
    { id: 'HB-450', title: 'Education Funding Bill', impactScore: 81 },
    { id: 'SB-50', title: 'Transportation Infrastructure', impactScore: 75 },
];

const processingStatusData = [
    { name: 'Processed', value: 400 },
    { name: 'Pending', value: 150 },
    { name: 'Failed', value: 50 },
];

const COLORS = ['#0088FE', '#FFBB28', '#FF8042'];

export function AnalyticsDashboard() {
    const [isClient, setIsClient] = useState(false);

    useEffect(() => {
        setIsClient(true);
    }, []);

    if (!isClient) {
        return null;
    }

    return (
        <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                <Card className="col-span-1 md:col-span-2 bg-white/40 backdrop-blur-md border-white/20 shadow-sm">
                    <CardHeader>
                        <CardTitle>Bills per Month</CardTitle>
                        <CardDescription>Volume of new bills introduced each month</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <ResponsiveContainer width="100%" height={300}>
                            <LineChart data={billsPerMonthData}>
                                <CartesianGrid strokeDasharray="3 3" />
                                <XAxis dataKey="name" />
                                <YAxis />
                                <Tooltip />
                                <Legend />
                                <Line type="monotone" dataKey="count" stroke="#8884d8" activeDot={{ r: 8 }} />
                            </LineChart>
                        </ResponsiveContainer>
                    </CardContent>
                </Card>

                <Card className="bg-white/40 backdrop-blur-md border-white/20 shadow-sm">
                    <CardHeader>
                        <CardTitle>Processing Status</CardTitle>
                        <CardDescription>Current state of all bills in the pipeline</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <ResponsiveContainer width="100%" height={300}>
                            <PieChart>
                                <Pie
                                    data={processingStatusData}
                                    cx="50%"
                                    cy="50%"
                                    labelLine={false}
                                    outerRadius={80}
                                    fill="#8884d8"
                                    dataKey="value"
                                >
                                    {processingStatusData.map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                    ))}
                                </Pie>
                                <Tooltip />
                                <Legend />
                            </PieChart>
                        </ResponsiveContainer>
                    </CardContent>
                </Card>
            </div>

            <Card className="bg-white/40 backdrop-blur-md border-white/20 shadow-sm">
                <CardHeader>
                    <CardTitle>High Impact Bills</CardTitle>
                    <CardDescription>Bills with the highest potential impact</CardDescription>
                </CardHeader>
                <CardContent>
                    <ResponsiveContainer width="100%" height={400}>
                        <BarChart layout="vertical" data={highImpactBillsData} margin={{ left: 100 }}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis type="number" />
                            <YAxis dataKey="id" type="category" />
                            <Tooltip />
                            <Legend />
                            <Bar dataKey="impactScore" fill="#82ca9d" />
                        </BarChart>
                    </ResponsiveContainer>
                </CardContent>
            </Card>
        </div>
    );
}
