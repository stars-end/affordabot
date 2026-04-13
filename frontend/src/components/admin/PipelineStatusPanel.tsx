'use client';

import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, ExternalLink, Loader2, RefreshCcw } from 'lucide-react';
import Link from 'next/link';
import { adminService } from '@/services/adminService';
import type {
    Jurisdiction,
    PipelineJurisdictionStatus,
    PipelineRefreshResponse,
} from '@/services/adminService';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';

const SOURCE_FAMILIES = [
    'meeting_minutes',
    'agendas',
    'legislation',
    'general_web_reference',
];

function formatTime(value?: string | null): string {
    if (!value) return 'n/a';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString();
}

export function PipelineStatusPanel() {
    const [jurisdictions, setJurisdictions] = useState<Jurisdiction[]>([]);
    const [selectedJurisdiction, setSelectedJurisdiction] = useState<string>('');
    const [sourceFamily, setSourceFamily] = useState<string>('meeting_minutes');

    const [status, setStatus] = useState<PipelineJurisdictionStatus | null>(null);
    const [refreshAck, setRefreshAck] = useState<PipelineRefreshResponse | null>(null);

    const [loading, setLoading] = useState(false);
    const [refreshing, setRefreshing] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const loadJurisdictions = async () => {
            try {
                const data = await adminService.getJurisdictions();
                setJurisdictions(data);
                setSelectedJurisdiction((current) => current || data[0]?.id || '');
            } catch (err) {
                console.error('Failed to load jurisdictions for pipeline panel:', err);
                setError('Unable to load jurisdictions');
            }
        };
        loadJurisdictions();
    }, []);

    const loadStatus = async (jurisdictionId: string, family: string) => {
        setLoading(true);
        setError(null);
        try {
            const statusData = await adminService.getPipelineJurisdictionStatus(
                jurisdictionId,
                family,
            );
            setStatus(statusData);
        } catch (err) {
            console.error('Failed to load pipeline jurisdiction status:', err);
            setStatus(null);
            setError('Failed to load pipeline status');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (!selectedJurisdiction) return;
        loadStatus(selectedJurisdiction, sourceFamily);
    }, [selectedJurisdiction, sourceFamily]);

    const statusBadge = useMemo(() => {
        const value = status?.pipeline_status || 'unknown';
        if (value === 'fresh') return <Badge className="bg-emerald-600 text-white">fresh</Badge>;
        if (value.includes('usable')) return <Badge className="bg-amber-500 text-black">{value}</Badge>;
        if (value.includes('blocked')) return <Badge variant="destructive">{value}</Badge>;
        return <Badge variant="outline">{value}</Badge>;
    }, [status?.pipeline_status]);

    const handleRefresh = async () => {
        if (!selectedJurisdiction) return;
        setRefreshing(true);
        try {
            const ack = await adminService.refreshPipelineJurisdiction(
                selectedJurisdiction,
                sourceFamily,
            );
            setRefreshAck(ack);
            await loadStatus(selectedJurisdiction, sourceFamily);
        } catch (err) {
            console.error('Failed to request pipeline refresh:', err);
            setError('Manual refresh request failed');
        } finally {
            setRefreshing(false);
        }
    };

    const pipelineRunId = status?.latest_pipeline_run_id || status?.operator_links?.pipeline_run_id || null;

    return (
        <Card data-testid="pipeline-status-panel">
            <CardHeader>
                <CardTitle>Pipeline Status</CardTitle>
                <CardDescription>
                    Backend-authored pipeline summary with freshness and evidence readiness.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                    <div className="space-y-1">
                        <Label htmlFor="pipeline-jurisdiction">Jurisdiction</Label>
                        <select
                            id="pipeline-jurisdiction"
                            className="h-9 w-full rounded border border-slate-300 bg-white px-2 text-sm"
                            value={selectedJurisdiction}
                            onChange={(event) => setSelectedJurisdiction(event.target.value)}
                        >
                            {jurisdictions.map((jur) => (
                                <option key={jur.id} value={jur.id}>
                                    {jur.name}
                                </option>
                            ))}
                        </select>
                    </div>
                    <div className="space-y-1">
                        <Label htmlFor="pipeline-source-family">Source family</Label>
                        <select
                            id="pipeline-source-family"
                            className="h-9 w-full rounded border border-slate-300 bg-white px-2 text-sm"
                            value={sourceFamily}
                            onChange={(event) => setSourceFamily(event.target.value)}
                        >
                            {SOURCE_FAMILIES.map((family) => (
                                <option key={family} value={family}>
                                    {family}
                                </option>
                            ))}
                        </select>
                    </div>
                    <div className="flex items-end gap-2">
                        <Button
                            variant="outline"
                            className="w-full"
                            onClick={() => loadStatus(selectedJurisdiction, sourceFamily)}
                            disabled={loading || !selectedJurisdiction}
                        >
                            {loading ? (
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            ) : (
                                <RefreshCcw className="mr-2 h-4 w-4" />
                            )}
                            Reload Status
                        </Button>
                        <Button
                            className="w-full"
                            onClick={handleRefresh}
                            disabled={refreshing || !selectedJurisdiction}
                        >
                            {refreshing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                            Queue Refresh
                        </Button>
                    </div>
                </div>

                {error ? (
                    <Alert variant="destructive">
                        <AlertTriangle className="h-4 w-4" />
                        <AlertTitle>Pipeline status error</AlertTitle>
                        <AlertDescription>{error}</AlertDescription>
                    </Alert>
                ) : null}

                {status ? (
                    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                        <div className="rounded border border-slate-200 p-3">
                            <div className="mb-2 flex items-center justify-between">
                                <p className="text-sm font-medium text-slate-900">
                                    {status.jurisdiction_name} / {status.source_family}
                                </p>
                                {statusBadge}
                            </div>
                            <p className="text-xs text-slate-600">
                                Last success: {formatTime(status.last_success_at)}
                            </p>
                            <p className="mt-2 text-xs text-slate-600">
                                Freshness policy: {status.freshness.fresh_hours}h fresh,{' '}
                                {status.freshness.stale_usable_ceiling_hours}h usable stale,{' '}
                                {status.freshness.fail_closed_ceiling_hours}h fail-closed.
                            </p>
                            {status.operator_links.windmill_run_url ? (
                                <a
                                    href={status.operator_links.windmill_run_url}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="mt-3 inline-flex items-center text-xs text-blue-700 underline"
                                >
                                    Open Windmill run <ExternalLink className="ml-1 h-3 w-3" />
                                </a>
                            ) : null}
                            {pipelineRunId ? (
                                <Link
                                    href={`/admin/audits/trace/${encodeURIComponent(pipelineRunId)}`}
                                    className="mt-2 inline-flex items-center text-xs text-blue-700 underline"
                                >
                                    Open Audit Trace run <ExternalLink className="ml-1 h-3 w-3" />
                                </Link>
                            ) : null}
                        </div>
                        <div className="rounded border border-slate-200 p-3">
                            <p className="text-sm font-medium text-slate-900">Counts</p>
                            <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-slate-700">
                                <span>Search: {status.counts.search_results}</span>
                                <span>Raw scrapes: {status.counts.raw_scrapes}</span>
                                <span>Artifacts: {status.counts.artifacts}</span>
                                <span>Chunks: {status.counts.chunks}</span>
                                <span>Analyses: {status.counts.analyses}</span>
                                <span>Evidence: {status.latest_analysis.evidence_count}</span>
                            </div>
                            <p className="mt-3 text-xs text-slate-600">
                                Analysis: {status.latest_analysis.status} / {status.latest_analysis.sufficiency_state}
                            </p>
                        </div>
                    </div>
                ) : null}

                {status && (status.alerts.length > 0 || status.freshness.alerts.length > 0) ? (
                    <div className="rounded border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900">
                        {(status.freshness.alerts.length > 0
                            ? status.freshness.alerts
                            : status.alerts
                        ).join(', ')}
                    </div>
                ) : null}

                {refreshAck ? (
                    <div className="rounded border border-slate-200 bg-slate-50 p-2 text-xs text-slate-600">
                        {refreshAck.message}
                    </div>
                ) : null}
            </CardContent>
        </Card>
    );
}
