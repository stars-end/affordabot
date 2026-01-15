"use client"

import { useState, useEffect } from "react"
import { useParams } from "next/navigation"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Loader2, ArrowLeft, Code, FileText, CheckCircle, AlertTriangle, RefreshCw } from "lucide-react"
import Link from "next/link"

interface ExtractionDebug {
    source_id: string
    url: string
    status: string
    last_scrape: string
    raw_content?: string
    extracted_text?: string
    extraction_metadata?: Record<string, unknown>
    error?: string
}

export default function SourceDebugPage() {
    const params = useParams()
    const [debug, setDebug] = useState<ExtractionDebug | null>(null)
    const [loading, setLoading] = useState(true)
    const [reprocessing, setReprocessing] = useState(false)

    useEffect(() => {
        const loadDebug = async () => {
            try {
                const res = await fetch(`/api/admin/sources/${params.id}/debug`)
                if (res.ok) {
                    const data = await res.json()
                    setDebug(data)
                }
            } catch (error) {
                console.error('Failed to load source debug:', error)
            } finally {
                setLoading(false)
            }
        }
        if (params.id) loadDebug()
    }, [params.id])

    const handleReprocess = async () => {
        setReprocessing(true)
        try {
            await fetch(`/api/admin/sources/${params.id}/reprocess`, { method: 'POST' })
            // Reload debug info
            const res = await fetch(`/api/admin/sources/${params.id}/debug`)
            if (res.ok) {
                setDebug(await res.json())
            }
        } catch (error) {
            console.error('Reprocess failed:', error)
        } finally {
            setReprocessing(false)
        }
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-screen">
                <Loader2 className="w-8 h-8 animate-spin text-purple-600" />
            </div>
        )
    }

    if (!debug) {
        return (
            <div className="p-8">
                <Card>
                    <CardContent className="py-12 text-center">
                        <AlertTriangle className="w-12 h-12 mx-auto mb-4 text-yellow-500" />
                        <h3 className="text-lg font-medium mb-2">Source Not Found</h3>
                        <Link href="/admin/sources">
                            <Button variant="outline" className="mt-4">
                                <ArrowLeft className="w-4 h-4 mr-2" />
                                Back to Sources
                            </Button>
                        </Link>
                    </CardContent>
                </Card>
            </div>
        )
    }

    return (
        <div className="p-8 space-y-6">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <Link href="/admin/sources">
                        <Button variant="ghost" size="sm">
                            <ArrowLeft className="w-4 h-4 mr-2" />
                            Back
                        </Button>
                    </Link>
                    <div>
                        <h1 className="text-3xl font-bold tracking-tight">Extraction Debug</h1>
                        <p className="text-muted-foreground truncate max-w-xl">{debug.url}</p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <Badge className={debug.status === 'active' ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'}>
                        {debug.status}
                    </Badge>
                    <Button onClick={handleReprocess} disabled={reprocessing}>
                        {reprocessing ? (
                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        ) : (
                            <RefreshCw className="w-4 h-4 mr-2" />
                        )}
                        Reprocess
                    </Button>
                </div>
            </div>

            <Tabs defaultValue="extracted" className="space-y-4">
                <TabsList>
                    <TabsTrigger value="extracted">Extracted Text</TabsTrigger>
                    <TabsTrigger value="raw">Raw HTML</TabsTrigger>
                    <TabsTrigger value="metadata">Metadata</TabsTrigger>
                </TabsList>

                <TabsContent value="extracted">
                    <Card>
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <FileText className="w-5 h-5" />
                                Extracted Text
                            </CardTitle>
                            <CardDescription>
                                Text content extracted from the source for analysis
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            {debug.extracted_text ? (
                                <pre className="bg-gray-50 p-4 rounded-lg text-sm overflow-x-auto max-h-96 overflow-y-auto whitespace-pre-wrap">
                                    {debug.extracted_text}
                                </pre>
                            ) : (
                                <p className="text-muted-foreground">No extracted text available.</p>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="raw">
                    <Card>
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <Code className="w-5 h-5" />
                                Raw HTML Content
                            </CardTitle>
                            <CardDescription>
                                Original HTML as received from the source
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            {debug.raw_content ? (
                                <pre className="bg-gray-50 p-4 rounded-lg text-sm overflow-x-auto max-h-96 overflow-y-auto">
                                    {debug.raw_content.substring(0, 10000)}
                                    {debug.raw_content.length > 10000 && '\n\n... (truncated)'}
                                </pre>
                            ) : (
                                <p className="text-muted-foreground">No raw content available.</p>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="metadata">
                    <Card>
                        <CardHeader>
                            <CardTitle>Extraction Metadata</CardTitle>
                            <CardDescription>
                                Technical details about the extraction process
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="space-y-4">
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="bg-gray-50 p-4 rounded-lg">
                                        <p className="text-sm text-muted-foreground">Last Scrape</p>
                                        <p className="font-medium">{new Date(debug.last_scrape).toLocaleString()}</p>
                                    </div>
                                    <div className="bg-gray-50 p-4 rounded-lg">
                                        <p className="text-sm text-muted-foreground">Status</p>
                                        <p className="font-medium flex items-center gap-2">
                                            {debug.status === 'active' ? (
                                                <CheckCircle className="w-4 h-4 text-green-500" />
                                            ) : (
                                                <AlertTriangle className="w-4 h-4 text-yellow-500" />
                                            )}
                                            {debug.status}
                                        </p>
                                    </div>
                                </div>
                                {debug.extraction_metadata && (
                                    <pre className="bg-gray-50 p-4 rounded-lg text-sm overflow-x-auto">
                                        {JSON.stringify(debug.extraction_metadata, null, 2)}
                                    </pre>
                                )}
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>

            {debug.error && (
                <Card className="border-red-200">
                    <CardHeader>
                        <CardTitle className="text-red-600">Extraction Error</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <pre className="bg-red-50 p-4 rounded-lg text-sm text-red-800 overflow-x-auto">
                            {debug.error}
                        </pre>
                    </CardContent>
                </Card>
            )}
        </div>
    )
}
