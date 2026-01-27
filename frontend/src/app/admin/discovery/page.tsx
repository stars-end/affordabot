"use client"

export const dynamic = 'force-dynamic';

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
    Card,
    CardContent,
    CardDescription,
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
        try {
            await fetch("/api/sources", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    jurisdiction_id: "todo-lookup-id",
                    url: result.url,
                    type: result.category,
                    source_method: "scrape",
                    status: "active"
                })
            })
            setResults(results.filter(r => r.url !== result.url))
        } catch (error) {
            console.error("Failed to approve source:", error)
        }
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div>
                <div className="flex items-center gap-2 mb-2">
                    <span className="text-sm text-slate-500">ADMIN</span>
                    <span className="text-slate-300">/</span>
                    <span className="text-sm text-slate-900 font-medium">AUTO-DISCOVERY</span>
                </div>
                <h1 className="text-2xl font-bold text-slate-900">Discovery Queue</h1>
                <p className="text-slate-500 mt-1">Discover new sources using template-based search</p>
            </div>

            {/* Search */}
            <div className="flex gap-4 max-w-xl">
                <Input
                    type="text"
                    placeholder="Enter jurisdiction name (e.g. San Jose)"
                    value={jurisdiction}
                    onChange={(e) => setJurisdiction(e.target.value)}
                    className="border-slate-200"
                />
                <Button onClick={runDiscovery} disabled={loading || !jurisdiction} className="bg-slate-900 hover:bg-slate-800">
                    {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    Run Discovery
                </Button>
            </div>

            {/* Results Grid */}
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {results.length === 0 && !loading && (
                    <>
                        {/* Demo Cards */}
                        <Card className="card-prism border-slate-200">
                            <CardHeader className="pb-3">
                                <div className="flex justify-between items-start">
                                    <Badge className="bg-prism-cyan/10 text-prism-cyan border-prism-cyan/30">City Council</Badge>
                                    <Badge variant="outline" className="text-slate-500">San Jose</Badge>
                                </div>
                                <CardTitle className="text-base mt-2">City Council Meeting Minutes</CardTitle>
                                <CardDescription className="text-xs">sanjoseca.gov</CardDescription>
                            </CardHeader>
                            <CardContent>
                                <p className="text-sm text-slate-600 mb-4">Official meeting minutes and agendas from San Jose City Council sessions.</p>
                                <div className="flex gap-2">
                                    <Button size="sm" className="flex-1 bg-prism-green hover:bg-prism-green/90 text-white">
                                        <Check className="mr-1 h-3 w-3" /> Approve
                                    </Button>
                                    <Button size="sm" variant="outline" className="flex-1 border-slate-200">
                                        <X className="mr-1 h-3 w-3" /> Reject
                                    </Button>
                                </div>
                            </CardContent>
                        </Card>

                        <Card className="card-prism border-slate-200">
                            <CardHeader className="pb-3">
                                <div className="flex justify-between items-start">
                                    <Badge className="bg-prism-yellow/10 text-prism-yellow border-prism-yellow/30">Legislation</Badge>
                                    <Badge variant="outline" className="text-slate-500">San Jose</Badge>
                                </div>
                                <CardTitle className="text-base mt-2">Municipal Code Database</CardTitle>
                                <CardDescription className="text-xs">codepublishing.com</CardDescription>
                            </CardHeader>
                            <CardContent>
                                <p className="text-sm text-slate-600 mb-4">Comprehensive database of San Jose municipal codes and ordinances.</p>
                                <div className="flex gap-2">
                                    <Button size="sm" className="flex-1 bg-prism-green hover:bg-prism-green/90 text-white">
                                        <Check className="mr-1 h-3 w-3" /> Approve
                                    </Button>
                                    <Button size="sm" variant="outline" className="flex-1 border-slate-200">
                                        <X className="mr-1 h-3 w-3" /> Reject
                                    </Button>
                                </div>
                            </CardContent>
                        </Card>

                        <Card className="card-prism border-slate-200">
                            <CardHeader className="pb-3">
                                <div className="flex justify-between items-start">
                                    <Badge className="bg-prism-pink/10 text-prism-pink border-prism-pink/30">Housing</Badge>
                                    <Badge variant="outline" className="text-slate-500">San Jose</Badge>
                                </div>
                                <CardTitle className="text-base mt-2">Housing Department Notices</CardTitle>
                                <CardDescription className="text-xs">sanjoseca.gov/housing</CardDescription>
                            </CardHeader>
                            <CardContent>
                                <p className="text-sm text-slate-600 mb-4">Public notices and updates from the San Jose Housing Department.</p>
                                <div className="flex gap-2">
                                    <Button size="sm" className="flex-1 bg-prism-green hover:bg-prism-green/90 text-white">
                                        <Check className="mr-1 h-3 w-3" /> Approve
                                    </Button>
                                    <Button size="sm" variant="outline" className="flex-1 border-slate-200">
                                        <X className="mr-1 h-3 w-3" /> Reject
                                    </Button>
                                </div>
                            </CardContent>
                        </Card>
                    </>
                )}

                {results.map((result, i) => (
                    <Card key={i} className="card-prism border-slate-200">
                        <CardHeader className="pb-3">
                            <div className="flex justify-between items-start">
                                <Badge className="bg-prism-cyan/10 text-prism-cyan border-prism-cyan/30">{result.category}</Badge>
                                <Badge variant="outline" className="text-slate-500">{result.jurisdiction_name}</Badge>
                            </div>
                            <CardTitle className="text-base mt-2">{result.title}</CardTitle>
                            <CardDescription className="text-xs">{new URL(result.url).hostname}</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <p className="text-sm text-slate-600 mb-4">{result.snippet}</p>
                            <div className="flex gap-2">
                                <Button size="sm" onClick={() => handleApprove(result)} className="flex-1 bg-prism-green hover:bg-prism-green/90 text-white">
                                    <Check className="mr-1 h-3 w-3" /> Approve
                                </Button>
                                <Button size="sm" variant="outline" className="flex-1 border-slate-200">
                                    <X className="mr-1 h-3 w-3" /> Reject
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                ))}
            </div>
        </div>
    )
}
