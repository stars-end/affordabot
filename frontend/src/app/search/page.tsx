"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Search, Loader2 } from "lucide-react"

interface SearchResult {
    bill_id: string
    title: string
    jurisdiction: string
    summary: string
}

export default function SearchPage() {
    const [query, setQuery] = useState("")
    const [results, setResults] = useState<SearchResult[]>([])
    const [loading, setLoading] = useState(false)
    const [searched, setSearched] = useState(false)
    const router = useRouter()

    const handleSearch = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!query.trim()) return

        setLoading(true)
        setSearched(true)
        try {
            const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`)
            if (res.ok) {
                const data = await res.json()
                setResults(data.results || [])
            } else {
                setResults([])
            }
        } catch (error) {
            console.error("Search failed:", error)
            setResults([])
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-purple-50">
            <div className="max-w-4xl mx-auto px-4 py-16">
                <div className="text-center mb-12">
                    <h1 className="text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-purple-600 to-blue-600 mb-4">
                        Search Legislation
                    </h1>
                    <p className="text-gray-600 text-lg">
                        Find bills and their economic impact analysis
                    </p>
                </div>

                <form onSubmit={handleSearch} className="mb-12">
                    <div className="flex gap-3 max-w-2xl mx-auto">
                        <div className="flex-1 relative">
                            <Search className="absolute left-4 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                            <input
                                type="text"
                                placeholder="Search for bills, topics, or jurisdictions..."
                                value={query}
                                onChange={(e) => setQuery(e.target.value)}
                                className="w-full pl-12 pr-4 py-4 rounded-xl border border-gray-200 focus:border-purple-500 focus:ring-2 focus:ring-purple-200 outline-none transition-all text-lg"
                            />
                        </div>
                        <button
                            type="submit"
                            disabled={loading || !query.trim()}
                            className="px-8 py-4 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-xl font-medium hover:shadow-lg hover:shadow-purple-200 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : "Search"}
                        </button>
                    </div>
                </form>

                {loading && (
                    <div className="text-center py-12">
                        <Loader2 className="w-8 h-8 animate-spin text-purple-600 mx-auto mb-4" />
                        <p className="text-gray-500">Searching legislation...</p>
                    </div>
                )}

                {!loading && searched && results.length === 0 && (
                    <div className="text-center py-12 border border-dashed border-gray-200 rounded-xl bg-white/50">
                        <Search className="w-12 h-12 text-purple-300 mx-auto mb-4" />
                        <p className="text-gray-600 text-lg font-medium mb-2">Search Coming Soon</p>
                        <p className="text-gray-500 text-sm mb-4">
                            Full-text search is being developed. In the meantime, browse our jurisdiction dashboards.
                        </p>
                        <a
                            href="/dashboard/california"
                            className="inline-block px-6 py-2 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-lg font-medium hover:shadow-lg transition-all"
                        >
                            Browse California Bills
                        </a>
                    </div>
                )}

                {!loading && results.length > 0 && (
                    <div className="space-y-4">
                        {results.map((result, i) => (
                            <div
                                key={i}
                                onClick={() => router.push(`/bill/${result.jurisdiction}/${result.bill_id}`)}
                                className="bg-white/80 backdrop-blur-sm border border-gray-100 rounded-xl p-6 cursor-pointer hover:shadow-lg hover:border-purple-200 transition-all group"
                            >
                                <div className="flex items-start justify-between mb-3">
                                    <span className="text-sm font-medium text-purple-600 bg-purple-50 px-2 py-1 rounded">
                                        {result.jurisdiction}
                                    </span>
                                    <span className="text-sm text-gray-400">
                                        {result.bill_id}
                                    </span>
                                </div>
                                <h3 className="text-lg font-semibold text-gray-800 group-hover:text-purple-700 transition-colors mb-2">
                                    {result.title}
                                </h3>
                                <p className="text-gray-600 line-clamp-2">
                                    {result.summary}
                                </p>
                            </div>
                        ))}
                    </div>
                )}

                <div className="mt-12 text-center text-sm text-gray-400">
                    <p>Automated analysis. Verify with official sources.</p>
                </div>
            </div>
        </div>
    )
}
