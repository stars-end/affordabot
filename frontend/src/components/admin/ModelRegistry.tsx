'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Switch } from '@/components/ui/switch';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
    Settings,
    Loader2,
    Save,
    Plus,
    GripVertical,
    CheckCircle2,
    XCircle,
    AlertCircle,
    Activity
} from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface ModelConfig {
    id?: string;
    provider: 'openrouter' | 'zai';
    model_name: string;
    priority: number;
    enabled: boolean;
    use_case: 'generation' | 'review' | 'research' | 'both';
}

const PROVIDERS = [
    { value: 'openrouter', label: 'OpenRouter' },
    { value: 'zai', label: 'Z.ai' },
];

const USE_CASES = [
    { value: 'generation', label: 'Generation' },
    { value: 'review', label: 'Review' },
    { value: 'research', label: 'Research' },
    { value: 'both', label: 'Both' },
];

export function ModelRegistry() {
    const [models, setModels] = useState<ModelConfig[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [checkingHealth, setCheckingHealth] = useState(false);
    const [healthStatus, setHealthStatus] = useState<any[]>([]);

    const checkHealth = async () => {
        setCheckingHealth(true);
        try {
            const response = await fetch('/api/admin/health/models');
            if (response.ok) {
                const data = await response.json();
                setHealthStatus(data);
            }
        } catch (error) {
            console.error('Failed to check health:', error);
        } finally {
            setCheckingHealth(false);
        }
    };
    const [isSaving, setIsSaving] = useState(false);
    const [showAddForm, setShowAddForm] = useState(false);
    const [alert, setAlert] = useState<{ type: 'success' | 'error', message: string } | null>(null);

    // New model form state
    const [newModel, setNewModel] = useState<Partial<ModelConfig>>({
        provider: 'openrouter',
        model_name: '',
        priority: 999,
        enabled: true,
        use_case: 'generation',
    });

    // Load models on mount
    useEffect(() => {
        loadModels();
    }, []);

    const loadModels = async () => {
        setIsLoading(true);
        try {
            const response = await fetch('/api/admin/models');
            if (!response.ok) throw new Error('Failed to load models');
            const data = await response.json();
            setModels(data.sort((a: ModelConfig, b: ModelConfig) => a.priority - b.priority));
        } catch (error) {
            setAlert({ type: 'error', message: 'Failed to load models' });
        } finally {
            setIsLoading(false);
        }
    };

    const handleSaveModels = async () => {
        setIsSaving(true);
        setAlert(null);

        try {
            const response = await fetch('/api/admin/models', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ models }),
            });

            if (!response.ok) throw new Error('Failed to save models');

            setAlert({ type: 'success', message: 'Model configuration saved successfully' });
        } catch (error) {
            setAlert({ type: 'error', message: 'Failed to save model configuration' });
        } finally {
            setIsSaving(false);
        }
    };

    const handleToggleEnabled = (index: number) => {
        const updated = [...models];
        updated[index].enabled = !updated[index].enabled;
        setModels(updated);
    };

    const handlePriorityChange = (index: number, direction: 'up' | 'down') => {
        const updated = [...models];
        const currentPriority = updated[index].priority;

        if (direction === 'up' && index > 0) {
            // Swap with previous
            const prevPriority = updated[index - 1].priority;
            updated[index].priority = prevPriority;
            updated[index - 1].priority = currentPriority;
            updated.sort((a, b) => a.priority - b.priority);
        } else if (direction === 'down' && index < updated.length - 1) {
            // Swap with next
            const nextPriority = updated[index + 1].priority;
            updated[index].priority = nextPriority;
            updated[index + 1].priority = currentPriority;
            updated.sort((a, b) => a.priority - b.priority);
        }

        setModels(updated);
    };

    const handleAddModel = () => {
        if (!newModel.model_name) {
            setAlert({ type: 'error', message: 'Model name is required' });
            return;
        }

        const maxPriority = Math.max(...models.map(m => m.priority), 0);
        const modelToAdd: ModelConfig = {
            provider: newModel.provider as 'openrouter' | 'zai',
            model_name: newModel.model_name,
            priority: maxPriority + 1,
            enabled: newModel.enabled ?? true,
            use_case: newModel.use_case as 'generation' | 'review' | 'research' | 'both',
        };

        setModels([...models, modelToAdd]);
        setShowAddForm(false);
        setNewModel({
            provider: 'openrouter',
            model_name: '',
            priority: 999,
            enabled: true,
            use_case: 'generation',
        });
        setAlert({ type: 'success', message: 'Model added. Click Save to persist changes.' });
    };

    const getUseCaseBadge = (useCase: string) => {
        const variants: Record<string, string> = {
            generation: 'bg-blue-100 text-blue-700 border-blue-200',
            review: 'bg-purple-100 text-purple-700 border-purple-200',
            research: 'bg-orange-100 text-orange-700 border-orange-200',
            both: 'bg-green-100 text-green-700 border-green-200',
        };

        return (
            <Badge className={variants[useCase] || ''}>
                {useCase}
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

            {/* Model List */}
            <Card className="bg-white/40 backdrop-blur-md border-white/20 shadow-sm">
                <CardHeader>
                    <div className="flex items-center justify-between">
                        <div>
                            <CardTitle className="text-gray-900">Model Configuration</CardTitle>
                            <CardDescription className="text-gray-500">
                                Manage LLM models and their priority order
                            </CardDescription>
                        </div>
                        <div className="flex gap-2">
                            <Button
                                onClick={() => setShowAddForm(!showAddForm)}
                                variant="outline"
                                className="bg-white/50 border-gray-200 text-gray-700 hover:bg-white/80"
                            >
                                <Plus className="w-4 h-4 mr-2" />
                                Add Model
                            </Button>
                            <Button
                                onClick={handleSaveModels}
                                disabled={isSaving}
                                className="bg-purple-600 hover:bg-purple-700 text-white"
                            >
                                {isSaving ? (
                                    <>
                                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                        Saving...
                                    </>
                                ) : (
                                    <>
                                        <Save className="w-4 h-4 mr-2" />
                                        Save Changes
                                    </>
                                )}
                            </Button>
                        </div>
                    </div>
                </CardHeader>
                <CardContent>
                    {/* Add Model Form */}
                    {showAddForm && (
                        <div className="mb-6 p-4 rounded-lg bg-white/50 border border-gray-200 space-y-4">
                            <h3 className="text-gray-900 font-medium">Add New Model</h3>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label className="text-gray-700">Provider</Label>
                                    <Select
                                        value={newModel.provider}
                                        onValueChange={(value) => setNewModel({ ...newModel, provider: value as any })}
                                    >
                                        <SelectTrigger className="bg-white border-gray-200 text-gray-900">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {PROVIDERS.map(p => (
                                                <SelectItem key={p.value} value={p.value}>
                                                    {p.label}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>

                                <div className="space-y-2">
                                    <Label className="text-gray-700">Model Name</Label>
                                    <Input
                                        placeholder="e.g., x-ai/grok-beta"
                                        value={newModel.model_name}
                                        onChange={(e) => setNewModel({ ...newModel, model_name: e.target.value })}
                                        className="bg-white border-gray-200 text-gray-900 placeholder:text-gray-400"
                                    />
                                </div>

                                <div className="space-y-2">
                                    <Label className="text-gray-700">Use Case</Label>
                                    <Select
                                        value={newModel.use_case}
                                        onValueChange={(value) => setNewModel({ ...newModel, use_case: value as any })}
                                    >
                                        <SelectTrigger className="bg-white border-gray-200 text-gray-900">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {USE_CASES.map(u => (
                                                <SelectItem key={u.value} value={u.value}>
                                                    {u.label}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>

                                <div className="flex items-end">
                                    <Button onClick={handleAddModel} className="w-full bg-green-600 hover:bg-green-700 text-white">
                                        <Plus className="w-4 h-4 mr-2" />
                                        Add Model
                                    </Button>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Models Table */}
                    {isLoading ? (
                        <div className="text-center py-8">
                            <Loader2 className="w-8 h-8 mx-auto text-purple-500 animate-spin" />
                            <p className="text-gray-500 mt-2">Loading models...</p>
                        </div>
                    ) : models.length === 0 ? (
                        <div className="text-center py-8 text-gray-400">
                            <Settings className="w-12 h-12 mx-auto mb-3 opacity-50" />
                            <p>No models configured</p>
                            <p className="text-sm mt-1">Add a model to get started</p>
                        </div>
                    ) : (
                        <Table>
                            <TableHeader>
                                <TableRow className="border-gray-200 hover:bg-white/50">
                                    <TableHead className="text-gray-500 w-12">Priority</TableHead>
                                    <TableHead className="text-gray-500">Provider</TableHead>
                                    <TableHead className="text-gray-500">Model Name</TableHead>
                                    <TableHead className="text-gray-500">Use Case</TableHead>
                                    <TableHead className="text-gray-500">Status</TableHead>
                                    <TableHead className="text-gray-500 w-24">Actions</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {models.map((model, index) => (
                                    <TableRow key={index} className="border-gray-200 hover:bg-white/50">
                                        <TableCell>
                                            <div className="flex items-center gap-2">
                                                <div className="flex flex-col">
                                                    <button
                                                        onClick={() => handlePriorityChange(index, 'up')}
                                                        disabled={index === 0}
                                                        className="text-gray-400 hover:text-gray-700 disabled:opacity-30 disabled:cursor-not-allowed"
                                                    >
                                                        ▲
                                                    </button>
                                                    <button
                                                        onClick={() => handlePriorityChange(index, 'down')}
                                                        disabled={index === models.length - 1}
                                                        className="text-gray-400 hover:text-gray-700 disabled:opacity-30 disabled:cursor-not-allowed"
                                                    >
                                                        ▼
                                                    </button>
                                                </div>
                                                <span className="text-gray-900 font-mono text-sm">{model.priority}</span>
                                            </div>
                                        </TableCell>
                                        <TableCell className="text-gray-900 font-medium capitalize">
                                            {model.provider}
                                        </TableCell>
                                        <TableCell className="text-gray-500 font-mono text-sm">
                                            {model.model_name}
                                        </TableCell>
                                        <TableCell>
                                            {getUseCaseBadge(model.use_case)}
                                        </TableCell>
                                        <TableCell>
                                            <div className="flex items-center gap-2">
                                                {model.enabled ? (
                                                    <CheckCircle2 className="w-4 h-4 text-green-500" />
                                                ) : (
                                                    <XCircle className="w-4 h-4 text-red-500" />
                                                )}
                                                <span className={model.enabled ? 'text-green-600' : 'text-red-600'}>
                                                    {model.enabled ? 'Enabled' : 'Disabled'}
                                                </span>
                                            </div>
                                        </TableCell>
                                        <TableCell>
                                            <Switch
                                                checked={model.enabled}
                                                onCheckedChange={() => handleToggleEnabled(index)}
                                            />
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    )}
                </CardContent>
            </Card>

            {/* Model Health (Placeholder) */}
            <Card className="bg-white/40 backdrop-blur-md border-white/20 shadow-sm">
                <CardHeader>
                    <div className="flex justify-between items-center">
                        <CardTitle className="flex items-center gap-2">
                            <Activity className="w-5 h-5" />
                            Model Health Status
                        </CardTitle>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={checkHealth}
                            disabled={checkingHealth}
                        >
                            {checkingHealth ? (
                                <>
                                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                    Checking...
                                </>
                            ) : (
                                'Check Health Now'
                            )}
                        </Button>
                    </div>
                    <CardDescription>Real-time status of configured models</CardDescription>
                </CardHeader>
                <CardContent>
                    {healthStatus.length === 0 ? (
                        <div className="text-center py-8 text-muted-foreground">
                            Click &quot;Check Health Now&quot; to verify model availability
                        </div>
                    ) : (
                        <div className="space-y-4">
                            {healthStatus.map((status, idx) => (
                                <div key={idx} className="flex items-center justify-between p-3 border rounded-lg">
                                    <div className="flex items-center gap-3">
                                        <div className={`w-3 h-3 rounded-full ${status.status === 'healthy' ? 'bg-green-500' : 'bg-red-500'
                                            }`} />
                                        <div>
                                            <div className="font-medium">{status.model_name}</div>
                                            <div className="text-xs text-muted-foreground capitalize">{status.provider}</div>
                                        </div>
                                    </div>
                                    <div className="text-right">
                                        <div className={`text-sm font-medium ${status.status === 'healthy' ? 'text-green-600' : 'text-red-600'
                                            }`}>
                                            {status.status === 'healthy' ? 'Operational' : 'Issues Detected'}
                                        </div>
                                        {status.latency_ms > 0 && (
                                            <div className="text-xs text-muted-foreground">
                                                {status.latency_ms}ms latency
                                            </div>
                                        )}
                                        {status.error && (
                                            <div className="text-xs text-red-500 max-w-[200px] truncate" title={status.error}>
                                                {status.error}
                                            </div>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}

