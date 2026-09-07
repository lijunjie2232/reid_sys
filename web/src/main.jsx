import React from 'react'
import ReactDOM from 'react-dom/client'
import { CssBaseline, ThemeProvider, createTheme } from '@mui/material'
import App from './App.jsx'
import { I18nProvider } from './i18n/I18nProvider.jsx'
import './index.css'

const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: { main: '#4dabf7' },
    secondary: { main: '#a78bfa' },
    success: { main: '#37d67a' },
    background: { default: '#0a0e15', paper: '#121826' },
    divider: 'rgba(255,255,255,0.08)',
  },
  shape: { borderRadius: 14 },
  typography: {
    fontFamily:
      '"Inter", "Noto Sans SC", "Microsoft YaHei", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    h6: { fontWeight: 650, letterSpacing: '-0.01em' },
    button: { textTransform: 'none', fontWeight: 600 },
  },
  components: {
    MuiPaper: { styleOverrides: { root: { backgroundImage: 'none' } } },
    MuiButton: { defaultProps: { disableElevation: true } },
    MuiTab: { styleOverrides: { root: { minHeight: 46 } } },
  },
})

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <I18nProvider>
        <App />
      </I18nProvider>
    </ThemeProvider>
  </React.StrictMode>,
)
