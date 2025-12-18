import { ThemeProvider, createTheme } from '@mui/material/styles'
import CssBaseline from '@mui/material/CssBaseline'
import { Box, AppBar, Toolbar, Typography, Container } from '@mui/material'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import GlassBoxViewer from './components/GlassBoxViewer'

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
                                Affordabot Admin V2
                            </Typography>
                        </Toolbar>
                    </AppBar>
                    <Container maxWidth="xl" sx={{ mt: 4, flex: 1, pb: 4 }}>
                        <GlassBoxViewer />
                    </Container>
                </Box>
            </ThemeProvider>
        </QueryClientProvider>
    )
}

export default App
