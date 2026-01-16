"use client"

export const dynamic = 'force-dynamic';

import { Suspense } from "react";
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
    Card,
    CardContent,
    CardDescription,
    CardFooter,
    CardHeader,
    CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Loader2, Check, X, Search } from "lucide-react"

interface DiscoveryResult {
    jurisdiction_name: string
    category: string
    title: string
    url: string
    snippet: string
}

export default function DiscoveryPage() {
    const [jurisdiction, setJurisdiction] = useState("")
    const [results, setResults] = useState<DiscoveryResult[]>([])
    const [loading, setLoading] = useState(false)

    const runDiscovery = async () => {
        if (!jurisdiction) return
        setLoading(true)
        try {
            const res = await fetch("/api/discovery/run", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ jurisdiction_name: jurisdiction, jurisdiction_type: "city" })
            })
            const data = await res.json()
            setResults(data)
        } catch (error) {
            console.error("Discovery failed:", error)
        } finally {
            setLoading(false)
        }
    }

    const handleApprove = async (result: DiscoveryResult) => {
        // Create source from result
        try {
            await fetch("/api/sources", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    jurisdiction_id: "todo-lookup-id", // In real app, we'd look this up
                    url: result.url,
                    type: result.category,
                    source_method: "scrape",
                    status: "active"
                })
            })
            // Remove from list
            setResults(results.filter(r => r.url !== result.url))
        } catch (error) {
            console.error("Failed to approve source:", error)
        }
    }

    return (
        <div className="p-8 space-y-6">
            <div className="space-y-2">
                <h1 className="text-3xl font-bold tracking-tight">Auto-Discovery</h1>
                <p className="text-muted-foreground">
                    Discover new sources using template-based search.
                </p>
            </div>

            <div className="flex gap-4 max-w-xl">
                <Input
                    type="text"
                    placeholder="Enter jurisdiction name (e.g. San Jose)"
                    value={jurisdiction}
                    onChange={(e) => setJurisdiction(e.target.value)}
                />
                <Button onClick={runDiscovery} disabled={loading || !jurisdiction}>
                    {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    Run Discovery
                </Button>
            </div>

            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                {results.map((result, i) => (
                    <Card key={i}>
                        <CardHeader>
                            <div className="flex justify-between items-start">
                                <Badge>{result.category}</Badge>
                                <Badge variant="outline">{result.jurisdiction_name}</Badge>
                            </div>
                            <CardTitle className="text-lg mt-2 line-clamp-2" title={result.title}>
                                {result.title}
                            </CardTitle>
                            <CardDescription className="line-clamp-1" title={result.url}>
                                {result.url}
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <p className="text-sm text-muted-foreground line-clamp-3">
                                {result.snippet}
                            </p>
                        </CardContent>
                        <CardFooter className="flex justify-between">
                            <Button variant="ghost" size="sm" onClick={() => setResults(results.filter(r => r !== result))}>
                                <X className="mr-2 h-4 w-4" /> Reject
                            </Button>
                            <Button size="sm" onClick={() => handleApprove(result)}>
                                <Check className="mr-2 h-4 w-4" /> Approve
                            </Button>
                        </CardFooter>
                    </Card>
                ))}
            </div>

            {loading && (
                <div className="text-center py-12 text-muted-foreground border rounded-lg border-dashed">
                    <Loader2 className="h-8 w-8 animate-spin mx-auto mb-3" />
                    <p>Searching for sources in {jurisdiction}...</p>
                </div>
            )}

            {!loading && results.length === 0 && (
                <div className="text-center py-12 text-muted-foreground border rounded-lg border-dashed">
                    <Search className="h-8 w-8 mx-auto mb-3 opacity-50" />
                    <p>No discovery results yet. Enter a jurisdiction name and run a search.</p>
                </div>
            )}
        </div>
    )
}
