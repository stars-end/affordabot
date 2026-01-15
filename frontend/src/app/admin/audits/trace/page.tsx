"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Loader2, Search, Eye, AlertTriangle, CheckCircle } from "lucide-react"
import Link from "next/link"

interface PipelineRun {
    id: string
    bill_id: string
    jurisdiction: string
    status: 'running' | 'completed' | 'failed'
    created_at: string
    completed_at?: string
    models: Record<string, string>
}

export default function AuditTracePage() {
    const [runs, setRuns] = useState<PipelineRun[]>([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        const loadRuns = async () => {
            try {
                const res = await fetch('/api/admin/pipeline-runs')
                if (res.ok) {
                    const data = await res.json()
                    setRuns(data.runs || [])
                }
            } catch (error) {
                console.error('Failed to load pipeline runs:', error)
            } finally {
                setLoading(false)
            }
        }
        loadRuns()
    }, [])

    const getStatusBadge = (status: string) => {
        switch (status) {
            case 'completed':
                return <Badge className="bg-green-100 text-green-800"><CheckCircle className="w-3 h-3 mr-1" />Completed</Badge>
            case 'failed':
                return <Badge variant="destructive"><AlertTriangle className="w-3 h-3 mr-1" />Failed</Badge>
            case 'running':
                return <Badge variant="secondary"><Loader2 className="w-3 h-3 mr-1 animate-spin" />Running</Badge>
            default:
                return <Badge variant="outline">{status}</Badge>
        }
    }

    return (
        <div className="p-8 space-y-6">
            <div className="space-y-2">
                <h1 className="text-3xl font-bold tracking-tight">Audit Trace</h1>
                <p className="text-muted-foreground">
                    View pipeline runs and debug LLM analysis steps.
                </p>
            </div>

            {loading && (
                <div className="flex items-center justify-center py-12">
                    <Loader2 className="w-8 h-8 animate-spin text-purple-600" />
                </div>
            )}

            {!loading && runs.length === 0 && (
                <Card>
                    <CardContent className="py-12 text-center">
                        <Search className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
                        <h3 className="text-lg font-medium mb-2">No Pipeline Runs Found</h3>
                        <p className="text-muted-foreground">
                            Pipeline runs will appear here once bills are analyzed.
                        </p>
                    </CardContent>
                </Card>
            )}

            <div className="grid gap-4">
                {runs.map((run) => (
                    <Card key={run.id} className="hover:border-purple-200 transition-colors">
                        <CardHeader className="pb-3">
                            <div className="flex items-start justify-between">
                                <div>
                                    <CardTitle className="text-lg">{run.bill_id}</CardTitle>
                                    <CardDescription>{run.jurisdiction}</CardDescription>
                                </div>
                                {getStatusBadge(run.status)}
                            </div>
                        </CardHeader>
                        <CardContent>
                            <div className="flex items-center justify-between">
                                <div className="text-sm text-muted-foreground">
                                    <p>Started: {new Date(run.created_at).toLocaleString()}</p>
                                    {run.completed_at && (
                                        <p>Completed: {new Date(run.completed_at).toLocaleString()}</p>
                                    )}
                                </div>
                                <Link href={`/admin/audits/trace/${run.id}`}>
                                    <Button variant="outline" size="sm">
                                        <Eye className="w-4 h-4 mr-2" />
                                        View Details
                                    </Button>
                                </Link>
                            </div>
                        </CardContent>
                    </Card>
                ))}
            </div>
        </div>
    )
}
