import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Loader2, Save, Globe, Database, Server } from 'lucide-react';

interface Jurisdiction {
    id: string;
    name: string;
    type: string;
    scrape_url?: string;
    api_type?: 'openstates' | 'legistar' | null;
    api_key_env?: string;
    openstates_jurisdiction_id?: string;
    scraper_class?: string;
    use_web_scraper_fallback?: boolean;
    source_priority?: 'api_first' | 'web_first' | 'api_only' | 'web_only' | 'both_merge';
}

export function JurisdictionMapper() {
    const [jurisdictions, setJurisdictions] = useState<Jurisdiction[]>([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    useEffect(() => {
        fetchJurisdictions();
    }, []);

    const fetchJurisdictions = async () => {
        try {
            setLoading(true);
            const response = await fetch('/api/admin/jurisdictions');
            if (!response.ok) throw new Error('Failed to fetch jurisdictions');
            const data = await response.json();
            setJurisdictions(data);
        } catch (err) {
            setError('Failed to load jurisdictions');
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const handleUpdate = async (id: string, updates: Partial<Jurisdiction>) => {
        try {
            setSaving(id);
            setError(null);
            setSuccess(null);

            const response = await fetch(`/api/admin/jurisdictions/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(updates),
            });

            if (!response.ok) throw new Error('Failed to update jurisdiction');

            const updated = await response.json();
            setJurisdictions(jurisdictions.map(j => j.id === id ? updated : j));
            setSuccess(`Updated ${updated.name} successfully`);

            // Clear success message after 3 seconds
            setTimeout(() => setSuccess(null), 3000);
        } catch (err) {
            setError('Failed to update jurisdiction');
            console.error(err);
        } finally {
            setSaving(null);
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <Loader2 className="w-8 h-8 animate-spin text-gray-500" />
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <div>
                    <h2 className="text-2xl font-bold tracking-tight">Data Sources</h2>
                    <p className="text-muted-foreground">
                        Manage jurisdiction data sources, APIs, and scraping configurations.
                    </p>
                </div>
                <Button variant="outline" onClick={fetchJurisdictions}>
                    Refresh
                </Button>
            </div>

            {error && (
                <Alert variant="destructive">
                    <AlertTitle>Error</AlertTitle>
                    <AlertDescription>{error}</AlertDescription>
                </Alert>
            )}

            {success && (
                <Alert className="bg-green-50 text-green-900 border-green-200">
                    <AlertTitle>Success</AlertTitle>
                    <AlertDescription>{success}</AlertDescription>
                </Alert>
            )}

            <div className="grid gap-6">
                {jurisdictions.map((jur) => (
                    <Card key={jur.id}>
                        <CardHeader className="pb-3">
                            <div className="flex justify-between items-start">
                                <div>
                                    <CardTitle className="flex items-center gap-2">
                                        {jur.name}
                                        <Badge variant="outline">{jur.type}</Badge>
                                    </CardTitle>
                                    <CardDescription>
                                        {jur.scraper_class || 'No scraper configured'}
                                    </CardDescription>
                                </div>
                                <div className="flex items-center gap-2">
                                    {jur.api_type && <Badge className="bg-blue-100 text-blue-800">API: {jur.api_type}</Badge>}
                                    {jur.scrape_url && <Badge className="bg-green-100 text-green-800">Web Scraper</Badge>}
                                </div>
                            </div>
                        </CardHeader>
                        <CardContent>
                            <div className="grid gap-4 md:grid-cols-2">
                                {/* Source Priority */}
                                <div className="space-y-2">
                                    <Label>Source Strategy</Label>
                                    <Select
                                        value={jur.source_priority || 'api_only'}
                                        onValueChange={(val) => handleUpdate(jur.id, { source_priority: val as any })}
                                    >
                                        <SelectTrigger>
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="api_only">API Only</SelectItem>
                                            <SelectItem value="web_only">Web Scraper Only</SelectItem>
                                            <SelectItem value="api_first">API First (Fallback to Web)</SelectItem>
                                            <SelectItem value="web_first">Web First (Supplement with API)</SelectItem>
                                            <SelectItem value="both_merge">Merge Both Sources</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>

                                {/* Scraper Class */}
                                <div className="space-y-2">
                                    <Label>Scraper Class</Label>
                                    <Input
                                        value={jur.scraper_class || ''}
                                        onChange={(e) => {
                                            // Local update only, save on blur or enter? 
                                            // For simplicity, we'll just show current value. 
                                            // Real implementation might want a debounced save or explicit save button.
                                        }}
                                        onBlur={(e) => handleUpdate(jur.id, { scraper_class: e.target.value })}
                                        placeholder="e.g. SanJoseScraper"
                                    />
                                </div>

                                {/* API Configuration */}
                                <div className="space-y-2">
                                    <Label>API Type</Label>
                                    <Select
                                        value={jur.api_type || 'none'}
                                        onValueChange={(val) => handleUpdate(jur.id, { api_type: val === 'none' ? null : val as any })}
                                    >
                                        <SelectTrigger>
                                            <SelectValue placeholder="Select API Type" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="none">None</SelectItem>
                                            <SelectItem value="openstates">OpenStates</SelectItem>
                                            <SelectItem value="legistar">Legistar</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>

                                {/* API Details */}
                                {jur.api_type === 'openstates' && (
                                    <div className="space-y-2">
                                        <Label>OpenStates Jurisdiction ID</Label>
                                        <Input
                                            defaultValue={jur.openstates_jurisdiction_id || ''}
                                            onBlur={(e) => handleUpdate(jur.id, { openstates_jurisdiction_id: e.target.value })}
                                            placeholder="e.g. ca"
                                        />
                                    </div>
                                )}

                                {/* Web Scraper URL */}
                                <div className="space-y-2 md:col-span-2">
                                    <Label>Web Scraper URL</Label>
                                    <div className="flex gap-2">
                                        <Input
                                            defaultValue={jur.scrape_url || ''}
                                            onBlur={(e) => handleUpdate(jur.id, { scrape_url: e.target.value })}
                                            placeholder="https://..."
                                        />
                                        {jur.scrape_url && (
                                            <Button variant="ghost" size="icon" asChild>
                                                <a href={jur.scrape_url} target="_blank" rel="noopener noreferrer">
                                                    <Globe className="w-4 h-4" />
                                                </a>
                                            </Button>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                ))}
            </div>
        </div>
    );
}
