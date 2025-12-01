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

    // Poll active tasks
    useEffect(() => {
        if (activeTasks.length === 0) return;

        const interval = setInterval(async () => {
            const updatedTasks = await Promise.all(activeTasks.map(async (task) => {
                if (task.status === 'completed' || task.status === 'failed') return task;

                try {
                    const response = await fetch(`/api/admin/tasks/${task.task_id}`);
                    if (!response.ok) return task;
                    const data = await response.json();

                    // If status changed to completed/failed, show alert and refresh history
                    if (data.status !== task.status) {
                        if (data.status === 'completed') {
                            setAlert({ type: 'success', message: `Scrape completed for ${task.jurisdiction}` });
                            fetchHistory();
                        } else if (data.status === 'failed') {
                            setAlert({ type: 'error', message: `Scrape failed for ${task.jurisdiction}: ${data.error_message}` });
                        }
                    }

                    return {
                        ...task,
                        status: data.status,
                        message: data.status === 'running' ? 'Scraping in progress...' : data.status
                    };
                } catch (e) {
                    return task;
                }
            }));

            // Remove completed/failed tasks after 5 seconds
            const active = updatedTasks.filter(t =>
                t.status === 'queued' ||
                t.status === 'running' ||
                (Date.now() - new Date(t.timestamp).getTime() < 5000) // Keep completed for 5s
            );

            setActiveTasks(active);
        }, 2000);

        return () => clearInterval(interval);
    }, [activeTasks]);

    // Load history on mount
    useEffect(() => {
        fetchHistory();
    }, []);

    const fetchHistory = async () => {
        try {
            const response = await fetch('/api/admin/scrapes');
            if (response.ok) {
                const data = await response.json();
                setHistory(data);
            }
        } catch (error) {
            console.error('Failed to fetch history:', error);
        }
    };

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

            setAlert({ type: 'success', message: `Scraping started for ${jurisdiction}` });

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
                return <Clock className="w-4 h-4 text-yellow-500" />;
            case 'running':
                return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />;
            case 'completed':
            case 'success':
                return <CheckCircle2 className="w-4 h-4 text-green-500" />;
            case 'failed':
                return <XCircle className="w-4 h-4 text-red-500" />;
            default:
                return null;
        }
    };

    const getStatusBadge = (status: string) => {
        const variants: Record<string, string> = {
            queued: 'bg-yellow-100 text-yellow-700 border-yellow-200',
            running: 'bg-blue-100 text-blue-700 border-blue-200',
            completed: 'bg-green-100 text-green-700 border-green-200',
            success: 'bg-green-100 text-green-700 border-green-200',
            failed: 'bg-red-100 text-red-700 border-red-200',
            partial: 'bg-orange-100 text-orange-700 border-orange-200',
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
                <Alert className={alert.type === 'error' ? 'bg-red-50 border-red-200 text-red-800' : 'bg-green-50 border-green-200 text-green-800'}>
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription>
                        {alert.message}
                    </AlertDescription>
                </Alert>
            )}

            {/* Trigger Scrape */}
            <Card className="bg-white/40 backdrop-blur-md border-white/20 shadow-sm">
                <CardHeader>
                    <CardTitle className="text-gray-900">Trigger Manual Scrape</CardTitle>
                    <CardDescription className="text-gray-500">
                        Start a scraping operation for a specific jurisdiction
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-gray-700">Jurisdiction</label>
                            <Select value={jurisdiction} onValueChange={setJurisdiction}>
                                <SelectTrigger className="bg-white/50 border-gray-200 text-gray-900">
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
                                    className="text-sm font-medium text-gray-700 cursor-pointer"
                                >
                                    Force re-scrape
                                </label>
                            </div>
                        </div>

                        <div className="flex items-end">
                            <Button
                                onClick={handleTriggerScrape}
                                disabled={isLoading || !jurisdiction}
                                className="w-full bg-purple-600 hover:bg-purple-700 text-white"
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
                <Card className="bg-white/40 backdrop-blur-md border-white/20 shadow-sm">
                    <CardHeader>
                        <CardTitle className="text-gray-900">Active Tasks</CardTitle>
                        <CardDescription className="text-gray-500">
                            Currently running scraping operations
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <Table>
                            <TableHeader>
                                <TableRow className="border-gray-200 hover:bg-white/50">
                                    <TableHead className="text-gray-500">Status</TableHead>
                                    <TableHead className="text-gray-500">Jurisdiction</TableHead>
                                    <TableHead className="text-gray-500">Task ID</TableHead>
                                    <TableHead className="text-gray-500">Started</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {activeTasks.map(task => (
                                    <TableRow key={task.task_id} className="border-gray-200 hover:bg-white/50">
                                        <TableCell>
                                            <div className="flex items-center gap-2">
                                                {getStatusIcon(task.status)}
                                                {getStatusBadge(task.status)}
                                            </div>
                                        </TableCell>
                                        <TableCell className="text-gray-900 font-medium">
                                            {task.jurisdiction}
                                        </TableCell>
                                        <TableCell className="text-gray-500 font-mono text-xs">
                                            {task.task_id.slice(0, 8)}...
                                        </TableCell>
                                        <TableCell className="text-gray-500">
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
            <Card className="bg-white/40 backdrop-blur-md border-white/20 shadow-sm">
                <CardHeader>
                    <CardTitle className="text-gray-900">Scrape History</CardTitle>
                    <CardDescription className="text-gray-500">
                        Recent scraping operations and results
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    {history.length === 0 ? (
                        <div className="text-center py-8 text-gray-400">
                            <p>No scrape history yet</p>
                            <p className="text-sm mt-1">Run a scrape to see results here</p>
                        </div>
                    ) : (
                        <Table>
                            <TableHeader>
                                <TableRow className="border-gray-200 hover:bg-white/50">
                                    <TableHead className="text-gray-500">Status</TableHead>
                                    <TableHead className="text-gray-500">Jurisdiction</TableHead>
                                    <TableHead className="text-gray-500">Bills Found</TableHead>
                                    <TableHead className="text-gray-500">Timestamp</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {history.map(item => (
                                    <TableRow key={item.id} className="border-gray-200 hover:bg-white/50">
                                        <TableCell>
                                            <div className="flex items-center gap-2">
                                                {getStatusIcon(item.status)}
                                                {getStatusBadge(item.status)}
                                            </div>
                                        </TableCell>
                                        <TableCell className="text-gray-900 font-medium">
                                            {item.jurisdiction}
                                        </TableCell>
                                        <TableCell className="text-gray-500">
                                            {item.bills_found}
                                        </TableCell>
                                        <TableCell className="text-gray-500">
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

