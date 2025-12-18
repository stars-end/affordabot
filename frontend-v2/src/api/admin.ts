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

export async function getAgentTraces(queryId: string): Promise<AgentStep[]> {
    const res = await fetch(`${API_BASE}/admin/traces/${queryId}`);
    if (!res.ok) throw new Error('Failed to fetch traces');
    return res.json();
}
