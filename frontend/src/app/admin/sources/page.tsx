"use client"

export const dynamic = 'force-dynamic';

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Plus, Search, Trash2, RefreshCw, Pause, Play } from "lucide-react"
import { adminService, Source } from "@/services/adminService"

export default function SourcesPage() {
    const [sources, setSources] = useState<Source[]>([])
    const [loading, setLoading] = useState(true)
    const [filter, setFilter] = useState("")

    useEffect(() => {
        fetchSources()
    }, [])

    const fetchSources = async () => {
        setLoading(true)
        try {
            const data = await adminService.getSources()
            setSources(data)
        } catch (error) {
            console.error("Failed to fetch sources:", error)
        } finally {
            setLoading(false)
        }
    }

    const handleDelete = async (id: string) => {
        if (!confirm("Are you sure you want to delete this source?")) return
        try {
            await adminService.deleteSource(id)
            fetchSources()
        } catch (error) {
            console.error("Failed to delete source:", error)
        }
    }

    const filteredSources = sources.filter(s =>
        s.url.toLowerCase().includes(filter.toLowerCase()) ||
        s.type.toLowerCase().includes(filter.toLowerCase())
    )

    const getStatusBadge = (status: string) => {
        switch (status) {
            case 'active':
                return <Badge className="bg-prism-green/10 text-prism-green border-prism-green/30 hover:bg-prism-green/20">PUBLISHED</Badge>
            case 'pending':
                return <Badge className="bg-prism-yellow/10 text-prism-yellow border-prism-yellow/30 hover:bg-prism-yellow/20">PENDING</Badge>
            case 'error':
                return <Badge className="bg-prism-pink/10 text-prism-pink border-prism-pink/30 hover:bg-prism-pink/20">ERROR</Badge>
            default:
                return <Badge variant="secondary">{status}</Badge>
        }
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900">Source Management</h1>
                    <p className="text-slate-500 mt-1">Manage legislative document sources and ingestion streams</p>
                </div>
                <div className="flex gap-2">
                    <Button variant="outline" onClick={fetchSources} className="border-slate-200">
                        <RefreshCw className="mr-2 h-4 w-4" /> Refresh
                    </Button>
                    <Button className="bg-slate-900 hover:bg-slate-800">
                        <Plus className="mr-2 h-4 w-4" /> Add Source
                    </Button>
                </div>
            </div>

            {/* Filters */}
            <div className="flex items-center gap-4">
                <div className="relative flex-1 max-w-sm">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400 h-4 w-4" />
                    <Input
                        placeholder="Search sources..."
                        value={filter}
                        onChange={(e) => setFilter(e.target.value)}
                        className="pl-10 border-slate-200"
                    />
                </div>
                <div className="flex gap-2">
                    <span className="px-3 py-1.5 text-xs font-medium border border-slate-200 rounded bg-white">
                        STATUS: ALL
                    </span>
                    <span className="px-3 py-1.5 text-xs font-medium border border-slate-200 rounded bg-white">
                        SOURCE: ALL
                    </span>
                </div>
                <Button variant="outline" className="border-slate-900 bg-slate-900 text-white hover:bg-slate-800">
                    <Pause className="mr-2 h-4 w-4" /> Pause Stream
                </Button>
            </div>

            {/* Table */}
            <div className="card-prism overflow-hidden">
                <Table>
                    <TableHeader>
                        <TableRow className="bg-slate-50 hover:bg-slate-50">
                            <TableHead className="text-xs font-semibold uppercase tracking-wider text-slate-500">Document ID</TableHead>
                            <TableHead className="text-xs font-semibold uppercase tracking-wider text-slate-500">Size</TableHead>
                            <TableHead className="text-xs font-semibold uppercase tracking-wider text-slate-500">Timestamp</TableHead>
                            <TableHead className="text-xs font-semibold uppercase tracking-wider text-slate-500">Status</TableHead>
                            <TableHead className="text-xs font-semibold uppercase tracking-wider text-slate-500">Latest Output</TableHead>
                            <TableHead className="text-xs font-semibold uppercase tracking-wider text-slate-500 text-right">Actions</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {loading ? (
                            <TableRow>
                                <TableCell colSpan={6} className="text-center py-8 text-slate-500">Loading...</TableCell>
                            </TableRow>
                        ) : filteredSources.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={6} className="text-center py-8 text-slate-500">
                                    <div className="space-y-4">
                                        <p>No sources found</p>
                                        {/* Demo Data */}
                                        <div className="text-left">
                                            <TableRow>
                                                <TableCell className="font-mono text-xs">
                                                    <div className="flex items-center gap-2">
                                                        <div className="w-4 h-4 bg-slate-200 rounded" />
                                                        HR-5501.pdf
                                                    </div>
                                                    <div className="text-slate-400 mt-1">SHA: 8f7a10bc</div>
                                                </TableCell>
                                                <TableCell className="font-mono text-sm">2.4 MB</TableCell>
                                                <TableCell className="font-mono text-sm">10-27 09:41:02</TableCell>
                                                <TableCell>{getStatusBadge('active')}</TableCell>
                                                <TableCell className="text-sm text-prism-cyan">Extracting text layers via OCR engine...</TableCell>
                                                <TableCell className="text-right">
                                                    <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                                                        <Trash2 className="h-4 w-4 text-slate-400" />
                                                    </Button>
                                                </TableCell>
                                            </TableRow>
                                            <TableRow>
                                                <TableCell className="font-mono text-xs">
                                                    <div className="flex items-center gap-2">
                                                        <div className="w-4 h-4 bg-prism-cyan/20 rounded" />
                                                        SB-102.html
                                                    </div>
                                                    <div className="text-slate-400 mt-1">SHA: a3b2c5d4</div>
                                                </TableCell>
                                                <TableCell className="font-mono text-sm">145 KB</TableCell>
                                                <TableCell className="font-mono text-sm">10-27 09:40:55</TableCell>
                                                <TableCell>{getStatusBadge('active')}</TableCell>
                                                <TableCell className="text-sm text-slate-600">Indexed 402 tokens. Relevance score: 0.98</TableCell>
                                                <TableCell className="text-right">
                                                    <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                                                        <Trash2 className="h-4 w-4 text-slate-400" />
                                                    </Button>
                                                </TableCell>
                                            </TableRow>
                                            <TableRow>
                                                <TableCell className="font-mono text-xs">
                                                    <div className="flex items-center gap-2">
                                                        <div className="w-4 h-4 bg-prism-pink/20 rounded" />
                                                        AMEND-88.pdf
                                                    </div>
                                                    <div className="text-slate-400 mt-1">SHA: e9f0g7h8</div>
                                                </TableCell>
                                                <TableCell className="font-mono text-sm">0 B</TableCell>
                                                <TableCell className="font-mono text-sm">10-27 09:39:12</TableCell>
                                                <TableCell>{getStatusBadge('error')}</TableCell>
                                                <TableCell className="text-sm text-prism-pink">ERR_CORRUPT_FILE: Unexpected EOF at byte 0.</TableCell>
                                                <TableCell className="text-right">
                                                    <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                                                        <Trash2 className="h-4 w-4 text-slate-400" />
                                                    </Button>
                                                </TableCell>
                                            </TableRow>
                                            <TableRow>
                                                <TableCell className="font-mono text-xs">
                                                    <div className="flex items-center gap-2">
                                                        <div className="w-4 h-4 bg-prism-yellow/20 rounded" />
                                                        HB-4021_DRAFT.html
                                                    </div>
                                                    <div className="text-slate-400 mt-1">SHA: 1j2k3l4m</div>
                                                </TableCell>
                                                <TableCell className="font-mono text-sm">320 KB</TableCell>
                                                <TableCell className="font-mono text-sm">10-27 09:38:45</TableCell>
                                                <TableCell>{getStatusBadge('pending')}</TableCell>
                                                <TableCell className="text-sm text-slate-600">File uploaded successfully. Queued for analysis.</TableCell>
                                                <TableCell className="text-right">
                                                    <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                                                        <Trash2 className="h-4 w-4 text-slate-400" />
                                                    </Button>
                                                </TableCell>
                                            </TableRow>
                                        </div>
                                    </div>
                                </TableCell>
                            </TableRow>
                        ) : (
                            filteredSources.map((source) => (
                                <TableRow key={source.id}>
                                    <TableCell className="font-mono text-sm">{source.url}</TableCell>
                                    <TableCell className="text-sm">{source.type}</TableCell>
                                    <TableCell className="text-sm">{source.source_method}</TableCell>
                                    <TableCell>{getStatusBadge(source.status)}</TableCell>
                                    <TableCell className="text-sm text-slate-500">
                                        {source.last_scraped_at ? new Date(source.last_scraped_at).toLocaleString() : 'Never'}
                                    </TableCell>
                                    <TableCell className="text-right">
                                        <Button variant="ghost" size="sm" onClick={() => handleDelete(source.id)}>
                                            <Trash2 className="h-4 w-4 text-slate-400" />
                                        </Button>
                                    </TableCell>
                                </TableRow>
                            ))
                        )}
                    </TableBody>
                </Table>
            </div>

            {/* Pagination */}
            <div className="flex items-center justify-between">
                <p className="text-sm text-slate-500">Viewing 1-9 of 1,204 records</p>
                <div className="flex gap-2">
                    <Button variant="outline" size="sm" className="border-slate-200" disabled>
                        Prev
                    </Button>
                    <Button variant="outline" size="sm" className="border-slate-200 bg-slate-900 text-white">
                        Next
                    </Button>
                </div>
            </div>
        </div>
    )
}
