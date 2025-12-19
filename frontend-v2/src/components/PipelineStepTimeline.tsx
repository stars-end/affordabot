
import { Box, Typography, Paper, Chip, Stack, Accordion, AccordionSummary, AccordionDetails, Tabs, Tab } from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import PlayCircleIcon from '@mui/icons-material/PlayCircle';
import { PipelineStep } from '../api/admin';
import { useState } from 'react';

interface Props {
    steps: PipelineStep[];
}

function StatusIcon({ status }: { status: string }) {
    if (status === 'completed') return <CheckCircleIcon color="success" />;
    if (status === 'failed') return <ErrorIcon color="error" />;
    return <PlayCircleIcon color="action" />;
}

function JsonViewer({ data }: { data: any }) {
    return (
        <Paper variant="outlined" sx={{ p: 1, bgcolor: 'background.default', maxHeight: 300, overflow: 'auto' }}>
            <pre style={{ margin: 0, fontSize: '0.8rem' }}>{JSON.stringify(data, null, 2)}</pre>
        </Paper>
    );
}

export default function PipelineStepTimeline({ steps }: Props) {
    // Tabs for each step detail
    const [activeTab, setActiveTab] = useState<Record<string, number>>({});

    const handleTabChange = (stepId: string, newValue: number) => {
        setActiveTab(prev => ({ ...prev, [stepId]: newValue }));
    };

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {steps.length === 0 && <Typography>No granular steps recorded for this run.</Typography>}

            {steps.map((step) => (
                <Paper key={step.id} sx={{ p: 2, borderLeft: 6, borderColor: step.status === 'completed' ? 'success.main' : step.status === 'failed' ? 'error.main' : 'grey.300' }}>
                    <Stack direction="row" alignItems="center" justifyContent="space-between" mb={1}>
                        <Stack direction="row" alignItems="center" gap={1}>
                            <StatusIcon status={step.status} />
                            <Typography variant="h6" sx={{ textTransform: 'capitalize' }}>
                                {step.step_number}. {step.step_name}
                            </Typography>
                            <Chip label={step.status} size="small" color={step.status === 'completed' ? 'success' : step.status === 'failed' ? 'error' : 'default'} />
                        </Stack>
                        <Typography variant="caption" color="text.secondary">
                            Duration: {step.duration_ms}ms
                        </Typography>
                    </Stack>

                    <Accordion variant="outlined" sx={{ mt: 1 }}>
                        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                            <Typography>Step Details</Typography>
                        </AccordionSummary>
                        <AccordionDetails>
                            <Tabs
                                value={activeTab[step.id] || 0}
                                onChange={(_, v) => handleTabChange(step.id, v)}
                                sx={{ mb: 2, borderBottom: 1, borderColor: 'divider' }}
                            >
                                <Tab label="Input Context" />
                                <Tab label="Output Result" />
                                <Tab label="Model Config" />
                            </Tabs>

                            {(!activeTab[step.id] || activeTab[step.id] === 0) && (
                                <JsonViewer data={step.input_context} />
                            )}
                            {activeTab[step.id] === 1 && (
                                <JsonViewer data={step.output_result} />
                            )}
                            {activeTab[step.id] === 2 && (
                                <JsonViewer data={step.model_info} />
                            )}
                        </AccordionDetails>
                    </Accordion>
                </Paper>
            ))}
        </Box>
    );
}
