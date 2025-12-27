// Mock prompt structure
export interface SystemPrompt {
  id: string;
  prompt_type: string;
  system_prompt: string;
  description?: string;
  is_active: boolean;
  version: number;
}

const API_BASE_URL = '';

class PromptService {
  async getPrompts(): Promise<SystemPrompt[]> {
    // Calls GET /admin/prompts
    const response = await fetch(`${API_BASE_URL}/api/admin/prompts`);
    if (!response.ok) {
      throw new Error('Failed to fetch prompts');
    }
    return await response.json();
  }

  async updatePrompt(promptType: string, content: string, description?: string): Promise<SystemPrompt> {
    // Calls POST /admin/prompts
    const response = await fetch(`${API_BASE_URL}/api/admin/prompts`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        type: promptType,
        system_prompt: content
        // description is currently not supported in backend PromptUpdate model
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || 'Failed to update prompt');
    }

    // The backend returns success message. Fetch updated prompt to return full object.
    const updatedPrompt = await this.getPrompt(promptType);
    return updatedPrompt;
  }

  async getPrompt(promptType: string): Promise<SystemPrompt> {
    // Calls GET /admin/prompts/{promptType}
    const response = await fetch(`${API_BASE_URL}/api/admin/prompts/${promptType}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch prompt: ${promptType}`);
    }
    return await response.json();
  }
}

export const promptService = new PromptService();
