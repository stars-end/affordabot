'use client';

import { useEffect, useState } from 'react';
import { AlertTriangle, Loader2, RefreshCcw, Search } from 'lucide-react';
import { adminService } from '@/services/adminService';
import type {
    SubstrateFailureBucket,
    SubstrateRawScrapeDetail,
    SubstrateRawScrapeRow,
    SubstrateRun,
    SubstrateRunDetail,
    SubstrateRunRawFilters,
} from '@/services/adminService';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

const RUN_PAGE_SIZE = 30;
const RAW_ROWS_PAGE_SIZE = 80;
const CONTENT_PREVIEW_TRUNCATE_AT = 1200;

function formatTime(value?: string | null): string {
    if (!value) return 'n/a';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString();
}

function toNumber(value: unknown): number {
    if (typeof value === 'number') return value;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
}

function bucketReason(bucket: SubstrateFailureBucket): string {
    const reason = bucket.reason ?? bucket.reason_category ?? bucket.bucket ?? bucket.stage ?? 'unknown';
    return String(reason);
}

export function SubstrateExplorer() {
    const [runs, setRuns] = useState<SubstrateRun[]>([]);
    const [runsLoading, setRunsLoading] = useState(false);
    const [runsError, setRunsError] = useState<string | null>(null);
    const [runsOffset, setRunsOffset] = useState(0);

    const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
    const [runDetail, setRunDetail] = useState<SubstrateRunDetail | null>(null);
    const [detailLoading, setDetailLoading] = useState(false);

    const [failureBuckets, setFailureBuckets] = useState<SubstrateFailureBucket[]>([]);
    const [bucketLoading, setBucketLoading] = useState(false);

    const [rawRows, setRawRows] = useState<SubstrateRawScrapeRow[]>([]);
    const [rawRowsLoading, setRawRowsLoading] = useState(false);
    const [rawRowsOffset, setRawRowsOffset] = useState(0);

    const [filters, setFilters] = useState<SubstrateRunRawFilters>({
        jurisdiction_name: '',
        document_type: '',
        promotion_state: '',
        trust_tier: '',
        content_class: '',
    });

    const [selectedRawId, setSelectedRawId] = useState<string | null>(null);
    const [rawDetail, setRawDetail] = useState<SubstrateRawScrapeDetail | null>(null);
    const [rawDetailLoading, setRawDetailLoading] = useState(false);
    const [copiedRunId, setCopiedRunId] = useState(false);

    const loadRuns = async (offset = runsOffset) => {
        setRunsLoading(true);
        setRunsError(null);
        try {
            const data = await adminService.getSubstrateRuns(RUN_PAGE_SIZE, offset);
            setRuns(data.runs || []);
            if (data.runs?.length && (!selectedRunId || !data.runs.some((run) => run.run_id === selectedRunId))) {
                setSelectedRunId(data.runs[0].run_id);
            }
        } catch (error) {
            console.error('Failed to load substrate runs:', error);
            setRunsError('Failed to load substrate runs.');
        } finally {
            setRunsLoading(false);
        }
    };

    const loadRunDetail = async (runId: string) => {
        setDetailLoading(true);
        try {
            const data = await adminService.getSubstrateRunDetail(runId);
            setRunDetail(data);
        } catch (error) {
            console.error('Failed to load run detail:', error);
            setRunDetail(null);
        } finally {
            setDetailLoading(false);
        }
    };

    const loadFailureBuckets = async (runId: string) => {
        setBucketLoading(true);
        try {
            const data = await adminService.getSubstrateFailureBuckets(runId);
            setFailureBuckets(data.failure_buckets || []);
        } catch (error) {
            console.error('Failed to load failure buckets:', error);
            setFailureBuckets([]);
        } finally {
            setBucketLoading(false);
        }
    };

    const loadRawRows = async (runId: string, activeFilters: SubstrateRunRawFilters, offset = rawRowsOffset) => {
        setRawRowsLoading(true);
        try {
            const data = await adminService.getSubstrateRunRawScrapes(runId, {
                limit: RAW_ROWS_PAGE_SIZE,
                offset,
                filters: activeFilters,
            });
            setRawRows(data.raw_scrapes || []);
            if (data.raw_scrapes?.length) {
                setSelectedRawId((prev) => prev ?? data.raw_scrapes[0].id);
            } else {
                setSelectedRawId(null);
                setRawDetail(null);
            }
        } catch (error) {
            console.error('Failed to load raw rows:', error);
            setRawRows([]);
        } finally {
            setRawRowsLoading(false);
        }
    };

    const loadRawDetail = async (rawId: string) => {
        setRawDetailLoading(true);
        try {
            const data = await adminService.getSubstrateRawScrapeDetail(rawId);
            setRawDetail(data);
        } catch (error) {
            console.error('Failed to load raw row detail:', error);
            setRawDetail(null);
        } finally {
            setRawDetailLoading(false);
        }
    };

    useEffect(() => {
        loadRuns(runsOffset);
    }, [runsOffset]);

    useEffect(() => {
        if (!selectedRunId) return;
        setSelectedRawId(null);
        setRawDetail(null);
        loadRunDetail(selectedRunId);
        loadFailureBuckets(selectedRunId);
        loadRawRows(selectedRunId, filters, rawRowsOffset);
    }, [selectedRunId, rawRowsOffset]);

    useEffect(() => {
        if (!selectedRawId) return;
        loadRawDetail(selectedRawId);
    }, [selectedRawId]);

    const applyFilters = () => {
        if (!selectedRunId) return;
        setRawRowsOffset(0);
        setSelectedRawId(null);
        setRawDetail(null);
        loadRawRows(selectedRunId, filters, 0);
    };

    const clearFilters = () => {
        const cleared = {
            jurisdiction_name: '',
            document_type: '',
            promotion_state: '',
            trust_tier: '',
            content_class: '',
        };
        setFilters(cleared);
        if (!selectedRunId) return;
        setRawRowsOffset(0);
        setSelectedRawId(null);
        setRawDetail(null);
        loadRawRows(selectedRunId, cleared, 0);
    };

    const summary = runDetail?.summary || {};
    const promotionCounts = (summary.promotion_state_counts as Record<string, unknown> | undefined) || {};
    const stageCounts = (summary.ingestion_truth_stage_counts as Record<string, unknown> | undefined) || {};
    const failureCount = failureBuckets.reduce((total, bucket) => total + toNumber(bucket.count), 0);
    const topStages = Object.entries(stageCounts)
        .sort((left, right) => toNumber(right[1]) - toNumber(left[1]))
        .slice(0, 3);
    const topJurisdictions = runDetail?.jurisdiction_names.slice(0, 4) || [];

    const jumpToSection = (sectionId: string) => {
        const node = document.getElementById(sectionId);
        if (node) {
            node.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    };

    const copyRunId = async () => {
        if (!selectedRunId || typeof navigator === 'undefined' || !navigator.clipboard) return;
        await navigator.clipboard.writeText(selectedRunId);
        setCopiedRunId(true);
        window.setTimeout(() => setCopiedRunId(false), 1500);
    };

    const hasNextRunsPage = runs.length === RUN_PAGE_SIZE;
    const hasNextRawRowsPage = rawRows.length === RAW_ROWS_PAGE_SIZE;
    const previewText = rawDetail?.content_preview || '';
    const previewIsTruncated = previewText.length > CONTENT_PREVIEW_TRUNCATE_AT;
    const visiblePreview = previewIsTruncated
        ? `${previewText.slice(0, CONTENT_PREVIEW_TRUNCATE_AT).trimEnd()}\n\n... (truncated for operator safety)`
        : previewText || 'n/a';

    return (
        <div className="space-y-6" data-testid="substrate-explorer">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold tracking-tight text-slate-900" data-testid="substrate-title">
                        Substrate Explorer
                    </h2>
                    <p className="text-sm text-slate-600">
                        Run-first debugging for raw substrate captures, failures, and row-level inspection.
                    </p>
                </div>
                <Button
                    variant="outline"
                    onClick={() => loadRuns(runsOffset)}
                    disabled={runsLoading}
                    data-testid="substrate-runs-refresh"
                >
                    {runsLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCcw className="mr-2 h-4 w-4" />}
                    Refresh Runs
                </Button>
            </div>

            {runsError && (
                <Alert variant="destructive">
                    <AlertTriangle className="h-4 w-4" />
                    <AlertTitle>Run Load Error</AlertTitle>
                    <AlertDescription>{runsError}</AlertDescription>
                </Alert>
            )}

            <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
                <Card className="xl:col-span-1" data-testid="substrate-run-list">
                    <CardHeader>
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                            <div>
                                <CardTitle>Recent Runs</CardTitle>
                                <CardDescription>Choose a run to inspect what worked and what failed.</CardDescription>
                            </div>
                            <div className="flex items-center gap-2 text-xs text-slate-500">
                                <span>Offset {runsOffset + 1}</span>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => setRunsOffset((prev) => Math.max(prev - RUN_PAGE_SIZE, 0))}
                                    disabled={runsLoading || runsOffset === 0}
                                >
                                    Previous
                                </Button>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => setRunsOffset((prev) => prev + RUN_PAGE_SIZE)}
                                    disabled={runsLoading || !hasNextRunsPage}
                                >
                                    Next
                                </Button>
                            </div>
                        </div>
                    </CardHeader>
                    <CardContent>
                        <ScrollArea className="h-[420px] pr-2">
                            <div className="space-y-2">
                                {runs.map((run) => {
                                    const selected = selectedRunId === run.run_id;
                                    return (
                                        <button
                                            type="button"
                                            key={run.run_id}
                                            data-testid="substrate-run-item"
                                            className={`w-full rounded border p-3 text-left transition ${
                                                selected ? 'border-slate-900 bg-slate-50' : 'border-slate-200 hover:bg-slate-50'
                                            }`}
                                            onClick={() => {
                                                setRawRowsOffset(0);
                                                setSelectedRunId(run.run_id);
                                            }}
                                        >
                                            <div className="flex items-start justify-between gap-3">
                                                <div className="min-w-0">
                                                    <p className="truncate text-xs font-mono text-slate-800">{run.run_id}</p>
                                                    <p className="mt-1 text-xs text-slate-500">{formatTime(run.last_created_at)}</p>
                                                </div>
                                                <Badge variant="outline">{run.status}</Badge>
                                            </div>
                                            <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-slate-600">
                                                <span>Rows: {run.raw_scrapes_total}</span>
                                                <span>Errors: {run.raw_capture_error_count}</span>
                                                <span>Promoted: {run.promoted_substrate_count}</span>
                                                <span>Retrievable: {run.retrievable_count}</span>
                                            </div>
                                        </button>
                                    );
                                })}
                                {!runsLoading && runs.length === 0 && (
                                    <p className="text-sm text-slate-500" data-testid="substrate-run-list-empty">
                                        No substrate runs found.
                                    </p>
                                )}
                            </div>
                        </ScrollArea>
                    </CardContent>
                </Card>

                <div className="space-y-6 xl:col-span-2">
                    <Card>
                        <CardHeader>
                            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                                <div>
                                    <CardTitle>Run Summary</CardTitle>
                                    <CardDescription>
                                        {selectedRunId ? `Run: ${selectedRunId}` : 'Select a run to view summary'}
                                    </CardDescription>
                                </div>
                                <div className="flex flex-wrap gap-2">
                                    <Button variant="outline" size="sm" onClick={copyRunId} disabled={!selectedRunId}>
                                        {copiedRunId ? 'Copied Run ID' : 'Copy Run ID'}
                                    </Button>
                                    <Button variant="outline" size="sm" onClick={() => jumpToSection('substrate-failure-buckets')} disabled={!runDetail}>
                                        Jump To Failures
                                    </Button>
                                    <Button variant="outline" size="sm" onClick={() => jumpToSection('substrate-raw-rows')} disabled={!runDetail}>
                                        Jump To Raw Rows
                                    </Button>
                                </div>
                            </div>
                        </CardHeader>
                        <CardContent>
                            {detailLoading ? (
                                <div className="flex items-center text-sm text-slate-600">
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Loading run summary...
                                </div>
                            ) : runDetail ? (
                                <div className="space-y-4">
                                    <div className="rounded border bg-slate-50 p-3">
                                        <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Operator Snapshot</p>
                                        <div className="mt-2 grid gap-2 text-sm text-slate-700 md:grid-cols-3">
                                            <div>
                                                <span className="font-medium text-slate-900">Latest capture:</span>{' '}
                                                {formatTime(runDetail.latest_created_at)}
                                            </div>
                                            <div>
                                                <span className="font-medium text-slate-900">Failure rows:</span>{' '}
                                                {failureCount}
                                            </div>
                                            <div>
                                                <span className="font-medium text-slate-900">Jurisdictions:</span>{' '}
                                                {runDetail.jurisdiction_names.length}
                                            </div>
                                        </div>
                                    </div>
                                    <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
                                        <Metric label="Raw Rows" value={toNumber(runDetail.raw_scrapes_total)} />
                                        <Metric label="Promoted" value={toNumber(promotionCounts.promoted_substrate)} />
                                        <Metric label="Durable Raw" value={toNumber(promotionCounts.durable_raw)} />
                                        <Metric label="Captured Candidate" value={toNumber(promotionCounts.captured_candidate)} />
                                        <Metric label="Failure Buckets" value={failureBuckets.length} />
                                    </div>
                                    <div className="grid gap-3 md:grid-cols-2">
                                        <div className="rounded border p-3">
                                            <p className="text-xs font-semibold text-slate-700">Top Ingestion Stages</p>
                                            <div className="mt-2 flex flex-wrap gap-2">
                                                {topStages.length ? (
                                                    topStages.map(([stage, count]) => (
                                                        <Badge key={stage} variant="outline">
                                                            {stage}: {toNumber(count)}
                                                        </Badge>
                                                    ))
                                                ) : (
                                                    <span className="text-xs text-slate-500">No stage summary available.</span>
                                                )}
                                            </div>
                                        </div>
                                        <div className="rounded border p-3">
                                            <p className="text-xs font-semibold text-slate-700">Jurisdiction Scope</p>
                                            <div className="mt-2 flex flex-wrap gap-2">
                                                {topJurisdictions.length ? (
                                                    <>
                                                        {topJurisdictions.map((name) => (
                                                            <Badge key={name} variant="secondary">
                                                                {name}
                                                            </Badge>
                                                        ))}
                                                        {runDetail.jurisdiction_names.length > topJurisdictions.length && (
                                                            <Badge variant="outline">
                                                                +{runDetail.jurisdiction_names.length - topJurisdictions.length} more
                                                            </Badge>
                                                        )}
                                                    </>
                                                ) : (
                                                    <span className="text-xs text-slate-500">No jurisdictions recorded.</span>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            ) : (
                                <p className="text-sm text-slate-500">Run summary unavailable.</p>
                            )}
                        </CardContent>
                    </Card>

                    <Card id="substrate-failure-buckets" data-testid="substrate-failure-buckets-section">
                        <CardHeader>
                            <CardTitle>Failure Buckets</CardTitle>
                            <CardDescription>Top grouped failure reasons for this run.</CardDescription>
                        </CardHeader>
                        <CardContent>
                            {bucketLoading ? (
                                <div className="flex items-center text-sm text-slate-600">
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Loading failure buckets...
                                </div>
                            ) : failureBuckets.length ? (
                                <div className="space-y-3">
                                    <div className="flex flex-wrap gap-2">
                                        {failureBuckets.map((bucket, index) => (
                                            <Badge key={`${bucketReason(bucket)}-pill-${index}`} variant="secondary">
                                                {bucketReason(bucket)} ({toNumber(bucket.count)})
                                            </Badge>
                                        ))}
                                    </div>
                                    <Table data-testid="substrate-failure-buckets-table">
                                        <TableHeader>
                                            <TableRow>
                                                <TableHead>Reason</TableHead>
                                                <TableHead className="w-24">Count</TableHead>
                                            </TableRow>
                                        </TableHeader>
                                        <TableBody>
                                            {failureBuckets.map((bucket, index) => (
                                                <TableRow key={`${bucketReason(bucket)}-${index}`}>
                                                    <TableCell className="text-sm">{bucketReason(bucket)}</TableCell>
                                                    <TableCell>{toNumber(bucket.count)}</TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                    </Table>
                                </div>
                            ) : (
                                <p className="text-sm text-slate-500" data-testid="substrate-failure-buckets-empty">
                                    No failure buckets for this run.
                                </p>
                            )}
                        </CardContent>
                    </Card>
                </div>
            </div>

            <Card id="substrate-raw-rows" data-testid="substrate-raw-rows-section">
                <CardHeader>
                    <CardTitle>Run Raw Rows</CardTitle>
                    <CardDescription>
                        Filter and inspect row-level substrate captures. {rawRows.length ? `${rawRows.length} row(s) loaded.` : 'No rows loaded yet.'}
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="grid grid-cols-1 gap-3 md:grid-cols-3 xl:grid-cols-5">
                        <FilterInput
                            label="Jurisdiction"
                            value={filters.jurisdiction_name || ''}
                            onChange={(value) => setFilters((prev) => ({ ...prev, jurisdiction_name: value }))}
                        />
                        <FilterInput
                            label="Document Type"
                            value={filters.document_type || ''}
                            onChange={(value) => setFilters((prev) => ({ ...prev, document_type: value }))}
                        />
                        <FilterInput
                            label="Promotion State"
                            value={filters.promotion_state || ''}
                            onChange={(value) => setFilters((prev) => ({ ...prev, promotion_state: value }))}
                        />
                        <FilterInput
                            label="Trust Tier"
                            value={filters.trust_tier || ''}
                            onChange={(value) => setFilters((prev) => ({ ...prev, trust_tier: value }))}
                        />
                        <FilterInput
                            label="Content Class"
                            value={filters.content_class || ''}
                            onChange={(value) => setFilters((prev) => ({ ...prev, content_class: value }))}
                        />
                    </div>
                    <div className="flex flex-wrap gap-2">
                        <Button onClick={applyFilters} disabled={!selectedRunId || rawRowsLoading}>
                            <Search className="mr-2 h-4 w-4" />
                            Apply Filters
                        </Button>
                        <Button variant="outline" onClick={clearFilters} disabled={!selectedRunId || rawRowsLoading}>
                            Clear
                        </Button>
                        <div className="ml-auto flex items-center gap-2 text-xs text-slate-500">
                            <span>
                                Showing {rawRows.length} rows starting at {rawRowsOffset + 1}
                            </span>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setRawRowsOffset((prev) => Math.max(prev - RAW_ROWS_PAGE_SIZE, 0))}
                                disabled={!selectedRunId || rawRowsLoading || rawRowsOffset === 0}
                            >
                                Previous
                            </Button>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setRawRowsOffset((prev) => prev + RAW_ROWS_PAGE_SIZE)}
                                disabled={!selectedRunId || rawRowsLoading || !hasNextRawRowsPage}
                            >
                                Next
                            </Button>
                        </div>
                    </div>

                    {rawRowsLoading ? (
                        <div className="flex items-center text-sm text-slate-600">
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            Loading raw rows...
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
                            <ScrollArea className="h-[360px] rounded border">
                                <Table data-testid="substrate-raw-rows-table">
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead>Created</TableHead>
                                            <TableHead>Jurisdiction</TableHead>
                                            <TableHead>Doc Type</TableHead>
                                            <TableHead>State</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {rawRows.map((row) => (
                                            <TableRow
                                                key={row.id}
                                                onClick={() => setSelectedRawId(row.id)}
                                                data-testid="substrate-raw-row-item"
                                                className={selectedRawId === row.id ? 'bg-slate-50' : 'cursor-pointer'}
                                            >
                                                <TableCell className="text-xs">{formatTime(row.created_at)}</TableCell>
                                                <TableCell className="text-xs">{row.jurisdiction_name || 'n/a'}</TableCell>
                                                <TableCell className="text-xs">{row.document_type || 'n/a'}</TableCell>
                                                <TableCell className="text-xs">{row.promotion_state || 'n/a'}</TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                                {!rawRows.length && (
                                    <p className="p-4 text-sm text-slate-500" data-testid="substrate-raw-rows-empty">
                                        No raw rows match the current filters.
                                    </p>
                                )}
                            </ScrollArea>

                            <Card data-testid="substrate-raw-row-detail">
                                <CardHeader>
                                    <CardTitle className="text-base">Raw Row Detail</CardTitle>
                                    <CardDescription>{selectedRawId || 'Select a row to inspect details'}</CardDescription>
                                </CardHeader>
                                <CardContent>
                                    {rawDetailLoading ? (
                                        <div className="flex items-center text-sm text-slate-600">
                                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                            Loading row detail...
                                        </div>
                                    ) : rawDetail ? (
                                        <div className="space-y-3 text-sm">
                                            <Detail label="URL" value={rawDetail.url || 'n/a'} mono />
                                            <Detail label="Source URL" value={rawDetail.source_url || 'n/a'} mono />
                                            <Detail label="Storage URI" value={rawDetail.storage_uri || 'n/a'} mono />
                                            <Detail label="Document ID" value={rawDetail.document_id || 'n/a'} mono />
                                            <Detail label="Promotion State" value={rawDetail.promotion_state || 'n/a'} />
                                            <Detail label="Trust Tier" value={rawDetail.trust_tier || 'n/a'} />
                                            <Detail label="Content Class" value={rawDetail.content_class || 'n/a'} />
                                            <Detail label="Ingestion Stage" value={rawDetail.ingestion_truth_stage || 'n/a'} />
                                            <Detail label="Retrievable" value={String(rawDetail.ingestion_truth_retrievable)} />
                                            <Detail label="Error" value={rawDetail.error_message || 'none'} />
                                            <div>
                                                <p className="mb-1 text-xs font-semibold text-slate-700">Content Preview</p>
                                                <p className="whitespace-pre-wrap rounded border bg-slate-50 p-2 text-xs text-slate-700">
                                                    {visiblePreview}
                                                </p>
                                                {previewIsTruncated && (
                                                    <p className="mt-1 text-[11px] text-slate-500">
                                                        Full artifact preview stays deferred until post-MVP.
                                                    </p>
                                                )}
                                            </div>
                                            <div>
                                                <p className="mb-1 text-xs font-semibold text-slate-700">Metadata JSON</p>
                                                <pre
                                                    className="max-h-48 overflow-auto rounded border bg-slate-950 p-2 text-[11px] text-slate-100"
                                                    data-testid="substrate-raw-row-metadata-json"
                                                >
                                                    {JSON.stringify(rawDetail.metadata || {}, null, 2)}
                                                </pre>
                                            </div>
                                        </div>
                                    ) : (
                                        <p className="text-sm text-slate-500" data-testid="substrate-raw-row-detail-empty">
                                            No row detail loaded.
                                        </p>
                                    )}
                                </CardContent>
                            </Card>
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}

function Metric({ label, value }: { label: string; value: number }) {
    return (
        <div className="rounded border bg-slate-50 p-3">
            <p className="text-xs text-slate-500">{label}</p>
            <p className="mt-1 text-xl font-semibold text-slate-900">{value}</p>
        </div>
    );
}

function FilterInput({
    label,
    value,
    onChange,
}: {
    label: string;
    value: string;
    onChange: (value: string) => void;
}) {
    return (
        <div className="space-y-1">
            <Label className="text-xs text-slate-600">{label}</Label>
            <Input value={value} onChange={(event) => onChange(event.target.value)} />
        </div>
    );
}

function Detail({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
    return (
        <div>
            <p className="text-xs font-semibold text-slate-700">{label}</p>
            <p className={`text-xs text-slate-700 ${mono ? 'font-mono break-all' : ''}`}>{value}</p>
        </div>
    );
}
