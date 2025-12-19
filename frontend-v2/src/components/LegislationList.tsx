import { useState } from 'react';
import {
    Box, Typography, Paper, Table, TableBody, TableCell, TableContainer,
    TableHead, TableRow, Button, Chip, CircularProgress, Collapse, IconButton
} from '@mui/material';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getLegislation, scrapeJurisdiction, Legislation } from '../api/legislation';

function LegislationRow({ row }: { row: Legislation }) {
    const [open, setOpen] = useState(false);

    return (
        <>
            <TableRow sx={{ '& > *': { borderBottom: 'unset' } }}>
                <TableCell>
                    <IconButton
                        aria-label="expand row"
                        size="small"
                        onClick={() => setOpen(!open)}
                    >
                        {open ? <KeyboardArrowUpIcon /> : <KeyboardArrowDownIcon />}
                    </IconButton>
                </TableCell>
                <TableCell component="th" scope="row">
                    {row.bill_number}
                </TableCell>
                <TableCell>{row.title}</TableCell>
                <TableCell>{row.status}</TableCell>
                <TableCell>
                    {row.impacts?.length > 0 ? (
                        <Chip label={`${row.impacts.length} Impacts`} color="warning" size="small" />
                    ) : (
                        <Chip label="None" size="small" />
                    )}
                </TableCell>
            </TableRow>
            <TableRow>
                <TableCell style={{ paddingBottom: 0, paddingTop: 0 }} colSpan={6}>
                    <Collapse in={open} timeout="auto" unmountOnExit>
                        <Box sx={{ margin: 1 }}>
                            <Typography variant="h6" gutterBottom component="div">
                                Cost of Living Impacts
                            </Typography>
                            {row.impacts?.length > 0 ? (
                                <Table size="small" aria-label="purchases">
                                    <TableHead>
                                        <TableRow>
                                            <TableCell>Description</TableCell>
                                            <TableCell>Clause</TableCell>
                                            <TableCell align="right">Confidence</TableCell>
                                            <TableCell align="right">Cost (P50)</TableCell>
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {row.impacts.map((impact, idx) => (
                                            <TableRow key={idx}>
                                                <TableCell component="th" scope="row">
                                                    {impact.impact_description}
                                                </TableCell>
                                                <TableCell>{impact.relevant_clause}</TableCell>
                                                <TableCell align="right">{impact.confidence_score}</TableCell>
                                                <TableCell align="right">
                                                    ${impact.p50?.toLocaleString()}
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            ) : (
                                <Typography variant="body2" color="text.secondary">
                                    No impacts detected.
                                </Typography>
                            )}
                        </Box>
                    </Collapse>
                </TableCell>
            </TableRow>
        </>
    );
}

export default function LegislationList({ jurisdiction }: { jurisdiction: string }) {
    const queryClient = useQueryClient();

    const { data, isLoading, error } = useQuery({
        queryKey: ['legislation', jurisdiction],
        queryFn: () => getLegislation(jurisdiction)
    });

    const scrapeMutation = useMutation({
        mutationFn: () => scrapeJurisdiction(jurisdiction),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['legislation', jurisdiction] });
        }
    });

    if (isLoading) return <CircularProgress />;
    if (error) return <Typography color="error">Error loading data.</Typography>;

    return (
        <Box sx={{ width: '100%' }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
                <Typography variant="h5">
                    {jurisdiction} Legislation
                </Typography>
                <Button
                    variant="contained"
                    onClick={() => scrapeMutation.mutate()}
                    disabled={scrapeMutation.isPending}
                >
                    {scrapeMutation.isPending ? 'Scraping...' : 'Run Analysis Agent'}
                </Button>
            </Box>

            <TableContainer component={Paper}>
                <Table aria-label="collapsible table">
                    <TableHead>
                        <TableRow>
                            <TableCell />
                            <TableCell>Bill #</TableCell>
                            <TableCell>Title</TableCell>
                            <TableCell>Status</TableCell>
                            <TableCell>Impacts</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {data?.legislation.map((row) => (
                            <LegislationRow key={row.id} row={row} />
                        ))}
                    </TableBody>
                </Table>
            </TableContainer>
        </Box>
    );
}
