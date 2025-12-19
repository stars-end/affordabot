import { useState } from 'react';
import { ThemeProvider, createTheme } from '@mui/material/styles'
import CssBaseline from '@mui/material/CssBaseline'
import { Box, AppBar, Toolbar, Typography, Container, Tabs, Tab } from '@mui/material'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom'
import GlassBoxViewer from './components/GlassBoxViewer'
import LegislationList from './components/LegislationList'

const darkTheme = createTheme({
    palette: {
        mode: 'dark',
    },
});

const queryClient = new QueryClient();

function App() {
    const navigate = useNavigate();
    const location = useLocation();

    // Sync tab with URL
    const isAdminPath = location.pathname.startsWith('/admin');
    const [value, setValue] = useState(isAdminPath ? 1 : 0);

    const handleChange = (_event: React.SyntheticEvent, newValue: number) => {
        setValue(newValue);
        if (newValue === 0) navigate('/');
        else navigate('/admin');
    };

    return (
        <QueryClientProvider client={queryClient}>
            <ThemeProvider theme={darkTheme}>
                <CssBaseline />
                <Box sx={{ flexGrow: 1, height: '100vh', display: 'flex', flexDirection: 'column' }}>
                    <AppBar position="static">
                        <Toolbar>
                            <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
                                Affordabot V2 Prototype
                            </Typography>
                            <Tabs value={value} onChange={handleChange} textColor="inherit">
                                <Tab label="Legislation Analysis" />
                                <Tab label="Agent GlassBox" />
                            </Tabs>
                        </Toolbar>
                    </AppBar>
                    <Container maxWidth="xl" sx={{ mt: 2, flex: 1, pb: 4, height: 'calc(100vh - 80px)' }}>
                        <Routes>
                            <Route path="/" element={<LegislationList jurisdiction="sanjose" />} />
                            <Route path="/admin" element={<GlassBoxViewer />} />
                            <Route path="/admin/runs/:runId" element={<GlassBoxViewer />} />
                        </Routes>
                    </Container>
                </Box>
            </ThemeProvider>
        </QueryClientProvider>
    )
}

export default App
