import { useState, useEffect } from 'react';
import { Box, Typography, List, ListItem, ListItemButton, ListItemText, Paper, CircularProgress, Accordion, AccordionSummary, AccordionDetails, Alert } from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { listAgentSessions, getAgentTraces, getRunSteps, AgentStep } from '../api/admin';
import { useQuery } from '@tanstack/react-query';
import PipelineStepTimeline from './PipelineStepTimeline';
import { useParams, useNavigate } from 'react-router-dom';

export default function GlassBoxViewer() {
    const { runId } = useParams();
    const navigate = useNavigate();
    const [selectedQuery, setSelectedQuery] = useState<string | null>(runId || null);

    // Sync state with URL param
    useEffect(() => {
        if (runId && runId !== selectedQuery) {
            setSelectedQuery(runId);
        }
    }, [runId, selectedQuery]);

    const handleSelectQuery = (q: string) => {
        setSelectedQuery(q);
        navigate(`/admin/runs/${q}`);
    };

    const { data: queries, isLoading: loadingQueries } = useQuery({
        queryKey: ['agent-sessions'],
        queryFn: listAgentSessions
    });

    // 1. Fetch Legacy Traces
    const { data: traces, isLoading: loadingTraces } = useQuery({
        queryKey: ['agent-traces', selectedQuery],
        queryFn: () => getAgentTraces(selectedQuery!),
        enabled: !!selectedQuery
    });

    // 2. Fetch Granular Steps (New)
    const { data: granularSteps, isLoading: loadingSteps } = useQuery({
        queryKey: ['pipeline-steps', selectedQuery],
        queryFn: () => getRunSteps(selectedQuery!),
        enabled: !!selectedQuery
    });

    const isLoading = loadingTraces || loadingSteps;
    const hasGranularData = granularSteps && granularSteps.length > 0;
    const hasLegacyData = traces && traces.length > 0;

    return (
        <Box sx={{ display: 'flex', gap: 2, height: '80vh' }}>
            {/* Sidebar: Sessions */}
            <Paper sx={{ width: 300, overflow: 'auto' }}>
                <Typography variant="h6" sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
                    Agent Sessions
                </Typography>
                {loadingQueries ? <CircularProgress sx={{ m: 2 }} /> : (
                    <List>
                        {queries?.map((q) => (
                            <ListItem key={q} disablePadding>
                                <ListItemButton
                                    selected={q === selectedQuery}
                                    onClick={() => handleSelectQuery(q)}
                                >
                                    <ListItemText primary={q.substring(0, 15) + '...'} secondary="Trace ID" />
                                </ListItemButton>
                            </ListItem>
                        ))}
                        {queries?.length === 0 && <Typography sx={{ p: 2 }}>No sessions found.</Typography>}
                    </List>
                )}
            </Paper>

            {/* Main: Traces */}
            <Paper sx={{ flex: 1, overflow: 'auto', p: 2 }}>
                <Typography variant="h6" gutterBottom>
                    Execution Trace: {selectedQuery || "Select a session"}
                </Typography>

                {isLoading && <CircularProgress />}

                {!isLoading && selectedQuery && !hasGranularData && !hasLegacyData && (
                    <Alert severity="info">No trace data found for this session.</Alert>
                )}

                {/* Prefer Granular Data */}
                {hasGranularData && (
                    <Box>
                        <Alert severity="success" sx={{ mb: 2 }}>
                            Viewing Granular Step Data (V2 Pipeline)
                        </Alert>
                        <PipelineStepTimeline steps={granularSteps} />
                    </Box>
                )}

                {/* Fallback to Legacy Data if no Granular Data */}
                {!hasGranularData && hasLegacyData && (
                    <Box>
                        <Alert severity="warning" sx={{ mb: 2 }}>
                            Viewing Legacy Trace Data (File System)
                        </Alert>
                        {traces?.map((step: AgentStep, idx: number) => (
                            <Accordion key={idx} defaultExpanded>
                                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                                    <Typography sx={{ width: '33%', flexShrink: 0, fontWeight: 'bold', color: 'primary.main' }}>
                                        {step.tool}
                                    </Typography>
                                    <Typography sx={{ color: 'text.secondary' }}>
                                        Tasks: {step.task_id} | {new Date(step.timestamp).toLocaleTimeString()}
                                    </Typography>
                                </AccordionSummary>
                                <AccordionDetails>
                                    <Box sx={{ mb: 2 }}>
                                        <Typography variant="subtitle2">Arguments:</Typography>
                                        <Paper variant="outlined" sx={{ p: 1, bgcolor: 'background.default' }}>
                                            <pre style={{ margin: 0, overflow: 'auto' }}>{JSON.stringify(step.args, null, 2)}</pre>
                                        </Paper>
                                    </Box>
                                    <Box>
                                        <Typography variant="subtitle2">Result:</Typography>
                                        <Paper variant="outlined" sx={{ p: 1, bgcolor: 'background.default' }}>
                                            <pre style={{ margin: 0, overflow: 'auto' }}>{JSON.stringify(step.result, null, 2)}</pre>
                                        </Paper>
                                    </Box>
                                </AccordionDetails>
                            </Accordion>
                        ))}
                    </Box>
                )}
            </Paper>
        </Box>
    );
}
