import React, { useState } from 'react';
import { Card, CardContent, Typography, Slider, Box, Collapse, IconButton, Link } from '@mui/material';
import { ExpandMore as ExpandMoreIcon, OpenInNew as OpenInNewIcon } from '@mui/icons-material';
import { styled } from '@mui/material/styles';

interface Evidence {
    source_name: string;
    url: string;
    excerpt: string;
}

interface ImpactProps {
    impactNumber: number;
    description: string;
    clause: string;
    confidence: number;
    p10: number;
    p25: number;
    p50: number;
    p75: number;
    p90: number;
    evidence?: Evidence[];
    chainOfCausality?: string;
}

const ExpandMore = styled((props: { expand: boolean } & React.ComponentProps<typeof IconButton>) => {
    const { expand: _, ...other } = props;
    return <IconButton {...other} />;
})(({ theme, expand }) => ({
    transform: !expand ? 'rotate(0deg)' : 'rotate(180deg)',
    marginLeft: 'auto',
    transition: theme.transitions.create('transform', {
        duration: theme.transitions.duration.shortest,
    }),
}));

const ImpactCard: React.FC<{ impact: ImpactProps }> = ({ impact }) => {
    const [selectedPercentile, setSelectedPercentile] = useState(50);
    const [currentCost, setCurrentCost] = useState(impact.p50);
    const [isChainOpen, setIsChainOpen] = useState(false);
    const [isEvidenceOpen, setIsEvidenceOpen] = useState(false);

    const handleSliderChange = (_event: Event, newValue: number | number[]) => {
        const val = newValue as number;
        setSelectedPercentile(val);
        // Linear interpolation
        if (val <= 10) setCurrentCost(impact.p10);
        else if (val <= 25) {
            const ratio = (val - 10) / 15;
            setCurrentCost(impact.p10 + ratio * (impact.p25 - impact.p10));
        } else if (val <= 50) {
            const ratio = (val - 25) / 25;
            setCurrentCost(impact.p25 + ratio * (impact.p50 - impact.p25));
        } else if (val <= 75) {
            const ratio = (val - 50) / 25;
            setCurrentCost(impact.p50 + ratio * (impact.p75 - impact.p50));
        } else if (val <= 90) {
            const ratio = (val - 75) / 15;
            setCurrentCost(impact.p75 + ratio * (impact.p90 - impact.p75));
        } else {
            setCurrentCost(impact.p90);
        }
    };

    const getConfidenceColor = (conf: number) => {
        if (conf > 0.8) return 'success.main';
        if (conf > 0.6) return 'warning.main';
        return 'error.main';
    };

    return (
        <Card sx={{ mb: 2 }}>
            <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <Box>
                        <Typography variant="h6" component="div">
                            Impact #{impact.impactNumber}
                        </Typography>
                        <Typography variant="h4" component="div">
                            ${Math.round(currentCost).toLocaleString()} <Typography variant="body1" component="span">/year</Typography>
                        </Typography>
                    </Box>
                    <Typography sx={{ color: getConfidenceColor(impact.confidence) }}>
                        {Math.round(impact.confidence * 100)}% Confidence
                    </Typography>
                </Box>
                <Typography variant="body1" sx={{ mt: 2 }}>{impact.description}</Typography>
                <Typography variant="body2" sx={{ mt: 2, fontStyle: 'italic' }}>&quot;{impact.clause}&quot;</Typography>

                {impact.chainOfCausality && (
                    <Box sx={{ mt: 2 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }} onClick={() => setIsChainOpen(!isChainOpen)}>
                            <Typography variant="h6">Chain of Causality</Typography>
                            <ExpandMore expand={isChainOpen}><ExpandMoreIcon /></ExpandMore>
                        </Box>
                        <Collapse in={isChainOpen} timeout="auto" unmountOnExit>
                            <Typography variant="body2">{impact.chainOfCausality}</Typography>
                        </Collapse>
                    </Box>
                )}

                {impact.evidence && impact.evidence.length > 0 && (
                    <Box sx={{ mt: 2 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }} onClick={() => setIsEvidenceOpen(!isEvidenceOpen)}>
                            <Typography variant="h6">Evidence ({impact.evidence.length} sources)</Typography>
                            <ExpandMore expand={isEvidenceOpen}><ExpandMoreIcon /></ExpandMore>
                        </Box>
                        <Collapse in={isEvidenceOpen} timeout="auto" unmountOnExit>
                            {impact.evidence.map((ev, idx) => (
                                <Box key={idx} sx={{ mt: 1 }}>
                                    <Link href={ev.url} target="_blank" rel="noopener noreferrer">
                                        {ev.source_name} <OpenInNewIcon fontSize="small" />
                                    </Link>
                                    <Typography variant="body2" sx={{ fontStyle: 'italic' }}>&quot;{ev.excerpt}&quot;</Typography>
                                </Box>
                            ))}
                        </Collapse>
                    </Box>
                )}

                <Box sx={{ mt: 4 }}>
                    <Slider
                        value={selectedPercentile}
                        onChange={handleSliderChange}
                        aria-labelledby="percentile-slider"
                        valueLabelDisplay="auto"
                        step={1}
                        marks
                        min={10}
                        max={90}
                    />
                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="caption">${impact.p10.toLocaleString()}</Typography>
                        <Typography variant="caption">${impact.p90.toLocaleString()}</Typography>
                    </Box>
                </Box>
            </CardContent>
        </Card>
    );
};

export default ImpactCard;
