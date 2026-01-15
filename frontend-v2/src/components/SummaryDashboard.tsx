import React from 'react';
import { Card, CardContent, Typography, Grid, Box, List, ListItem, ListItemText, Paper } from '@mui/material';
import { ResponsiveContainer, ScatterChart, Scatter, XAxis, YAxis, ZAxis, Tooltip, Cell } from 'recharts';

interface Bill {
    id: string;
    bill_number: string;
    title: string;
    total_impact: number;
    avg_confidence: number;
    impact_count: number;
}

interface SummaryDashboardProps {
    bills: Bill[];
    jurisdiction: string;
    onSelectBill: (billId: string) => void;
}

const SummaryDashboard: React.FC<SummaryDashboardProps> = ({ bills, onSelectBill }) => {
    const chartData = bills.map((bill) => ({
        name: bill.bill_number,
        confidence: Math.round(bill.avg_confidence * 100),
        impact: bill.total_impact,
        impacts: bill.impact_count,
        id: bill.id,
        title: bill.title
    }));

    const totalImpact = bills.reduce((sum, bill) => sum + bill.total_impact, 0);
    const avgConfidence = bills.length > 0
        ? bills.reduce((sum, bill) => sum + bill.avg_confidence, 0) / bills.length
        : 0;

    return (
        <Box>
            <Grid container spacing={3} sx={{ mb: 3 }}>
                <Grid item xs={12} md={4}>
                    <Card>
                        <CardContent>
                            <Typography variant="h6">Total Bills</Typography>
                            <Typography variant="h4">{bills.length}</Typography>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid item xs={12} md={4}>
                    <Card>
                        <CardContent>
                            <Typography variant="h6">Annual Impact (Median)</Typography>
                            <Typography variant="h4">${totalImpact.toLocaleString()}</Typography>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid item xs={12} md={4}>
                    <Card>
                        <CardContent>
                            <Typography variant="h6">Avg Confidence</Typography>
                            <Typography variant="h4">{Math.round(avgConfidence * 100)}%</Typography>
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>

            <Card sx={{ mb: 3 }}>
                <CardContent>
                    <Typography variant="h6">Impact vs Confidence Analysis</Typography>
                    <Box sx={{ height: 400 }}>
                        <ResponsiveContainer width="100%" height="100%">
                            <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                                <XAxis type="number" dataKey="confidence" name="Confidence" unit="%" domain={[0, 100]} />
                                <YAxis type="number" dataKey="impact" name="Impact" unit="$" />
                                <ZAxis type="number" dataKey="impacts" range={[60, 400]} name="Impacts" />
                                <Tooltip cursor={{ strokeDasharray: '3 3' }} content={({ active, payload }) => {
                                    if (active && payload && payload.length) {
                                        const data = payload[0].payload;
                                        return (
                                            <Paper sx={{ p: 2 }}>
                                                <Typography variant="subtitle1">{data.name}</Typography>
                                                <Typography variant="body2">{data.title}</Typography>
                                                <Typography variant="body2">Impact: ${data.impact}</Typography>
                                                <Typography variant="body2">Confidence: {data.confidence}%</Typography>
                                                <Typography variant="body2">Impacts found: {data.impacts}</Typography>
                                            </Paper>
                                        );
                                    }
                                    return null;
                                }} />
                                <Scatter name="Bills" data={chartData} fill="#8884d8">
                                    {chartData.map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={entry.impact > 1000 ? '#ef4444' : '#3b82f6'} />
                                    ))}
                                </Scatter>
                            </ScatterChart>
                        </ResponsiveContainer>
                    </Box>
                </CardContent>
            </Card>

            <Card>
                <CardContent>
                    <Typography variant="h6">Bills by Impact (Highest First)</Typography>
                    <List>
                        {bills
                            .sort((a, b) => b.total_impact - a.total_impact)
                            .map((bill) => (
                                <ListItem button key={bill.id} onClick={() => onSelectBill(bill.id)}>
                                    <ListItemText
                                        primary={bill.title}
                                        secondary={`$${bill.total_impact.toLocaleString()} - ${Math.round(bill.avg_confidence * 100)}% confidence`}
                                    />
                                </ListItem>
                            ))}
                    </List>
                </CardContent>
            </Card>
        </Box>
    );
};

export default SummaryDashboard;
