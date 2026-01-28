"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"

export const dynamic = 'force-dynamic';
import {
    Card,
    CardContent,
    CardHeader,
    CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Check, X, ArrowRight } from "lucide-react"

interface Review {
    id: string
    jurisdiction_type: string
    category: string
    current_template: string
    suggested_template: string
    reasoning: string
    status: string
    created_at: string
}

export default function TemplateReviewsPage() {
    const [reviews, setReviews] = useState<Review[]>([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        fetchReviews()
    }, [])

    const fetchReviews = async () => {
        try {
            const res = await fetch("/api/admin/reviews")
            if (res.ok) {
                const data = await res.json()
                setReviews(data)
            }
        } catch (error) {
            console.error("Failed to fetch reviews:", error)
        } finally {
            setLoading(false)
        }
    }

    const handleAction = async (id: string, status: 'approved' | 'rejected') => {
        try {
            await fetch(`/api/admin/reviews/${id}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ status })
            })
            setReviews(reviews.filter(r => r.id !== id))
        } catch (error) {
            console.error("Failed to update review:", error)
        }
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div>
                <div className="flex items-center gap-2 mb-2">
                    <span className="text-sm text-slate-500">ADMIN</span>
                    <span className="text-slate-300">/</span>
                    <span className="text-sm text-slate-900 font-medium">TEMPLATE REVIEWS</span>
                </div>
                <h1 className="text-2xl font-bold text-slate-900">Review Queue</h1>
                <p className="text-slate-500 mt-1">Review LLM-suggested improvements to scraping templates</p>
            </div>

            <div className="grid gap-4">
                {loading ? (
                    <div className="text-center py-12 text-slate-500">Loading...</div>
                ) : reviews.length === 0 ? (
                    // Demo reviews
                    <>
                        <Card className="card-prism border-slate-200">
                            <CardHeader className="pb-4">
                                <div className="flex justify-between items-start">
                                    <div className="space-x-2">
                                        <Badge className="bg-prism-cyan/10 text-prism-cyan border-prism-cyan/30">City</Badge>
                                        <Badge variant="outline" className="text-slate-500">Legislation</Badge>
                                    </div>
                                    <span className="text-xs text-slate-400">
                                        {new Date().toLocaleDateString()}
                                    </span>
                                </div>
                                <CardTitle className="text-lg mt-2">Template Improvement</CardTitle>
                            </CardHeader>
                            <CardContent className="grid gap-4 md:grid-cols-2">
                                <div className="space-y-2 p-4 bg-slate-50 rounded border border-slate-200">
                                    <span className="text-xs font-semibold text-slate-500 uppercase">Current</span>
                                    <p className="font-mono text-sm text-slate-700">city_council_minutes_2024_v1</p>
                                </div>
                                <div className="space-y-2 p-4 bg-prism-green/5 rounded border border-prism-green/20">
                                    <span className="text-xs font-semibold text-prism-green uppercase">Suggested</span>
                                    <p className="font-mono text-sm text-slate-700">city_council_minutes_2024_v2</p>
                                </div>
                                <div className="md:col-span-2">
                                    <p className="text-sm text-slate-600">
                                        <span className="font-medium">Reasoning:</span> Updated selector to handle new website layout. Added fallback for PDF links.
                                    </p>
                                </div>
                                <div className="md:col-span-2 flex gap-2">
                                    <Button
                                        onClick={() => handleAction('demo-1', 'approved')}
                                        className="flex-1 bg-prism-green hover:bg-prism-green/90 text-white"
                                    >
                                        <Check className="mr-2 h-4 w-4" /> Approve
                                    </Button>
                                    <Button
                                        onClick={() => handleAction('demo-1', 'rejected')}
                                        variant="outline"
                                        className="flex-1 border-slate-200"
                                    >
                                        <X className="mr-2 h-4 w-4" /> Reject
                                    </Button>
                                </div>
                            </CardContent>
                        </Card>

                        <Card className="card-prism border-slate-200">
                            <CardHeader className="pb-4">
                                <div className="flex justify-between items-start">
                                    <div className="space-x-2">
                                        <Badge className="bg-prism-yellow/10 text-prism-yellow border-prism-yellow/30">County</Badge>
                                        <Badge variant="outline" className="text-slate-500">Housing</Badge>
                                    </div>
                                    <span className="text-xs text-slate-400">
                                        {new Date(Date.now() - 86400000).toLocaleDateString()}
                                    </span>
                                </div>
                                <CardTitle className="text-lg mt-2">Template Improvement</CardTitle>
                            </CardHeader>
                            <CardContent className="grid gap-4 md:grid-cols-2">
                                <div className="space-y-2 p-4 bg-slate-50 rounded border border-slate-200">
                                    <span className="text-xs font-semibold text-slate-500 uppercase">Current</span>
                                    <p className="font-mono text-sm text-slate-700">housing_notices_generic</p>
                                </div>
                                <div className="space-y-2 p-4 bg-prism-green/5 rounded border border-prism-green/20">
                                    <span className="text-xs font-semibold text-prism-green uppercase">Suggested</span>
                                    <p className="font-mono text-sm text-slate-700">housing_notices_santa_clara</p>
                                </div>
                                <div className="md:col-span-2">
                                    <p className="text-sm text-slate-600">
                                        <span className="font-medium">Reasoning:</span> Specialized template for Santa Clara County housing notices with specific date format handling.
                                    </p>
                                </div>
                                <div className="md:col-span-2 flex gap-2">
                                    <Button
                                        onClick={() => handleAction('demo-2', 'approved')}
                                        className="flex-1 bg-prism-green hover:bg-prism-green/90 text-white"
                                    >
                                        <Check className="mr-2 h-4 w-4" /> Approve
                                    </Button>
                                    <Button
                                        onClick={() => handleAction('demo-2', 'rejected')}
                                        variant="outline"
                                        className="flex-1 border-slate-200"
                                    >
                                        <X className="mr-2 h-4 w-4" /> Reject
                                    </Button>
                                </div>
                            </CardContent>
                        </Card>

                        <div className="text-center py-8 text-slate-400 border border-dashed border-slate-200 rounded">
                            No more pending reviews
                        </div>
                    </>
                ) : (
                    reviews.map((review) => (
                        <Card key={review.id} className="card-prism border-slate-200">
                            <CardHeader className="pb-4">
                                <div className="flex justify-between items-start">
                                    <div className="space-x-2">
                                        <Badge className="bg-prism-cyan/10 text-prism-cyan border-prism-cyan/30">{review.jurisdiction_type}</Badge>
                                        <Badge variant="outline" className="text-slate-500">{review.category}</Badge>
                                    </div>
                                    <span className="text-xs text-slate-400">
                                        {new Date(review.created_at).toLocaleDateString()}
                                    </span>
                                </div>
                                <CardTitle className="text-lg mt-2">Template Improvement</CardTitle>
                            </CardHeader>
                            <CardContent className="grid gap-4 md:grid-cols-2">
                                <div className="space-y-2 p-4 bg-slate-50 rounded border border-slate-200">
                                    <span className="text-xs font-semibold text-slate-500 uppercase">Current</span>
                                    <p className="font-mono text-sm text-slate-700">{review.current_template}</p>
                                </div>
                                <div className="space-y-2 p-4 bg-prism-green/5 rounded border border-prism-green/20">
                                    <span className="text-xs font-semibold text-prism-green uppercase">Suggested</span>
                                    <p className="font-mono text-sm text-slate-700">{review.suggested_template}</p>
                                </div>
                                <div className="md:col-span-2">
                                    <p className="text-sm text-slate-600">
                                        <span className="font-medium">Reasoning:</span> {review.reasoning}
                                    </p>
                                </div>
                                <div className="md:col-span-2 flex gap-2">
                                    <Button
                                        onClick={() => handleAction(review.id, 'approved')}
                                        className="flex-1 bg-prism-green hover:bg-prism-green/90 text-white"
                                    >
                                        <Check className="mr-2 h-4 w-4" /> Approve
                                    </Button>
                                    <Button
                                        onClick={() => handleAction(review.id, 'rejected')}
                                        variant="outline"
                                        className="flex-1 border-slate-200"
                                    >
                                        <X className="mr-2 h-4 w-4" /> Reject
                                    </Button>
                                </div>
                            </CardContent>
                        </Card>
                    ))
                )}
            </div>
        </div>
    )
}
