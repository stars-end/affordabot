'use client';

import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
    Settings,
    Database,
    Zap,
    FileText,
    Activity,
    PlayCircle,
    History
} from 'lucide-react';
import { ScrapeManager } from '@/components/admin/ScrapeManager';

export default function AdminDashboard() {
    const [activeTab, setActiveTab] = useState('overview');

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 p-8">
            {/* Header */}
            <div className="mb-8">
                <h1 className="text-4xl font-bold text-white mb-2">Admin Dashboard</h1>
                <p className="text-slate-300">Manage scraping, analysis, models, and prompts</p>
            </div>

            {/* Main Content */}
            <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
                <TabsList className="bg-white/10 backdrop-blur-md border border-white/20">
                    <TabsTrigger value="overview" className="data-[state=active]:bg-white/20">
                        <Activity className="w-4 h-4 mr-2" />
                        Overview
                    </TabsTrigger>
                    <TabsTrigger value="scraping" className="data-[state=active]:bg-white/20">
                        <Database className="w-4 h-4 mr-2" />
                        Scraping
                    </TabsTrigger>
                    <TabsTrigger value="analysis" className="data-[state=active]:bg-white/20">
                        <Zap className="w-4 h-4 mr-2" />
                        Analysis
                    </TabsTrigger>
                    <TabsTrigger value="models" className="data-[state=active]:bg-white/20">
                        <Settings className="w-4 h-4 mr-2" />
                        Models
                    </TabsTrigger>
                    <TabsTrigger value="prompts" className="data-[state=active]:bg-white/20">
                        <FileText className="w-4 h-4 mr-2" />
                        Prompts
                    </TabsTrigger>
                </TabsList>

                {/* Overview Tab */}
                <TabsContent value="overview" className="space-y-6">
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                        {/* Quick Stats */}
                        <Card className="bg-white/10 backdrop-blur-md border-white/20">
                            <CardHeader className="pb-3">
                                <CardTitle className="text-white text-sm font-medium">Total Scrapes</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="text-3xl font-bold text-white">0</div>
                                <p className="text-xs text-slate-300 mt-1">Last 30 days</p>
                            </CardContent>
                        </Card>

                        <Card className="bg-white/10 backdrop-blur-md border-white/20">
                            <CardHeader className="pb-3">
                                <CardTitle className="text-white text-sm font-medium">Analyses Run</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="text-3xl font-bold text-white">0</div>
                                <p className="text-xs text-slate-300 mt-1">All time</p>
                            </CardContent>
                        </Card>

                        <Card className="bg-white/10 backdrop-blur-md border-white/20">
                            <CardHeader className="pb-3">
                                <CardTitle className="text-white text-sm font-medium">Active Models</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="text-3xl font-bold text-white">3</div>
                                <p className="text-xs text-slate-300 mt-1">Configured</p>
                            </CardContent>
                        </Card>

                        <Card className="bg-white/10 backdrop-blur-md border-white/20">
                            <CardHeader className="pb-3">
                                <CardTitle className="text-white text-sm font-medium">System Health</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <Badge className="bg-green-500/20 text-green-300 border-green-500/30">
                                    Healthy
                                </Badge>
                            </CardContent>
                        </Card>
                    </div>

                    {/* Recent Activity */}
                    <Card className="bg-white/10 backdrop-blur-md border-white/20">
                        <CardHeader>
                            <CardTitle className="text-white">Recent Activity</CardTitle>
                            <CardDescription className="text-slate-300">
                                Latest scraping and analysis operations
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="text-center py-8 text-slate-400">
                                <History className="w-12 h-12 mx-auto mb-3 opacity-50" />
                                <p>No recent activity</p>
                                <p className="text-sm mt-1">Run a scrape or analysis to get started</p>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* Scraping Tab */}
                <TabsContent value="scraping" className="space-y-6">
                    <ScrapeManager />
                </TabsContent>

                {/* Analysis Tab */}
                <TabsContent value="analysis" className="space-y-6">
                    <Card className="bg-white/10 backdrop-blur-md border-white/20">
                        <CardHeader>
                            <CardTitle className="text-white">Analysis Pipeline</CardTitle>
                            <CardDescription className="text-slate-300">
                                Run research, generation, and review steps
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="text-center py-8 text-slate-400">
                                <Zap className="w-12 h-12 mx-auto mb-3 opacity-50" />
                                <p>Analysis interface coming soon</p>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* Models Tab */}
                <TabsContent value="models" className="space-y-6">
                    <Card className="bg-white/10 backdrop-blur-md border-white/20">
                        <CardHeader>
                            <CardTitle className="text-white">Model Configuration</CardTitle>
                            <CardDescription className="text-slate-300">
                                Manage LLM models and priorities
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="text-center py-8 text-slate-400">
                                <Settings className="w-12 h-12 mx-auto mb-3 opacity-50" />
                                <p>Model configuration interface coming soon</p>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* Prompts Tab */}
                <TabsContent value="prompts" className="space-y-6">
                    <Card className="bg-white/10 backdrop-blur-md border-white/20">
                        <CardHeader>
                            <CardTitle className="text-white">System Prompts</CardTitle>
                            <CardDescription className="text-slate-300">
                                Edit and version control system prompts
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="text-center py-8 text-slate-400">
                                <FileText className="w-12 h-12 mx-auto mb-3 opacity-50" />
                                <p>Prompt editor coming soon</p>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>
        </div>
    );
}
