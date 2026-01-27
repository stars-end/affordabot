'use client';

import { Suspense } from 'react';
export const dynamic = 'force-dynamic';
import { useState } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
    Settings,
    Database,
    Zap,
    Activity,
    PlayCircle,
    BarChart,
    Server,
    Clock,
    AlertTriangle
} from 'lucide-react';
import { ScrapeManager } from '@/components/admin/ScrapeManager';
import { AnalysisLab } from '@/components/admin/AnalysisLab';
import { ModelRegistry } from '@/components/admin/ModelRegistry';
import { JurisdictionMapper } from '@/components/admin/JurisdictionMapper';
import { AnalyticsDashboard } from '@/components/admin/AnalyticsDashboard';

export default function AdminDashboard() {
    const [activeTab, setActiveTab] = useState('overview');

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <div className="flex items-center gap-2 mb-2">
                        <span className="text-sm text-slate-500">ADMIN</span>
                        <span className="text-slate-300">/</span>
                        <span className="text-sm text-slate-900 font-medium">SYSTEM PIPELINE & LOGS</span>
                    </div>
                    <h1 className="text-2xl font-bold text-slate-900">Ingestion Pipeline</h1>
                </div>

                <div className="flex items-center gap-4">
                    {/* System Status */}
                    <div className="flex items-center gap-2 px-3 py-1.5 bg-prism-green/10 border border-prism-green/30 rounded">
                        <div className="w-2 h-2 rounded-full bg-prism-green animate-pulse" />
                        <span className="text-xs font-medium text-prism-green uppercase tracking-wider">System Online</span>
                    </div>
                </div>
            </div>

            {/* Pipeline Stats */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="kpi-card">
                    <div className="flex items-center gap-2 mb-2">
                        <span className="label-uppercase text-slate-500">Queue Size</span>
                        <AlertTriangle className="w-3 h-3 text-prism-yellow" />
                    </div>
                    <p className="text-3xl font-numbers font-bold text-slate-900">142</p>
                    <div className="h-1 w-full bg-slate-100 rounded-full mt-2 overflow-hidden">
                        <div className="h-full bg-prism-cyan w-[60%]" />
                    </div>
                </div>

                <div className="kpi-card">
                    <div className="flex items-center gap-2 mb-2">
                        <span className="label-uppercase text-slate-500">Latency</span>
                        <Clock className="w-3 h-3 text-slate-400" />
                    </div>
                    <p className="text-3xl font-numbers font-bold text-slate-900">45<span className="text-lg text-slate-500">ms</span></p>
                    <div className="h-1 w-full bg-slate-100 rounded-full mt-2 overflow-hidden">
                        <div className="h-full bg-prism-pink w-[30%]" />
                    </div>
                </div>

                <div className="kpi-card">
                    <div className="flex items-center gap-2 mb-2">
                        <span className="label-uppercase text-slate-500">Active Nodes</span>
                        <Server className="w-3 h-3 text-slate-400" />
                    </div>
                    <p className="text-3xl font-numbers font-bold text-slate-900">12</p>
                    <div className="h-1 w-full bg-slate-100 rounded-full mt-2 overflow-hidden">
                        <div className="h-full bg-prism-green w-[80%]" />
                    </div>
                </div>

                <div className="kpi-card">
                    <div className="flex items-center gap-2 mb-2">
                        <span className="label-uppercase text-slate-500">Error Rate</span>
                    </div>
                    <p className="text-3xl font-numbers font-bold text-slate-900">0.4<span className="text-lg text-slate-500">%</span></p>
                    <div className="h-1 w-full bg-slate-100 rounded-full mt-2 overflow-hidden">
                        <div className="h-full bg-prism-yellow w-[5%]" />
                    </div>
                </div>
            </div>

            {/* Pipeline Info */}
            <div className="card-prism p-4">
                <div className="flex items-center gap-2 text-sm text-slate-600">
                    <span className="text-prism-cyan">›</span>
                    <span>Active monitoring node: <span className="font-medium text-slate-900">US-EAST-1A</span></span>
                </div>
                <div className="flex items-center gap-2 text-sm text-slate-600 mt-1">
                    <span className="text-prism-cyan">›</span>
                    <span>Legislative document ingestion stream initialized.</span>
                </div>
            </div>

            {/* Main Content */}
            <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
                <TabsList className="bg-white border border-slate-200 p-1 rounded">
                    <TabsTrigger value="overview" className="data-[state=active]:bg-slate-900 data-[state=active]:text-white rounded text-sm">
                        <Activity className="w-4 h-4 mr-2" />
                        Overview
                    </TabsTrigger>
                    <TabsTrigger value="scraping" className="data-[state=active]:bg-slate-900 data-[state=active]:text-white rounded text-sm">
                        <Database className="w-4 h-4 mr-2" />
                        Scraping
                    </TabsTrigger>
                    <TabsTrigger value="sources" className="data-[state=active]:bg-slate-900 data-[state=active]:text-white rounded text-sm">
                        <PlayCircle className="w-4 h-4 mr-2" />
                        Jurisdiction
                    </TabsTrigger>
                    <TabsTrigger value="analysis" className="data-[state=active]:bg-slate-900 data-[state=active]:text-white rounded text-sm">
                        <Zap className="w-4 h-4 mr-2" />
                        Analysis
                    </TabsTrigger>
                    <TabsTrigger value="models" className="data-[state=active]:bg-slate-900 data-[state=active]:text-white rounded text-sm">
                        <Settings className="w-4 h-4 mr-2" />
                        Models
                    </TabsTrigger>
                </TabsList>

                {/* Overview Tab */}
                <TabsContent value="overview" className="space-y-6">
                    <AnalyticsDashboard />
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
            </Tabs>
        </div>
    );
}
