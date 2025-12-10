'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { adminService, JurisdictionDashboardStats } from '@/services/adminService';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Activity, Clock, FileText, AlertTriangle, PlayCircle, ShieldCheck } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';

export default function JurisdictionDashboard() {
    const params = useParams();
    const id = params.id as string;
    const [stats, setStats] = useState<JurisdictionDashboardStats | null>(null);
    const [loading, setLoading] = useState(true);
    const [taskStatus, setTaskStatus] = useState<string | null>(null);
    const { toast } = useToast();

    const loadStats = () => {
        setLoading(true);
        adminService.getJurisdictionDashboard(id)
            .then(setStats)
            .catch((err) => {
                console.error(err);
                toast({
                    title: "Error",
                    description: "Failed to load dashboard stats",
                    variant: "destructive"
                });
            })
            .finally(() => setLoading(false));
    };

    useEffect(() => {
        if (id) loadStats();
    }, [id]);

    const handleScrape = async (force: boolean) => {
        if (!stats) return;
        try {
            setTaskStatus("Starting scrape...");
            const task = await adminService.triggerScrape(stats.jurisdiction, force);
            setTaskStatus(`Scrape started: ${task.task_id}`);
            toast({
                title: "Scrape Triggered",
                description: `Task ID: ${task.task_id}`
            });
            // Polling could be added here
        } catch (err) {
            console.error(err);
            toast({
                title: "Error",
                description: "Failed to trigger scrape",
                variant: "destructive"
            });
            setTaskStatus("Failed to start scrape");
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center h-full">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900" />
            </div>
        );
    }

    if (!stats) {
        return (
            <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>Error</AlertTitle>
                <AlertDescription>Could not load jurisdiction details.</AlertDescription>
            </Alert>
        );
    }

    return (
        <div className="space-y-8 p-6 max-w-7xl mx-auto">
            {/* Header */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6 pb-6 border-b">
                <div>
                    <h1 className="text-3xl font-bold text-gray-900 tracking-tight">{stats.jurisdiction}</h1>
                    <div className="flex items-center gap-3 mt-3">
                        <Badge variant={stats.pipeline_status === 'healthy' ? 'default' : 'destructive'} className="text-sm px-3 py-1 bg-white border shadow-sm">
                            {stats.pipeline_status === 'healthy' ? (
                                <ShieldCheck className="w-4 h-4 mr-1 inline text-green-600" />
                            ) : (
                                <AlertTriangle className="w-4 h-4 mr-1 inline text-red-600" />
                            )}
                            <span className={stats.pipeline_status === 'healthy' ? 'text-green-700' : 'text-red-700'}>
                                {stats.pipeline_status.toUpperCase()}
                            </span>
                        </Badge>
                        <span className="text-sm text-gray-500 flex items-center bg-gray-50 px-3 py-1 rounded-full border">
                            <Clock className="w-4 h-4 mr-1.5" />
                            Last Scrape: {stats.last_scrape ? new Date(stats.last_scrape).toLocaleString() : 'Never'}
                        </span>
                    </div>
                </div>
                <div className="flex gap-3 flex-wrap">
                    <Button variant="outline" className="bg-white" onClick={() => loadStats()}>
                        Refresh
                    </Button>
                    <Button onClick={() => handleScrape(false)} className="bg-blue-600 hover:bg-blue-700 text-white shadow-sm">
                        <PlayCircle className="w-4 h-4 mr-2" />
                        Run Scraper
                    </Button>
                    <Button variant="secondary" onClick={() => handleScrape(true)} className="bg-gray-100 hover:bg-gray-200 text-gray-900 border">
                        Force Rescrape
                    </Button>
                </div>
            </div>

            {/* Task Status Feedback */}
            {taskStatus && (
                <Alert className="bg-blue-50 border-blue-200">
                    <Activity className="h-4 w-4 text-blue-600" />
                    <AlertTitle>Task Status</AlertTitle>
                    <AlertDescription className="text-blue-800">{taskStatus}</AlertDescription>
                </Alert>
            )}

            {/* Metrics Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <Card className="bg-white/80 backdrop-blur border shadow-sm">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium text-gray-600">Raw Scrapes</CardTitle>
                        <FileText className="h-4 w-4 text-gray-400" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-gray-900">{stats.total_raw_scrapes}</div>
                        <p className="text-xs text-gray-500">
                            Items collected from sources
                        </p>
                    </CardContent>
                </Card>

                <Card className="bg-white/80 backdrop-blur border shadow-sm">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium text-gray-600">Processed Content</CardTitle>
                        <Activity className="h-4 w-4 text-gray-400" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-gray-900">{stats.processed_scrapes}</div>
                        <p className="text-xs text-gray-500">
                            Items successfully processed
                        </p>
                    </CardContent>
                </Card>

                <Card className="bg-white/80 backdrop-blur border shadow-sm">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium text-gray-600">Bills Analyzed</CardTitle>
                        <ShieldCheck className="h-4 w-4 text-gray-400" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-gray-900">{stats.total_bills}</div>
                        <p className="text-xs text-gray-500">
                            Legislative items generated
                        </p>
                    </CardContent>
                </Card>
            </div>

            {/* Recent Scrapes History */}
            <Card className="bg-white border shadow-sm">
                <CardHeader>
                    <CardTitle>Recent History</CardTitle>
                    <p className="text-sm text-gray-500">Latest scraping activity for this jurisdiction</p>
                </CardHeader>
                <CardContent>
                    <RecentScrapesTable jurisdiction={id} />
                </CardContent>
            </Card>

            {/* Active Alerts */}
            {stats.active_alerts.length > 0 && (
                <Card className="border-red-200 bg-red-50">
                    <CardHeader>
                        <CardTitle className="text-red-800 flex items-center">
                            <AlertTriangle className="w-5 h-5 mr-2" />
                            Active Alerts
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <ul className="list-disc pl-5 space-y-1 text-red-700">
                            {stats.active_alerts.map((alert, i) => (
                                <li key={i}>{alert}</li>
                            ))}
                        </ul>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}

function RecentScrapesTable({ jurisdiction }: { jurisdiction: string }) {
    const [history, setHistory] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        adminService.getScrapeHistory()
            .then(data => {
                // Filter client side for now as API supports optional filter
                const filtered = data.filter((h: any) => h.jurisdiction === jurisdiction || h.jurisdiction === decodeURIComponent(jurisdiction));
                setHistory(filtered.slice(0, 5));
            })
            .catch(console.error)
            .finally(() => setLoading(false));
    }, [jurisdiction]);

    if (loading) return <div className="text-sm text-gray-500">Loading history...</div>;
    if (history.length === 0) return <div className="text-sm text-gray-500">No recent history found.</div>;

    return (
        <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
                <thead className="bg-gray-50 text-gray-600 font-medium">
                    <tr>
                        <th className="px-4 py-2">Time</th>
                        <th className="px-4 py-2">Status</th>
                        <th className="px-4 py-2">Found</th>
                        <th className="px-4 py-2">Message</th>
                    </tr>
                </thead>
                <tbody className="divide-y">
                    {history.map((h) => (
                        <tr key={h.id} className="hover:bg-gray-50">
                            <td className="px-4 py-2 whitespace-nowrap">
                                {new Date(h.timestamp).toLocaleString()}
                            </td>
                            <td className="px-4 py-2">
                                <Badge variant={h.status === 'success' ? 'default' : 'destructive'}
                                    className={`text-xs ${h.status === 'success' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                                    {h.status}
                                </Badge>
                            </td>
                            <td className="px-4 py-2">{h.bills_found} items</td>
                            <td className="px-4 py-2 text-gray-500 max-w-xs truncate">
                                {h.error || "Completed successfully"}
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}
