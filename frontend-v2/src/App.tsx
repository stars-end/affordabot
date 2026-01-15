import { ThemeProvider, createTheme } from '@mui/material/styles'
import CssBaseline from '@mui/material/CssBaseline'
import { Box, AppBar, Toolbar, Typography, Container } from '@mui/material'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Routes, Route } from 'react-router-dom'
import DashboardPage from './components/DashboardPage'

const darkTheme = createTheme({
    palette: {
        mode: 'dark',
    },
});

const queryClient = new QueryClient();

function App() {
    return (
        <QueryClientProvider client={queryClient}>
            <ThemeProvider theme={darkTheme}>
                <CssBaseline />
                <Box sx={{ flexGrow: 1, height: '100vh', display: 'flex', flexDirection: 'column' }}>
                    <AppBar position="static">
                        <Toolbar>
                            <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
                                Affordabot
                            </Typography>
                        </Toolbar>
                    </AppBar>
                    <Container maxWidth="xl" sx={{ mt: 2, flex: 1, pb: 4, height: 'calc(100vh - 80px)' }}>
                        <Routes>
                            <Route path="/" element={<DashboardPage />} />
                        </Routes>
                    </Container>
                </Box>
            </ThemeProvider>
        </QueryClientProvider>
    )
}

export default App
