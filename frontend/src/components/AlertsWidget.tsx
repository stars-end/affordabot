"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { AlertTriangle, CheckCircle, Clock, TrendingDown, TrendingUp, Activity } from "lucide-react"

interface Alert {
    id: string
    type: 'error' | 'warning' | 'info'
    title: string
    message: string
    created_at: string
    resolved: boolean
}

interface AlertsWidgetProps {
    className?: string
}

export function AlertsWidget({ className }: AlertsWidgetProps) {
    const [alerts, setAlerts] = useState<Alert[]>([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        const loadAlerts = async () => {
            try {
                const res = await fetch('/api/admin/alerts')
                if (res.ok) {
                    const data = await res.json()
                    setAlerts(data.alerts || [])
                }
            } catch (error) {
                console.error('Failed to load alerts:', error)
            } finally {
                setLoading(false)
            }
        }
        loadAlerts()
        // Refresh alerts every minute
        const interval = setInterval(loadAlerts, 60000)
        return () => clearInterval(interval)
    }, [])

    const activeAlerts = alerts.filter(a => !a.resolved)
    const errorCount = activeAlerts.filter(a => a.type === 'error').length
    const warningCount = activeAlerts.filter(a => a.type === 'warning').length

    const getAlertIcon = (type: string) => {
        switch (type) {
            case 'error':
                return <AlertTriangle className="w-4 h-4 text-red-500" />
            case 'warning':
                return <Clock className="w-4 h-4 text-yellow-500" />
            default:
                return <Activity className="w-4 h-4 text-blue-500" />
        }
    }

    if (loading) {
        return (
            <Card className={className}>
                <CardHeader className="pb-2">
                    <CardTitle className="text-base">System Alerts</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="animate-pulse space-y-2">
                        <div className="h-4 bg-gray-200 rounded w-3/4"></div>
                        <div className="h-4 bg-gray-200 rounded w-1/2"></div>
                    </div>
                </CardContent>
            </Card>
        )
    }

    return (
        <Card className={className}>
            <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-base">System Alerts</CardTitle>
                    <div className="flex items-center gap-2">
                        {errorCount > 0 && (
                            <Badge variant="destructive" className="text-xs">
                                {errorCount} Error{errorCount > 1 ? 's' : ''}
                            </Badge>
                        )}
                        {warningCount > 0 && (
                            <Badge variant="secondary" className="text-xs bg-yellow-100 text-yellow-800">
                                {warningCount} Warning{warningCount > 1 ? 's' : ''}
                            </Badge>
                        )}
                        {activeAlerts.length === 0 && (
                            <Badge className="text-xs bg-green-100 text-green-800">
                                <CheckCircle className="w-3 h-3 mr-1" />
                                All Clear
                            </Badge>
                        )}
                    </div>
                </div>
            </CardHeader>
            <CardContent>
                {activeAlerts.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                        No active alerts. System is operating normally.
                    </p>
                ) : (
                    <div className="space-y-2 max-h-48 overflow-y-auto">
                        {activeAlerts.slice(0, 5).map((alert) => (
                            <div
                                key={alert.id}
                                className={`flex items-start gap-2 p-2 rounded-lg text-sm ${alert.type === 'error' ? 'bg-red-50' :
                                        alert.type === 'warning' ? 'bg-yellow-50' : 'bg-blue-50'
                                    }`}
                            >
                                {getAlertIcon(alert.type)}
                                <div className="flex-1 min-w-0">
                                    <p className="font-medium truncate">{alert.title}</p>
                                    <p className="text-muted-foreground truncate">{alert.message}</p>
                                </div>
                            </div>
                        ))}
                        {activeAlerts.length > 5 && (
                            <p className="text-xs text-muted-foreground text-center pt-2">
                                +{activeAlerts.length - 5} more alerts
                            </p>
                        )}
                    </div>
                )}
            </CardContent>
        </Card>
    )
}

// Stats widget for the dashboard
interface StatsData {
    total_bills: number
    analyzed_today: number
    scrape_success_rate: number
    pending_reviews: number
}

export function DashboardStats({ className }: { className?: string }) {
    const [stats, setStats] = useState<StatsData | null>(null)

    useEffect(() => {
        const loadStats = async () => {
            try {
                const res = await fetch('/api/admin/stats')
                if (res.ok) {
                    setStats(await res.json())
                }
            } catch (error) {
                console.error('Failed to load stats:', error)
            }
        }
        loadStats()
    }, [])

    if (!stats) return null

    return (
        <div className={`grid grid-cols-4 gap-4 ${className}`}>
            <Card>
                <CardContent className="pt-4">
                    <p className="text-sm text-muted-foreground">Total Bills</p>
                    <p className="text-2xl font-bold">{stats.total_bills}</p>
                </CardContent>
            </Card>
            <Card>
                <CardContent className="pt-4">
                    <p className="text-sm text-muted-foreground">Analyzed Today</p>
                    <p className="text-2xl font-bold flex items-center gap-2">
                        {stats.analyzed_today}
                        {stats.analyzed_today > 0 && <TrendingUp className="w-4 h-4 text-green-500" />}
                    </p>
                </CardContent>
            </Card>
            <Card>
                <CardContent className="pt-4">
                    <p className="text-sm text-muted-foreground">Scrape Success</p>
                    <p className="text-2xl font-bold flex items-center gap-2">
                        {(stats.scrape_success_rate * 100).toFixed(0)}%
                        {stats.scrape_success_rate < 0.9 && <TrendingDown className="w-4 h-4 text-red-500" />}
                    </p>
                </CardContent>
            </Card>
            <Card>
                <CardContent className="pt-4">
                    <p className="text-sm text-muted-foreground">Pending Reviews</p>
                    <p className="text-2xl font-bold">{stats.pending_reviews}</p>
                </CardContent>
            </Card>
        </div>
    )
}
