export interface AgentStep {
    tool: string;
    args: Record<string, any>;
    result: any;
    task_id: string;
    query_id: string;
    timestamp: number;
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export async function listAgentSessions(): Promise<string[]> {
    const res = await fetch(`${API_BASE}/admin/traces`);
    if (!res.ok) throw new Error('Failed to fetch sessions');
    return res.json();
}


export interface PipelineStep {
    id: string;
    run_id: string;
    step_number: number;
    step_name: string;
    status: string;
    input_context?: Record<string, any>;
    output_result?: Record<string, any>;
    model_info?: Record<string, any>;
    duration_ms?: number;
    created_at?: string;
}

export async function getAgentTraces(queryId: string): Promise<AgentStep[]> {
    const res = await fetch(`${API_BASE}/admin/traces/${queryId}`);
    if (!res.ok) throw new Error('Failed to fetch traces');
    return res.json();
}

export async function getRunSteps(runId: string): Promise<PipelineStep[]> {
    const res = await fetch(`${API_BASE}/admin/runs/${runId}/steps`);
    if (!res.ok) return []; // Return empty if not found or old run
    return res.json();
}
