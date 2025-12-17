
// Mock prompt structure
export interface SystemPrompt {
  id: string;
  prompt_type: string;
  system_prompt: string;
  is_active: boolean;
  version: number;
}

const API_BASE_URL = process.env.BACKEND_URL || 'http://localhost:8000';

class PromptService {
  async getPrompts(): Promise<SystemPrompt[]> {
    const response = await fetch(`${API_BASE_URL}/prompts`);
    if (!response.ok) {
      throw new Error('Failed to fetch prompts');
    }
    return await response.json();
  }

  async updatePrompt(promptType: string, content: string, description?: string): Promise<SystemPrompt> {
    const response = await fetch(`${API_BASE_URL}/prompts/${promptType}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ 
        prompt_type: promptType, 
        system_prompt: content,
        description: description || `Updated via Admin UI`
      }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Failed to update prompt');
    }

    // The backend returns a {prompt_type, new_version} object on success.
    // We can't return a full SystemPrompt object without fetching it again.
    // For now, we'll just return a partial object and let the UI handle it.
    const updateResult = await response.json();
    
    // To give a more complete response, let's fetch the updated prompt
    const updatedPrompt = await this.getPrompt(promptType);
    return updatedPrompt;
  }

  async getPrompt(promptType: string): Promise<SystemPrompt> {
    const response = await fetch(`${API_BASE_URL}/prompts/${promptType}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch prompt: ${promptType}`);
    }
    return await response.json();
  }
}

export const promptService = new PromptService();
