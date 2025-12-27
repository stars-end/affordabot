"use client"

import { useState, useEffect } from "react"
export const dynamic = 'force-dynamic';
import { Button } from "@/components/ui/button"
import {
    Card,
    CardContent,
    CardDescription,
    CardFooter,
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
        <div className="p-8 space-y-6">
            <div className="space-y-2">
                <h1 className="text-3xl font-bold tracking-tight">Template Reviews</h1>
                <p className="text-muted-foreground">
                    Review LLM-suggested improvements to scraping templates.
                </p>
            </div>

            <div className="grid gap-6">
                {loading ? (
                    <div>Loading...</div>
                ) : reviews.length === 0 ? (
                    <div className="text-center py-12 text-muted-foreground border rounded-lg border-dashed">
                        No pending reviews.
                    </div>
                ) : (
                    reviews.map((review) => (
                        <Card key={review.id}>
                            <CardHeader>
                                <div className="flex justify-between items-start">
                                    <div className="space-x-2">
                                        <Badge>{review.jurisdiction_type}</Badge>
                                        <Badge variant="outline">{review.category}</Badge>
                                    </div>
                                    <span className="text-xs text-muted-foreground">
                                        {new Date(review.created_at).toLocaleDateString()}
                                    </span>
                                </div>
                                <CardTitle className="mt-2">Template Improvement</CardTitle>
                            </CardHeader>
                            <CardContent className="grid gap-4 md:grid-cols-2">
                                <div className="space-y-2 p-4 bg-muted/50 rounded-md">
                                    <span className="text-xs font-semibold text-muted-foreground uppercase">Current</span>
                                    <p className="font-mono text-sm">{review.current_template}</p>
                                </div>
                                <div className="space-y-2 p-4 bg-green-50/50 dark:bg-green-900/10 rounded-md border border-green-200 dark:border-green-900">
                                    <span className="text-xs font-semibold text-green-600 dark:text-green-400 uppercase">Suggested</span>
                                    <p className="font-mono text-sm">{review.suggested_template}</p>
                                </div>
                                <div className="md:col-span-2">
                                    <p className="text-sm text-muted-foreground italic">
                                        Reasoning: {review.reasoning}
                                    </p>
                                </div>
                            </CardContent>
                            <CardFooter className="flex justify-end gap-2">
                                <Button variant="ghost" onClick={() => handleAction(review.id, 'rejected')}>
                                    <X className="mr-2 h-4 w-4" /> Reject
                                </Button>
                                <Button onClick={() => handleAction(review.id, 'approved')}>
                                    <Check className="mr-2 h-4 w-4" /> Approve
                                </Button>
                            </CardFooter>
                        </Card>
                    ))
                )}
            </div>
        </div>
    )
}
