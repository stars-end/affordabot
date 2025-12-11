'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { PlayCircle, Loader2, CheckCircle2, XCircle, Zap, FileSearch, FileText, CheckSquare, Check, ChevronsUpDown } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { AlertCircle } from 'lucide-react';
import { adminService, Jurisdiction } from '@/services/adminService';
import { cn } from "@/lib/utils";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

const ANALYSIS_STEPS = [
    { value: 'research', label: 'Research', icon: FileSearch, description: 'Gather background information' },
    { value: 'generate', label: 'Generate', icon: FileText, description: 'Create impact analysis' },
    { value: 'review', label: 'Review', icon: CheckSquare, description: 'Quality check and validation' },
];

interface AnalysisTask {
    task_id: string;
    jurisdiction: string;
    bill_id: string;
    step: string;
    status: 'started' | 'completed' | 'failed';
    timestamp: string;
}

interface AnalysisHistory {
    id: string;
    jurisdiction: string;
    bill_id: string;
    step: string;
    model_used: string;
    timestamp: string;
    status: 'success' | 'failed';
    result?: any;
    error?: string;
}

export function AnalysisLab() {
    const [jurisdiction, setJurisdiction] = useState<string>('');
    const [jurisdictions, setJurisdictions] = useState<Jurisdiction[]>([]);
    const [open, setOpen] = useState(false);
    const [billId, setBillId] = useState<string>('');
    const [step, setStep] = useState<string>('');
    const [modelOverride, setModelOverride] = useState<string>('');
    const [isLoading, setIsLoading] = useState(false);
    const [activeTasks, setActiveTasks] = useState<AnalysisTask[]>([]);
    const [history, setHistory] = useState<AnalysisHistory[]>([]);
    const [alert, setAlert] = useState<{ type: 'success' | 'error', message: string } | null>(null);

    const [models, setModels] = useState<{ value: string, label: string }[]>([]);

    // Fetch models and history on mount
    useEffect(() => {
        fetchModels();
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

    const fetchModels = async () => {
        try {
            const response = await fetch('/api/admin/models');
            if (response.ok) {
                const data = await response.json();
                setModels(data.map((m: any) => ({
                    value: `${m.provider}/${m.model_name}`,
                    label: `${m.provider === 'zai' ? 'Z.ai' : 'OpenRouter'} - ${m.model_name}`
                })));
            }
        } catch (error) {
            console.error('Failed to fetch models:', error);
        }
    };

    const fetchHistory = async () => {
        try {
            const response = await fetch('/api/admin/analyses');
            if (response.ok) {
                const data = await response.json();
                setHistory(data);
            }
        } catch (error) {
            console.error('Failed to fetch history:', error);
        }
    };

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
                            setAlert({ type: 'success', message: `Analysis ${task.step} completed for ${task.bill_id}` });
                            fetchHistory();
                        } else if (data.status === 'failed') {
                            setAlert({ type: 'error', message: `Analysis failed for ${task.bill_id}: ${data.error_message}` });
                        }
                    }

                    return {
                        ...task,
                        status: data.status
                    };
                } catch (e) {
                    return task;
                }
            }));

            // Remove completed/failed tasks after 5 seconds
            const active = updatedTasks.filter(t =>
                t.status === 'started' ||
                t.status === 'running' || // Handle both 'started' and 'running'
                (Date.now() - new Date(t.timestamp).getTime() < 5000)
            );

            setActiveTasks(active);
        }, 2000);

        return () => clearInterval(interval);
    }, [activeTasks]);

    const handleRunAnalysis = async () => {
        if (!jurisdiction || !billId || !step) {
            setAlert({ type: 'error', message: 'Please fill in all required fields' });
            return;
        }

        setIsLoading(true);
        setAlert(null);

        try {
            const response = await fetch('/api/admin/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    jurisdiction,
                    bill_id: billId,
                    step,
                    model_override: modelOverride || null,
                }),
            });

            if (!response.ok) throw new Error('Failed to run analysis');

            const data = await response.json();

            // Add to active tasks
            setActiveTasks(prev => [
                {
                    task_id: data.task_id,
                    jurisdiction,
                    bill_id: billId,
                    step,
                    status: 'started',
                    timestamp: new Date().toISOString(),
                },
                ...prev,
            ]);

            setAlert({ type: 'success', message: `Started ${step} analysis for ${billId}` });

            // Reset form (optional, maybe keep for sequential steps)
            // setBillId('');
            // setStep('');
            // setModelOverride('');
        } catch (error) {
            setAlert({ type: 'error', message: 'Failed to run analysis' });
        } finally {
            setIsLoading(false);
        }
    };

    const getStepIcon = (stepName: string) => {
        const stepConfig = ANALYSIS_STEPS.find(s => s.value === stepName);
        if (!stepConfig) return Zap;
        return stepConfig.icon;
    };

    const getStatusBadge = (status: string) => {
        const variants: Record<string, string> = {
            started: 'bg-blue-100 text-blue-700 border-blue-200',
            running: 'bg-blue-100 text-blue-700 border-blue-200',
            completed: 'bg-green-100 text-green-700 border-green-200',
            success: 'bg-green-100 text-green-700 border-green-200',
            failed: 'bg-red-100 text-red-700 border-red-200',
        };

        return (
            <Badge className={variants[status] || ''}>
                {status}
            </Badge>
        );
    };

    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'started':
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

            {/* Run Analysis */}
            <Card className="bg-white/40 backdrop-blur-md border-white/20 shadow-sm">
                <CardHeader>
                    <CardTitle className="text-gray-900">Run Analysis Pipeline</CardTitle>
                    <CardDescription className="text-gray-500">
                        Execute research, generation, or review steps for a specific bill
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                    {/* Bill Selection */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <Label className="text-gray-700">Jurisdiction</Label>
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

                        <div className="space-y-2">
                            <Label className="text-gray-700">Bill ID</Label>
                            <Input
                                placeholder="e.g., SB-123"
                                value={billId}
                                onChange={(e) => setBillId(e.target.value)}
                                className="bg-white/50 border-gray-200 text-gray-900 placeholder:text-gray-400"
                            />
                        </div>
                    </div>

                    {/* Analysis Step Selection */}
                    <div className="space-y-2">
                        <Label className="text-gray-700">Analysis Step</Label>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            {ANALYSIS_STEPS.map(s => {
                                const Icon = s.icon;
                                return (
                                    <button
                                        key={s.value}
                                        onClick={() => setStep(s.value)}
                                        className={`p-4 rounded-lg border-2 transition-all ${step === s.value
                                            ? 'bg-purple-100 border-purple-500'
                                            : 'bg-white/50 border-gray-200 hover:border-purple-200'
                                            }`}
                                    >
                                        <div className="flex items-center gap-3 mb-2">
                                            <Icon className={`w-5 h-5 ${step === s.value ? 'text-purple-700' : 'text-gray-500'}`} />
                                            <span className={`font-medium ${step === s.value ? 'text-purple-900' : 'text-gray-900'}`}>
                                                {s.label}
                                            </span>
                                        </div>
                                        <p className="text-sm text-gray-500 text-left">{s.description}</p>
                                    </button>
                                );
                            })}
                        </div>
                    </div>

                    {/* Model Override (Optional) */}
                    <div className="space-y-2">
                        <Label className="text-gray-700">Model Selection (Optional)</Label>
                        <Select value={modelOverride} onValueChange={setModelOverride}>
                            <SelectTrigger className="bg-white/50 border-gray-200 text-gray-900">
                                <SelectValue placeholder="Default (Auto-select based on priority)" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="">Default (Auto-select)</SelectItem>
                                {models.map(m => (
                                    <SelectItem key={m.value} value={m.value}>
                                        {m.label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        <p className="text-xs text-gray-500">Select a specific model to override the default configuration</p>
                    </div>

                    {/* Run Button */}
                    <Button
                        onClick={handleRunAnalysis}
                        disabled={isLoading || !jurisdiction || !billId || !step}
                        className="w-full bg-purple-600 hover:bg-purple-700 text-white"
                    >
                        {isLoading ? (
                            <>
                                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                Running...
                            </>
                        ) : (
                            <>
                                <PlayCircle className="w-4 h-4 mr-2" />
                                Run Analysis
                            </>
                        )}
                    </Button>
                </CardContent>
            </Card>

            {/* Active Tasks */}
            {activeTasks.length > 0 && (
                <Card className="bg-white/40 backdrop-blur-md border-white/20 shadow-sm">
                    <CardHeader>
                        <CardTitle className="text-gray-900">Active Analysis Tasks</CardTitle>
                        <CardDescription className="text-gray-500">
                            Currently running analysis operations
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <Table>
                            <TableHeader>
                                <TableRow className="border-gray-200 hover:bg-white/50">
                                    <TableHead className="text-gray-500">Status</TableHead>
                                    <TableHead className="text-gray-500">Step</TableHead>
                                    <TableHead className="text-gray-500">Bill ID</TableHead>
                                    <TableHead className="text-gray-500">Jurisdiction</TableHead>
                                    <TableHead className="text-gray-500">Started</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {activeTasks.map(task => {
                                    const Icon = getStepIcon(task.step);
                                    return (
                                        <TableRow key={task.task_id} className="border-gray-200 hover:bg-white/50">
                                            <TableCell>
                                                <div className="flex items-center gap-2">
                                                    {getStatusIcon(task.status)}
                                                    {getStatusBadge(task.status)}
                                                </div>
                                            </TableCell>
                                            <TableCell>
                                                <div className="flex items-center gap-2">
                                                    <Icon className="w-4 h-4 text-gray-500" />
                                                    <span className="text-gray-900 font-medium capitalize">{task.step}</span>
                                                </div>
                                            </TableCell>
                                            <TableCell className="text-gray-900 font-mono">{task.bill_id}</TableCell>
                                            <TableCell className="text-gray-500">{task.jurisdiction}</TableCell>
                                            <TableCell className="text-gray-500">
                                                {new Date(task.timestamp).toLocaleTimeString()}
                                            </TableCell>
                                        </TableRow>
                                    );
                                })}
                            </TableBody>
                        </Table>
                    </CardContent>
                </Card>
            )}

            {/* Analysis History */}
            <Card className="bg-white/40 backdrop-blur-md border-white/20 shadow-sm">
                <CardHeader>
                    <CardTitle className="text-gray-900">Analysis History</CardTitle>
                    <CardDescription className="text-gray-500">
                        Recent analysis pipeline executions
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    {history.length === 0 ? (
                        <div className="text-center py-8 text-gray-400">
                            <Zap className="w-12 h-12 mx-auto mb-3 opacity-50" />
                            <p>No analysis history yet</p>
                            <p className="text-sm mt-1">Run an analysis to see results here</p>
                        </div>
                    ) : (
                        <Table>
                            <TableHeader>
                                <TableRow className="border-gray-200 hover:bg-white/50">
                                    <TableHead className="text-gray-500">Status</TableHead>
                                    <TableHead className="text-gray-500">Step</TableHead>
                                    <TableHead className="text-gray-500">Bill ID</TableHead>
                                    <TableHead className="text-gray-500">Model</TableHead>
                                    <TableHead className="text-gray-500">Timestamp</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {history.map(item => {
                                    const Icon = getStepIcon(item.step);
                                    return (
                                        <TableRow key={item.id} className="border-gray-200 hover:bg-white/50">
                                            <TableCell>
                                                <div className="flex items-center gap-2">
                                                    {getStatusIcon(item.status)}
                                                    {getStatusBadge(item.status)}
                                                </div>
                                            </TableCell>
                                            <TableCell>
                                                <div className="flex items-center gap-2">
                                                    <Icon className="w-4 h-4 text-gray-500" />
                                                    <span className="text-gray-900 font-medium capitalize">{item.step}</span>
                                                </div>
                                            </TableCell>
                                            <TableCell className="text-gray-900 font-mono">{item.bill_id}</TableCell>
                                            <TableCell className="text-gray-500 text-sm">{item.model_used}</TableCell>
                                            <TableCell className="text-gray-500">
                                                {new Date(item.timestamp).toLocaleString()}
                                            </TableCell>
                                        </TableRow>
                                    );
                                })}
                            </TableBody>
                        </Table>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}
