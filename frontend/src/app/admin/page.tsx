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
import { AnalysisLab } from '@/components/admin/AnalysisLab';
import { ModelRegistry } from '@/components/admin/ModelRegistry';
import { PromptEditor } from '@/components/admin/PromptEditor';
import { JurisdictionMapper } from '@/components/admin/JurisdictionMapper';

export default function AdminDashboard() {
    const [activeTab, setActiveTab] = useState('overview');

    return (
        <div className="space-y-8">
            {/* Header */}
            <div>
                <h1 className="text-4xl font-bold text-gray-900 mb-2">Admin Dashboard</h1>
                <p className="text-gray-600">Manage scraping, analysis, models, and prompts</p>
            </div>

            {/* Main Content */}
            <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
                <TabsList className="bg-white/40 backdrop-blur-md border border-white/20 p-1">
                    <TabsTrigger value="overview" className="data-[state=active]:bg-white data-[state=active]:shadow-sm">
                        <Activity className="w-4 h-4 mr-2" />
                        Overview
                    </TabsTrigger>
                    <TabsTrigger value="scraping" className="data-[state=active]:bg-white data-[state=active]:shadow-sm">
                        <Database className="w-4 h-4 mr-2" />
                        Scraping
                    </TabsTrigger>
                    <TabsTrigger value="sources" className="data-[state=active]:bg-white data-[state=active]:shadow-sm">
                        <PlayCircle className="w-4 h-4 mr-2" />
                        Jurisdiction
                    </TabsTrigger>
                    <TabsTrigger value="analysis" className="data-[state=active]:bg-white data-[state=active]:shadow-sm">
                        <Zap className="w-4 h-4 mr-2" />
                        Analysis
                    </TabsTrigger>
                    <TabsTrigger value="models" className="data-[state=active]:bg-white data-[state=active]:shadow-sm">
                        <Settings className="w-4 h-4 mr-2" />
                        Models
                    </TabsTrigger>
                    <TabsTrigger value="prompts" className="data-[state=active]:bg-white data-[state=active]:shadow-sm">
                        <FileText className="w-4 h-4 mr-2" />
                        Prompts
                    </TabsTrigger>
                </TabsList>

                {/* Overview Tab */}
                <TabsContent value="overview" className="space-y-6">
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                        {/* Quick Stats */}
                        <Card className="bg-white/40 backdrop-blur-md border-white/20 shadow-sm">
                            <CardHeader className="pb-3">
                                <CardTitle className="text-gray-600 text-sm font-medium">Total Scrapes</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="text-3xl font-bold text-gray-900">0</div>
                                <p className="text-xs text-gray-500 mt-1">Last 30 days</p>
                            </CardContent>
                        </Card>

                        <Card className="bg-white/40 backdrop-blur-md border-white/20 shadow-sm">
                            <CardHeader className="pb-3">
                                <CardTitle className="text-gray-600 text-sm font-medium">Analyses Run</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="text-3xl font-bold text-gray-900">0</div>
                                <p className="text-xs text-gray-500 mt-1">All time</p>
                            </CardContent>
                        </Card>

                        <Card className="bg-white/40 backdrop-blur-md border-white/20 shadow-sm">
                            <CardHeader className="pb-3">
                                <CardTitle className="text-gray-600 text-sm font-medium">Active Models</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="text-3xl font-bold text-gray-900">3</div>
                                <p className="text-xs text-gray-500 mt-1">Configured</p>
                            </CardContent>
                        </Card>

                        <Card className="bg-white/40 backdrop-blur-md border-white/20 shadow-sm">
                            <CardHeader className="pb-3">
                                <CardTitle className="text-gray-600 text-sm font-medium">System Health</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <Badge className="bg-green-100 text-green-700 border-green-200 hover:bg-green-200">
                                    Healthy
                                </Badge>
                            </CardContent>
                        </Card>
                    </div>

                    {/* Recent Activity Placeholder */}
                    <Card className="bg-white/40 backdrop-blur-md border-white/20 shadow-sm">
                        <CardHeader>
                            <CardTitle className="text-gray-900">Recent Activity</CardTitle>
                            <CardDescription className="text-gray-500">Latest system actions and events</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="text-sm text-gray-500 text-center py-8">
                                No recent activity to display
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* Scraping Tab */}
                <TabsContent value="scraping">
                    <ScrapeManager />
                </TabsContent>

                {/* Jurisdiction Tab */}
                <TabsContent value="sources">
                    <JurisdictionMapper />
                </TabsContent>

                {/* Analysis Tab */}
                <TabsContent value="analysis">
                    <AnalysisLab />
                </TabsContent>

                {/* Models Tab */}
                <TabsContent value="models">
                    <ModelRegistry />
                </TabsContent>

                {/* Prompts Tab */}
                <TabsContent value="prompts" className="space-y-6">
                    <PromptEditor />
                </TabsContent>
            </Tabs>
        </div>
    );
}
