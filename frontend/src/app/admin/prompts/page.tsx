"use client";

import React, { useState, useEffect } from 'react';
import { promptService, SystemPrompt } from '@/services/PromptService';

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
      
      // Update the UI with the new prompt data
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
    return <div>Loading prompts...</div>;
  }

  if (error) {
    return <div className="text-red-500">{error}</div>;
  }

  return (
    <div className="container mx-auto p-4">
      <h1 className="text-3xl font-bold mb-6">System Prompts</h1>
      
      {editingPrompt ? (
        <div className="bg-white p-6 rounded-lg shadow-md">
          <h2 className="text-2xl font-semibold mb-4">
            Edit Prompt: <span className="font-mono text-blue-600">{editingPrompt.prompt_type}</span> (v{editingPrompt.version})
          </h2>
          <textarea
            className="w-full h-96 p-2 border border-gray-300 rounded-md font-mono text-sm"
            value={editedContent}
            onChange={(e) => setEditedContent(e.target.value)}
          />
          <div className="mt-4 flex space-x-2">
            <button
              onClick={handleSave}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              Save Changes
            </button>
            <button
              onClick={handleCancel}
              className="px-4 py-2 bg-gray-300 text-gray-800 rounded-md hover:bg-gray-400"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {prompts.map((prompt) => (
            <div key={prompt.id} className="bg-white p-6 rounded-lg shadow-md">
              <div className="flex justify-between items-center mb-2">
                <h3 className="text-xl font-semibold">
                  {prompt.prompt_type}
                </h3>
                <div>
                  <span className={`px-2 py-1 text-xs font-semibold rounded-full ${
                    prompt.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                  }`}>
                    {prompt.is_active ? 'Active' : 'Inactive'}
                  </span>
                  <span className="ml-2 text-sm text-gray-500">v{prompt.version}</span>
                </div>
              </div>
              <pre className="bg-gray-50 p-4 rounded-md text-sm whitespace-pre-wrap font-mono">
                {prompt.system_prompt}
              </pre>
              <div className="mt-4">
                <button
                  onClick={() => handleEdit(prompt)}
                  className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
                >
                  Edit
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default PromptsPage;
