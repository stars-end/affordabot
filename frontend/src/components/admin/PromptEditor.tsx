'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
    FileText,
    FileSearch,
    Loader2,
    Save,
    History,
    CheckCircle2,
    AlertCircle
} from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface PromptConfig {
    prompt_type: 'generation' | 'review' | 'research';
    system_prompt: string;
    updated_at: string;
    updated_by: string;
    version?: number;
}

export function PromptEditor() {
    const [activePromptType, setActivePromptType] = useState<'generation' | 'review' | 'research'>('generation');
    const [generationPrompt, setGenerationPrompt] = useState<PromptConfig | null>(null);
    const [reviewPrompt, setReviewPrompt] = useState<PromptConfig | null>(null);
    const [researchPrompt, setResearchPrompt] = useState<PromptConfig | null>(null);
    const [editedPrompt, setEditedPrompt] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [hasChanges, setHasChanges] = useState(false);
    const [alert, setAlert] = useState<{ type: 'success' | 'error', message: string } | null>(null);

    // Load prompts on mount and when type changes
    useEffect(() => {
        loadPrompt(activePromptType);
    }, [activePromptType]);

    // Track changes
    useEffect(() => {
        let currentPrompt: PromptConfig | null = null;
        if (activePromptType === 'generation') currentPrompt = generationPrompt;
        else if (activePromptType === 'review') currentPrompt = reviewPrompt;
        else currentPrompt = researchPrompt;

        setHasChanges(currentPrompt ? editedPrompt !== currentPrompt.system_prompt : false);
    }, [editedPrompt, generationPrompt, reviewPrompt, researchPrompt, activePromptType]);

    const loadPrompt = async (type: 'generation' | 'review' | 'research') => {
        setIsLoading(true);
        setAlert(null);

        try {
            const response = await fetch(`/api/admin/prompts/${type}`);
            if (!response.ok) throw new Error('Failed to load prompt');

            const data: PromptConfig = await response.json();

            if (type === 'generation') {
                setGenerationPrompt(data);
            } else if (type === 'review') {
                setReviewPrompt(data);
            } else {
                setResearchPrompt(data);
            }

            setEditedPrompt(data.system_prompt);
        } catch (error) {
            setAlert({ type: 'error', message: `Failed to load ${type} prompt` });
        } finally {
            setIsLoading(false);
        }
    };

    const handleSave = async () => {
        if (!editedPrompt.trim()) {
            setAlert({ type: 'error', message: 'Prompt cannot be empty' });
            return;
        }

        setIsSaving(true);
        setAlert(null);

        try {
            const response = await fetch('/api/admin/prompts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    prompt_type: activePromptType,
                    system_prompt: editedPrompt,
                }),
            });

            if (!response.ok) throw new Error('Failed to save prompt');

            const data = await response.json();

            setAlert({
                type: 'success',
                message: `Prompt saved successfully (Version ${data.version || 'new'})`
            });

            // Reload the prompt to get the latest version
            await loadPrompt(activePromptType);
            setHasChanges(false);
        } catch (error) {
            setAlert({ type: 'error', message: 'Failed to save prompt' });
        } finally {
            setIsSaving(false);
        }
    };

    const handleReset = () => {
        let currentPrompt: PromptConfig | null = null;
        if (activePromptType === 'generation') currentPrompt = generationPrompt;
        else if (activePromptType === 'review') currentPrompt = reviewPrompt;
        else currentPrompt = researchPrompt;

        if (currentPrompt) {
            setEditedPrompt(currentPrompt.system_prompt);
            setHasChanges(false);
        }
    };



    let currentPrompt: PromptConfig | null = null;
    if (activePromptType === 'generation') currentPrompt = generationPrompt;
    else if (activePromptType === 'review') currentPrompt = reviewPrompt;
    else currentPrompt = researchPrompt;

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

            {/* Prompt Editor */}
            <Card className="bg-white/40 backdrop-blur-md border-white/20 shadow-sm">
                <CardHeader>
                    <div className="flex items-center justify-between">
                        <div>
                            <CardTitle className="text-gray-900">System Prompt Editor</CardTitle>
                            <CardDescription className="text-gray-500">
                                Edit and version control system prompts for generation and review
                            </CardDescription>
                        </div>
                        {currentPrompt && (
                            <div className="flex items-center gap-2">
                                <Badge className="bg-blue-100 text-blue-700 border-blue-200">
                                    Version {currentPrompt.version || 1}
                                </Badge>
                                <Badge className="bg-purple-100 text-purple-700 border-purple-200">
                                    {currentPrompt.updated_by}
                                </Badge>
                            </div>
                        )}
                    </div>
                </CardHeader>
                <CardContent className="space-y-4">
                    {/* Prompt Type Tabs */}
                    <Tabs value={activePromptType} onValueChange={(v) => setActivePromptType(v as any)}>
                        <TabsList className="bg-white/50 backdrop-blur-md border border-gray-200">
                            <TabsTrigger value="generation" className="data-[state=active]:bg-white data-[state=active]:shadow-sm">
                                <FileText className="w-4 h-4 mr-2" />
                                Generation
                            </TabsTrigger>
                            <TabsTrigger value="review" className="data-[state=active]:bg-white data-[state=active]:shadow-sm">
                                <CheckCircle2 className="w-4 h-4 mr-2" />
                                Review
                            </TabsTrigger>
                            <TabsTrigger value="research" className="data-[state=active]:bg-white data-[state=active]:shadow-sm">
                                <FileSearch className="w-4 h-4 mr-2" />
                                Research
                            </TabsTrigger>
                        </TabsList>

                        <TabsContent value="generation" className="space-y-4 mt-4">
                            {isLoading ? (
                                <div className="text-center py-8">
                                    <Loader2 className="w-8 h-8 mx-auto text-purple-500 animate-spin" />
                                    <p className="text-gray-500 mt-2">Loading prompt...</p>
                                </div>
                            ) : (
                                <>
                                    <div className="space-y-2">
                                        <Label className="text-gray-700">System Prompt</Label>
                                        <Textarea
                                            value={editedPrompt}
                                            onChange={(e) => setEditedPrompt(e.target.value)}
                                            placeholder="Enter system prompt for generation..."
                                            className="min-h-[300px] bg-white/50 border-gray-200 text-gray-900 placeholder:text-gray-400 font-mono text-sm"
                                        />
                                        <p className="text-xs text-gray-500">
                                            This prompt guides the LLM when generating impact analyses
                                        </p>
                                    </div>

                                    {currentPrompt && (
                                        <div className="text-sm text-gray-500">
                                            Last updated: {new Date(currentPrompt.updated_at).toLocaleString()}
                                        </div>
                                    )}
                                </>
                            )}
                        </TabsContent>

                        <TabsContent value="review" className="space-y-4 mt-4">
                            {isLoading ? (
                                <div className="text-center py-8">
                                    <Loader2 className="w-8 h-8 mx-auto text-purple-500 animate-spin" />
                                    <p className="text-gray-500 mt-2">Loading prompt...</p>
                                </div>
                            ) : (
                                <>
                                    <div className="space-y-2">
                                        <Label className="text-gray-700">System Prompt</Label>
                                        <Textarea
                                            value={editedPrompt}
                                            onChange={(e) => setEditedPrompt(e.target.value)}
                                            placeholder="Enter system prompt for review..."
                                            className="min-h-[300px] bg-white/50 border-gray-200 text-gray-900 placeholder:text-gray-400 font-mono text-sm"
                                        />
                                        <p className="text-xs text-gray-500">
                                            This prompt guides the LLM when reviewing generated analyses
                                        </p>
                                    </div>

                                    {currentPrompt && (
                                        <div className="text-sm text-gray-500">
                                            Last updated: {new Date(currentPrompt.updated_at).toLocaleString()}
                                        </div>
                                    )}
                                </>
                            )}
                        </TabsContent>

                        <TabsContent value="research" className="space-y-4 mt-4">
                            {isLoading ? (
                                <div className="text-center py-8">
                                    <Loader2 className="w-8 h-8 mx-auto text-purple-500 animate-spin" />
                                    <p className="text-gray-500 mt-2">Loading prompt...</p>
                                </div>
                            ) : (
                                <>
                                    <div className="space-y-2">
                                        <Label className="text-gray-700">System Prompt</Label>
                                        <Textarea
                                            value={editedPrompt}
                                            onChange={(e) => setEditedPrompt(e.target.value)}
                                            placeholder="Enter system prompt for research..."
                                            className="min-h-[300px] bg-white/50 border-gray-200 text-gray-900 placeholder:text-gray-400 font-mono text-sm"
                                        />
                                        <p className="text-xs text-gray-500">
                                            This prompt guides the LLM when gathering research and context
                                        </p>
                                    </div>

                                    {currentPrompt && (
                                        <div className="text-sm text-gray-500">
                                            Last updated: {new Date(currentPrompt.updated_at).toLocaleString()}
                                        </div>
                                    )}
                                </>
                            )}
                        </TabsContent>
                    </Tabs>

                    {/* Action Buttons */}
                    <div className="flex gap-2 pt-4">
                        <Button
                            onClick={handleSave}
                            disabled={isSaving || !hasChanges}
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
                        <Button
                            onClick={handleReset}
                            disabled={!hasChanges}
                            variant="outline"
                            className="bg-white/50 border-gray-200 text-gray-700 hover:bg-white/80"
                        >
                            Reset
                        </Button>
                        {hasChanges && (
                            <Badge className="ml-auto bg-yellow-100 text-yellow-700 border-yellow-200">
                                Unsaved changes
                            </Badge>
                        )}
                    </div>
                </CardContent>
            </Card>

            {/* Version History (Placeholder) */}
            <Card className="bg-white/40 backdrop-blur-md border-white/20 shadow-sm">
                <CardHeader>
                    <CardTitle className="text-gray-900">Version History</CardTitle>
                    <CardDescription className="text-gray-500">
                        View and restore previous prompt versions
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="text-center py-8 text-gray-400">
                        <History className="w-12 h-12 mx-auto mb-3 opacity-50" />
                        <p>Version history coming soon</p>
                        <p className="text-sm mt-1">Will show all previous versions with diff viewer</p>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}

