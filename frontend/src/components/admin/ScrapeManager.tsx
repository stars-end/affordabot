'use client';

import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { PlayCircle, Loader2, CheckCircle2, XCircle, Clock, AlertCircle } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';

const JURISDICTIONS = [
    { value: 'san_jose', label: 'San Jose' },
    { value: 'saratoga', label: 'Saratoga' },
    { value: 'santa_clara_county', label: 'Santa Clara County' },
    { value: 'california_state', label: 'California State' },
];

interface ScrapeTask {
    task_id: string;
    jurisdiction: string;
    status: 'queued' | 'running' | 'completed' | 'failed';
    message: string;
    timestamp: string;
}

interface ScrapeHistory {
    id: string;
    jurisdiction: string;
    timestamp: string;
    bills_found: number;
    status: 'success' | 'partial' | 'failed';
    error?: string;
}

export function ScrapeManager() {
    const [jurisdiction, setJurisdiction] = useState<string>('');
    const [force, setForce] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [activeTasks, setActiveTasks] = useState<ScrapeTask[]>([]);
    const [history, setHistory] = useState<ScrapeHistory[]>([]);
    const [alert, setAlert] = useState<{ type: 'success' | 'error', message: string } | null>(null);

    const handleTriggerScrape = async () => {
        if (!jurisdiction) {
            setAlert({ type: 'error', message: 'Please select a jurisdiction' });
            return;
        }

        setIsLoading(true);
        setAlert(null);

        try {
            const response = await fetch('/api/admin/scrape', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ jurisdiction, force }),
            });

            if (!response.ok) throw new Error('Failed to trigger scrape');

            const data = await response.json();

            // Add to active tasks
            setActiveTasks(prev => [
                {
                    task_id: data.task_id,
                    jurisdiction: data.jurisdiction,
                    status: 'queued',
                    message: data.message,
                    timestamp: new Date().toISOString(),
                },
                ...prev,
            ]);

            setAlert({ type: 'success', message: `Scraping ${jurisdiction}...` });

            // Reset form
            setJurisdiction('');
            setForce(false);
        } catch (error) {
            setAlert({ type: 'error', message: 'Failed to trigger scrape' });
        } finally {
            setIsLoading(false);
        }
    };

    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'queued':
                return <Clock className="w-4 h-4 text-yellow-400" />;
            case 'running':
                return <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />;
            case 'completed':
            case 'success':
                return <CheckCircle2 className="w-4 h-4 text-green-400" />;
            case 'failed':
                return <XCircle className="w-4 h-4 text-red-400" />;
            default:
                return null;
        }
    };

    const getStatusBadge = (status: string) => {
        const variants: Record<string, string> = {
            queued: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30',
            running: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
            completed: 'bg-green-500/20 text-green-300 border-green-500/30',
            success: 'bg-green-500/20 text-green-300 border-green-500/30',
            failed: 'bg-red-500/20 text-red-300 border-red-500/30',
            partial: 'bg-orange-500/20 text-orange-300 border-orange-500/30',
        };

        return (
            <Badge className={variants[status] || ''}>
                {status}
            </Badge>
        );
    };

    return (
        <div className="space-y-6">
            {/* Alert */}
            {alert && (
                <Alert className={alert.type === 'error' ? 'bg-red-500/20 border-red-500/30' : 'bg-green-500/20 border-green-500/30'}>
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription className="text-white">
                        {alert.message}
                    </AlertDescription>
                </Alert>
            )}

            {/* Trigger Scrape */}
            <Card className="bg-white/10 backdrop-blur-md border-white/20">
                <CardHeader>
                    <CardTitle className="text-white">Trigger Manual Scrape</CardTitle>
                    <CardDescription className="text-slate-300">
                        Start a scraping operation for a specific jurisdiction
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-white">Jurisdiction</label>
                            <Select value={jurisdiction} onValueChange={setJurisdiction}>
                                <SelectTrigger className="bg-white/5 border-white/20 text-white">
                                    <SelectValue placeholder="Select jurisdiction" />
                                </SelectTrigger>
                                <SelectContent>
                                    {JURISDICTIONS.map(j => (
                                        <SelectItem key={j.value} value={j.value}>
                                            {j.label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>

                        <div className="flex items-end">
                            <div className="flex items-center space-x-2">
                                <Checkbox
                                    id="force"
                                    checked={force}
                                    onCheckedChange={(checked) => setForce(checked as boolean)}
                                />
                                <label
                                    htmlFor="force"
                                    className="text-sm font-medium text-white cursor-pointer"
                                >
                                    Force re-scrape
                                </label>
                            </div>
                        </div>

                        <div className="flex items-end">
                            <Button
                                onClick={handleTriggerScrape}
                                disabled={isLoading || !jurisdiction}
                                className="w-full bg-purple-600 hover:bg-purple-700"
                            >
                                {isLoading ? (
                                    <>
                                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                        Starting...
                                    </>
                                ) : (
                                    <>
                                        <PlayCircle className="w-4 h-4 mr-2" />
                                        Start Scrape
                                    </>
                                )}
                            </Button>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Active Tasks */}
            {activeTasks.length > 0 && (
                <Card className="bg-white/10 backdrop-blur-md border-white/20">
                    <CardHeader>
                        <CardTitle className="text-white">Active Tasks</CardTitle>
                        <CardDescription className="text-slate-300">
                            Currently running scraping operations
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <Table>
                            <TableHeader>
                                <TableRow className="border-white/10 hover:bg-white/5">
                                    <TableHead className="text-slate-300">Status</TableHead>
                                    <TableHead className="text-slate-300">Jurisdiction</TableHead>
                                    <TableHead className="text-slate-300">Task ID</TableHead>
                                    <TableHead className="text-slate-300">Started</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {activeTasks.map(task => (
                                    <TableRow key={task.task_id} className="border-white/10 hover:bg-white/5">
                                        <TableCell>
                                            <div className="flex items-center gap-2">
                                                {getStatusIcon(task.status)}
                                                {getStatusBadge(task.status)}
                                            </div>
                                        </TableCell>
                                        <TableCell className="text-white font-medium">
                                            {task.jurisdiction}
                                        </TableCell>
                                        <TableCell className="text-slate-300 font-mono text-xs">
                                            {task.task_id.slice(0, 8)}...
                                        </TableCell>
                                        <TableCell className="text-slate-300">
                                            {new Date(task.timestamp).toLocaleTimeString()}
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </CardContent>
                </Card>
            )}

            {/* Scrape History */}
            <Card className="bg-white/10 backdrop-blur-md border-white/20">
                <CardHeader>
                    <CardTitle className="text-white">Scrape History</CardTitle>
                    <CardDescription className="text-slate-300">
                        Recent scraping operations and results
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    {history.length === 0 ? (
                        <div className="text-center py-8 text-slate-400">
                            <p>No scrape history yet</p>
                            <p className="text-sm mt-1">Run a scrape to see results here</p>
                        </div>
                    ) : (
                        <Table>
                            <TableHeader>
                                <TableRow className="border-white/10 hover:bg-white/5">
                                    <TableHead className="text-slate-300">Status</TableHead>
                                    <TableHead className="text-slate-300">Jurisdiction</TableHead>
                                    <TableHead className="text-slate-300">Bills Found</TableHead>
                                    <TableHead className="text-slate-300">Timestamp</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {history.map(item => (
                                    <TableRow key={item.id} className="border-white/10 hover:bg-white/5">
                                        <TableCell>
                                            <div className="flex items-center gap-2">
                                                {getStatusIcon(item.status)}
                                                {getStatusBadge(item.status)}
                                            </div>
                                        </TableCell>
                                        <TableCell className="text-white font-medium">
                                            {item.jurisdiction}
                                        </TableCell>
                                        <TableCell className="text-slate-300">
                                            {item.bills_found}
                                        </TableCell>
                                        <TableCell className="text-slate-300">
                                            {new Date(item.timestamp).toLocaleString()}
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}
