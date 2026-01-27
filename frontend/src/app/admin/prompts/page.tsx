"use client";

import React, { useState, useEffect } from 'react';
import { promptService, SystemPrompt } from '@/services/PromptService';
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Loader2, Save, X, Edit } from 'lucide-react';

const PromptsPage = () => {
  const [prompts, setPrompts] = useState<SystemPrompt[]>([]);
  const [editingPrompt, setEditingPrompt] = useState<SystemPrompt | null>(null);
  const [editedContent, setEditedContent] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchPrompts = async () => {
      setIsLoading(true);
      try {
        const fetchedPrompts = await promptService.getPrompts();
        setPrompts(fetchedPrompts);
        setError(null);
      } catch (err) {
        setError("Failed to fetch prompts.");
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchPrompts();
  }, []);

  const handleEdit = (prompt: SystemPrompt) => {
    setEditingPrompt(prompt);
    setEditedContent(prompt.system_prompt);
  };

  const handleCancel = () => {
    setEditingPrompt(null);
    setEditedContent('');
  };

  const handleSave = async () => {
    if (!editingPrompt) return;

    try {
      const updatedPrompt = await promptService.updatePrompt(
        editingPrompt.prompt_type,
        editedContent
      );

      setPrompts(prompts.map(p =>
        p.prompt_type === updatedPrompt.prompt_type ? updatedPrompt : p
      ));

      handleCancel();
    } catch (err) {
      setError("Failed to update prompt.");
      console.error(err);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-prism-cyan mr-3" />
        <span className="text-slate-500">Loading prompts...</span>
      </div>
    );
  }

  if (error) {
    return <div className="text-prism-pink p-4 border border-prism-pink/30 rounded bg-prism-pink/10">{error}</div>;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 mb-2">
          <span className="text-sm text-slate-500">ADMIN</span>
          <span className="text-slate-300">/</span>
          <span className="text-sm text-slate-900 font-medium">SYSTEM PROMPTS</span>
        </div>
        <h1 className="text-2xl font-bold text-slate-900">Prompt Editor</h1>
        <p className="text-slate-500 mt-1">Manage LLM system prompts and templates</p>
      </div>

      {editingPrompt ? (
        <div className="card-prism p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">
                Edit Prompt: <span className="font-mono text-prism-cyan">{editingPrompt.prompt_type}</span>
              </h2>
              <p className="text-sm text-slate-500">Version {editingPrompt.version}</p>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={handleCancel} className="border-slate-200">
                <X className="mr-2 h-4 w-4" /> Cancel
              </Button>
              <Button onClick={handleSave} className="bg-slate-900 hover:bg-slate-800">
                <Save className="mr-2 h-4 w-4" /> Save Changes
              </Button>
            </div>
          </div>
          <textarea
            className="w-full h-96 p-4 border border-slate-200 rounded font-mono text-sm focus:border-prism-cyan focus:ring-2 focus:ring-prism-cyan/20 outline-none resize-none"
            value={editedContent}
            onChange={(e) => setEditedContent(e.target.value)}
          />
        </div>
      ) : (
        <div className="grid gap-4">
          {prompts.length === 0 ? (
            // Demo prompts
            <>
              <div className="card-prism p-6">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="font-mono text-prism-cyan font-medium">impact_analysis</h3>
                      <Badge className="bg-prism-green/10 text-prism-green border-prism-green/30">v2.1</Badge>
                    </div>
                    <p className="text-sm text-slate-600 mb-4 line-clamp-2">
                      You are an expert legislative analyst specializing in cost-of-living impacts. Analyze the provided bill text...
                    </p>
                    <div className="flex items-center gap-4 text-xs text-slate-400">
                      <span>Last updated: 2 days ago</span>
                      <span>•</span>
                      <span>Used in 1,234 analyses</span>
                    </div>
                  </div>
                  <Button variant="outline" size="sm" onClick={() => handleEdit({
                    id: 'demo-1',
                    prompt_type: 'impact_analysis',
                    system_prompt: 'You are an expert legislative analyst...',
                    version: 2.1,
                    is_active: true
                  } as unknown as SystemPrompt)} className="border-slate-200">
                    <Edit className="mr-2 h-4 w-4" /> Edit
                  </Button>
                </div>
              </div>

              <div className="card-prism p-6">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="font-mono text-prism-cyan font-medium">evidence_extraction</h3>
                      <Badge className="bg-prism-yellow/10 text-prism-yellow border-prism-yellow/30">v1.5</Badge>
                    </div>
                    <p className="text-sm text-slate-600 mb-4 line-clamp-2">
                      Extract and validate evidence sources from legislative documents. Identify citations...
                    </p>
                    <div className="flex items-center gap-4 text-xs text-slate-400">
                      <span>Last updated: 1 week ago</span>
                      <span>•</span>
                      <span>Used in 892 analyses</span>
                    </div>
                  </div>
                  <Button variant="outline" size="sm" onClick={() => handleEdit({
                    id: 'demo-2',
                    prompt_type: 'evidence_extraction',
                    system_prompt: 'Extract and validate evidence sources...',
                    version: 1.5,
                    is_active: true
                  } as unknown as SystemPrompt)} className="border-slate-200">
                    <Edit className="mr-2 h-4 w-4" /> Edit
                  </Button>
                </div>
              </div>

              <div className="card-prism p-6">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="font-mono text-prism-cyan font-medium">confidence_scoring</h3>
                      <Badge className="bg-prism-pink/10 text-prism-pink border-prism-pink/30">v1.0</Badge>
                    </div>
                    <p className="text-sm text-slate-600 mb-4 line-clamp-2">
                      Evaluate the confidence level of impact estimates based on available evidence quality...
                    </p>
                    <div className="flex items-center gap-4 text-xs text-slate-400">
                      <span>Last updated: 3 weeks ago</span>
                      <span>•</span>
                      <span>Used in 567 analyses</span>
                    </div>
                  </div>
                  <Button variant="outline" size="sm" onClick={() => handleEdit({
                    id: 'demo-3',
                    prompt_type: 'confidence_scoring',
                    system_prompt: 'Evaluate the confidence level...',
                    version: 1.0,
                    is_active: true
                  } as unknown as SystemPrompt)} className="border-slate-200">
                    <Edit className="mr-2 h-4 w-4" /> Edit
                  </Button>
                </div>
              </div>
            </>
          ) : (
            prompts.map((prompt) => (
              <div key={prompt.prompt_type} className="card-prism p-6">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="font-mono text-prism-cyan font-medium">{prompt.prompt_type}</h3>
                      <Badge className="bg-prism-cyan/10 text-prism-cyan border-prism-cyan/30">v{prompt.version}</Badge>
                    </div>
                    <p className="text-sm text-slate-600 mb-4 line-clamp-2">
                      {prompt.system_prompt.substring(0, 150)}...
                    </p>
                    <div className="flex items-center gap-4 text-xs text-slate-400">
                      <span>Last updated: Recently</span>
                    </div>
                  </div>
                  <Button variant="outline" size="sm" onClick={() => handleEdit(prompt)} className="border-slate-200">
                    <Edit className="mr-2 h-4 w-4" /> Edit
                  </Button>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
};

export default PromptsPage;
