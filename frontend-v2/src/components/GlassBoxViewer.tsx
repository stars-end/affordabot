import { useState } from 'react';
import { Box, Typography, List, ListItem, ListItemButton, ListItemText, Paper, CircularProgress, Accordion, AccordionSummary, AccordionDetails } from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { listAgentSessions, getAgentTraces, AgentStep } from '../api/admin';
import { useQuery } from '@tanstack/react-query';

export default function GlassBoxViewer() {
    const [selectedQuery, setSelectedQuery] = useState<string | null>(null);

    const { data: queries, isLoading: loadingQueries } = useQuery({
        queryKey: ['agent-sessions'],
        queryFn: listAgentSessions
    });

    const { data: traces, isLoading: loadingTraces } = useQuery({
        queryKey: ['agent-traces', selectedQuery],
        queryFn: () => getAgentTraces(selectedQuery!),
        enabled: !!selectedQuery
    });

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
                                    onClick={() => setSelectedQuery(q)}
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

                {loadingTraces && <CircularProgress />}

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
            </Paper>
        </Box>
    );
}
