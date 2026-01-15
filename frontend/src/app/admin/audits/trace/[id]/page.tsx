"use client"

import { useState, useEffect } from "react"
import { useParams } from "next/navigation"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Loader2, ArrowLeft, Copy, CheckCircle, AlertTriangle, ExternalLink } from "lucide-react"
import Link from "next/link"

interface PipelineStep {
    step_name: string
    model: string
    input: string
    output: string
    created_at: string
}

interface PipelineDetail {
    id: string
    bill_id: string
    jurisdiction: string
    status: string
    created_at: string
    completed_at?: string
    steps: PipelineStep[]
    analysis?: Record<string, unknown>
    error?: string
}

export default function AuditTraceDetailPage() {
    const params = useParams()
    const [detail, setDetail] = useState<PipelineDetail | null>(null)
    const [loading, setLoading] = useState(true)
    const [copiedStep, setCopiedStep] = useState<string | null>(null)

    useEffect(() => {
        const loadDetail = async () => {
            try {
                const res = await fetch(`/api/admin/pipeline-runs/${params.id}`)
                if (res.ok) {
                    const data = await res.json()
                    setDetail(data)
                }
            } catch (error) {
                console.error('Failed to load pipeline detail:', error)
            } finally {
                setLoading(false)
            }
        }
        if (params.id) loadDetail()
    }, [params.id])

    const copyToClipboard = (text: string, stepName: string) => {
        navigator.clipboard.writeText(text)
        setCopiedStep(stepName)
        setTimeout(() => setCopiedStep(null), 2000)
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-screen">
                <Loader2 className="w-8 h-8 animate-spin text-purple-600" />
            </div>
        )
    }

    if (!detail) {
        return (
            <div className="p-8">
                <Card>
                    <CardContent className="py-12 text-center">
                        <AlertTriangle className="w-12 h-12 mx-auto mb-4 text-yellow-500" />
                        <h3 className="text-lg font-medium mb-2">Pipeline Run Not Found</h3>
                        <Link href="/admin/audits/trace">
                            <Button variant="outline" className="mt-4">
                                <ArrowLeft className="w-4 h-4 mr-2" />
                                Back to Audit Trace
                            </Button>
                        </Link>
                    </CardContent>
                </Card>
            </div>
        )
    }

    return (
        <div className="p-8 space-y-6">
            <div className="flex items-center gap-4">
                <Link href="/admin/audits/trace">
                    <Button variant="ghost" size="sm">
                        <ArrowLeft className="w-4 h-4 mr-2" />
                        Back
                    </Button>
                </Link>
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">{detail.bill_id}</h1>
                    <p className="text-muted-foreground">{detail.jurisdiction}</p>
                </div>
                <Badge className={detail.status === 'completed' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}>
                    {detail.status}
                </Badge>
            </div>

            <Tabs defaultValue="steps" className="space-y-4">
                <TabsList>
                    <TabsTrigger value="steps">Pipeline Steps</TabsTrigger>
                    <TabsTrigger value="analysis">Analysis Output</TabsTrigger>
                    <TabsTrigger value="citations">Citations</TabsTrigger>
                </TabsList>

                <TabsContent value="steps" className="space-y-4">
                    {detail.steps.map((step, index) => (
                        <Card key={index}>
                            <CardHeader className="pb-2">
                                <div className="flex items-center justify-between">
                                    <CardTitle className="text-base">{step.step_name}</CardTitle>
                                    <Badge variant="outline">{step.model}</Badge>
                                </div>
                                <CardDescription>
                                    {new Date(step.created_at).toLocaleString()}
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <div>
                                    <div className="flex items-center justify-between mb-2">
                                        <span className="text-sm font-medium">Input Prompt</span>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => copyToClipboard(step.input, `${step.step_name}-input`)}
                                        >
                                            {copiedStep === `${step.step_name}-input` ? (
                                                <CheckCircle className="w-4 h-4 text-green-500" />
                                            ) : (
                                                <Copy className="w-4 h-4" />
                                            )}
                                        </Button>
                                    </div>
                                    <pre className="bg-gray-50 p-4 rounded-lg text-sm overflow-x-auto max-h-48 overflow-y-auto">
                                        {step.input}
                                    </pre>
                                </div>
                                <div>
                                    <div className="flex items-center justify-between mb-2">
                                        <span className="text-sm font-medium">Output Response</span>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => copyToClipboard(step.output, `${step.step_name}-output`)}
                                        >
                                            {copiedStep === `${step.step_name}-output` ? (
                                                <CheckCircle className="w-4 h-4 text-green-500" />
                                            ) : (
                                                <Copy className="w-4 h-4" />
                                            )}
                                        </Button>
                                    </div>
                                    <pre className="bg-gray-50 p-4 rounded-lg text-sm overflow-x-auto max-h-48 overflow-y-auto">
                                        {step.output}
                                    </pre>
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </TabsContent>

                <TabsContent value="analysis">
                    <Card>
                        <CardHeader>
                            <CardTitle>Analysis Output</CardTitle>
                            <CardDescription>Final structured analysis result</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <pre className="bg-gray-50 p-4 rounded-lg text-sm overflow-x-auto max-h-96 overflow-y-auto">
                                {JSON.stringify(detail.analysis, null, 2)}
                            </pre>
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="citations">
                    <Card>
                        <CardHeader>
                            <CardTitle>Citation Validation</CardTitle>
                            <CardDescription>Verify sources used in analysis</CardDescription>
                        </CardHeader>
                        <CardContent>
                            {detail.analysis && (detail.analysis as { citations?: Array<{ url: string; title: string }> }).citations ? (
                                <div className="space-y-2">
                                    {((detail.analysis as { citations: Array<{ url: string; title: string }> }).citations).map((citation, i) => (
                                        <div key={i} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                                            <span className="text-sm">{citation.title || citation.url}</span>
                                            <a href={citation.url} target="_blank" rel="noopener noreferrer">
                                                <Button variant="ghost" size="sm">
                                                    <ExternalLink className="w-4 h-4" />
                                                </Button>
                                            </a>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <p className="text-muted-foreground">No citations available for this analysis.</p>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>

            {detail.error && (
                <Card className="border-red-200">
                    <CardHeader>
                        <CardTitle className="text-red-600">Error Details</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <pre className="bg-red-50 p-4 rounded-lg text-sm text-red-800 overflow-x-auto">
                            {detail.error}
                        </pre>
                    </CardContent>
                </Card>
            )}
        </div>
    )
}
