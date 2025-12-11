'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { PlayCircle, Loader2, CheckCircle2, XCircle, Clock, AlertCircle, Check, ChevronsUpDown } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { adminService, ScrapeTask, ScrapeHistory, Jurisdiction } from '@/services/adminService';
import { cn } from "@/lib/utils";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

export function ScrapeManager() {
    const [jurisdiction, setJurisdiction] = useState<string>('');
    const [jurisdictions, setJurisdictions] = useState<Jurisdiction[]>([]);
    const [open, setOpen] = useState(false);
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
                    const data = await adminService.getTaskStatus(task.task_id);

                    // If status changed to completed/failed, show alert and refresh history
                    if (data.status !== task.status) {
                        if (data.status === 'completed') {
                            setAlert({ type: 'success', message: `Scrape completed for ${task.jurisdiction}` });
                            fetchHistory();
                        } else if (data.status === 'failed') {
                            setAlert({ type: 'error', message: `Scrape failed for ${task.jurisdiction}` });
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

    // Load history and jurisdictions on mount
    useEffect(() => {
        fetchHistory();
        fetchJurisdictions();
    }, []);

    const fetchJurisdictions = async () => {
        try {
            const data = await adminService.getJurisdictions();
            setJurisdictions(data);
        } catch (error) {
            console.error('Failed to fetch jurisdictions:', error);
        }
    };

    const fetchHistory = async () => {
        try {
            const data = await adminService.getScrapeHistory();
            setHistory(data);
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
            const data = await adminService.triggerScrape(jurisdiction, force);

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
                            <Popover open={open} onOpenChange={setOpen}>
                                <PopoverTrigger asChild>
                                    <Button
                                        variant="outline"
                                        role="combobox"
                                        aria-expanded={open}
                                        className="w-full justify-between bg-white/50 border-gray-200 text-gray-900"
                                    >
                                        {jurisdiction
                                            ? jurisdictions.find((j) => j.name === jurisdiction)?.name
                                            : "Select jurisdiction..."}
                                        <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                                    </Button>
                                </PopoverTrigger>
                                <PopoverContent className="w-[300px] p-0">
                                    <Command>
                                        <CommandInput placeholder="Search jurisdiction..." />
                                        <CommandList>
                                            <CommandEmpty>No jurisdiction found.</CommandEmpty>
                                            <CommandGroup>
                                                {jurisdictions.map((j) => (
                                                    <CommandItem
                                                        key={j.id}
                                                        value={j.name}
                                                        onSelect={(currentValue) => {
                                                            setJurisdiction(currentValue === jurisdiction ? "" : currentValue)
                                                            setOpen(false)
                                                        }}
                                                    >
                                                        <Check
                                                            className={cn(
                                                                "mr-2 h-4 w-4",
                                                                jurisdiction === j.name ? "opacity-100" : "opacity-0"
                                                            )}
                                                        />
                                                        {j.name}
                                                    </CommandItem>
                                                ))}
                                            </CommandGroup>
                                        </CommandList>
                                    </Command>
                                </PopoverContent>
                            </Popover>
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