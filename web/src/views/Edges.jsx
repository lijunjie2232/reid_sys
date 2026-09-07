import { useCallback, useEffect, useState } from 'react'
import {
  Alert, Box, Chip, CircularProgress, Divider, IconButton, Stack, Table, TableBody,
  TableCell, TableHead, TableRow, Tooltip, Typography,
} from '@mui/material'
import RefreshIcon from '@mui/icons-material/Refresh'
import RouterOutlinedIcon from '@mui/icons-material/RouterOutlined'
import { api } from '../api.js'
import { Panel } from '../ui.jsx'
import { useI18n } from '../i18n/I18nProvider.jsx'
import { DemoNotice, MetricCell, NotConnectedChip, PlaceholderPanel } from '../components.jsx'

// 数据来自 GET /api/monitor/edges —— 接口契约已定义，服务尚未接入，
// 因此返回 connected=false 且实时指标为空（null -> 显示 —）。
export default function EdgesView() {
  const { t } = useI18n()
  const [data, setData] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setBusy(true)
    try {
      setData(await api.monitorEdges())
      setError('')
    } catch (e) {
      setError(String(e.message || e))
    } finally {
      setBusy(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const rows = data?.rows ?? []
  const metrics = data?.metrics ?? {}
  const dash = (v) => (v === null || v === undefined ? '—' : v)

  return (
    <Stack spacing={2.5}>
      <DemoNotice detail={t('edges.demoDetail')} />

      <Panel
        title={t('tabs.edges')}
        subtitle={t('edges.subtitle')}
        action={
          <Stack direction="row" spacing={1.5} alignItems="center">
            {busy && <CircularProgress size={16} />}
            <Tooltip title={t('common.refresh')}>
              <IconButton size="small" onClick={load}><RefreshIcon fontSize="small" /></IconButton>
            </Tooltip>
          </Stack>
        }
      >
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(4, 1fr)' }, gap: 2, mb: 2.5 }}>
          <MetricCell label={t('edges.mOnline')} value={dash(metrics.online)} />
          <MetricCell label={t('edges.mRtt')} value={dash(metrics.avg_rtt_ms)} />
          <MetricCell label={t('edges.mThroughput')} value={dash(metrics.embedding_qps)} />
          <MetricCell label={t('edges.mWatchlist')} value={dash(metrics.watchlist_hits)} />
        </Box>

        <Divider sx={{ mb: 2 }} />

        <Box sx={{ overflowX: 'auto' }}>
          <Table size="small" sx={{ minWidth: 860 }}>
            <TableHead>
              <TableRow>
                <TableCell>{t('edges.colNode')}</TableCell>
                <TableCell>{t('edges.colZone')}</TableCell>
                <TableCell align="right">{t('edges.colIpc')}</TableCell>
                <TableCell align="right">{t('edges.colPing')}</TableCell>
                <TableCell align="right">QPS</TableCell>
                <TableCell align="right">{t('edges.colLoad')}</TableCell>
                <TableCell>{t('edges.colPod')}</TableCell>
                <TableCell>{t('edges.colStatus')}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.map((r) => (
                <TableRow key={r.id}>
                  <TableCell sx={{ fontFamily: 'ui-monospace, monospace', fontSize: 12 }}>
                    <Stack direction="row" spacing={1} alignItems="center">
                      <RouterOutlinedIcon fontSize="small" sx={{ opacity: 0.45 }} />
                      {r.id}
                    </Stack>
                  </TableCell>
                  <TableCell><Typography variant="caption" color="text.secondary">{t('edges.zonePrefix')}{r.zone ?? '—'}</Typography></TableCell>
                  <TableCell align="right" sx={{ fontFamily: 'ui-monospace, monospace' }}>{dash(r.ipcs_managed)}</TableCell>
                  <TableCell align="right" sx={{ fontFamily: 'ui-monospace, monospace', color: 'text.disabled' }}>{dash(r.ping_ms)}</TableCell>
                  <TableCell align="right" sx={{ fontFamily: 'ui-monospace, monospace', color: 'text.disabled' }}>{dash(r.qps)}</TableCell>
                  <TableCell align="right" sx={{ fontFamily: 'ui-monospace, monospace', color: 'text.disabled' }}>{dash(r.load_pct)}</TableCell>
                  <TableCell align="right" sx={{ fontFamily: 'ui-monospace, monospace', color: 'text.disabled' }}>{dash(r.pod)}</TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={1}>
                      <Chip size="small" variant="outlined" label={t('edges.offline')} sx={{ height: 20, opacity: 0.6 }} />
                      <NotConnectedChip />
                    </Stack>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Box>

        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 2 }}>
          {t('edges.tableNote')}
        </Typography>
      </Panel>

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: 'repeat(3, 1fr)' }, gap: 2.5 }}>
        <PlaceholderPanel
          title={t('edges.pingTitle')}
          subtitle={t('edges.pingSubtitle')}
          note={t('edges.pingNote')}
        >
          <Stack spacing={0.75}>
            {['edges.ping1', 'edges.ping2', 'edges.ping3', 'edges.ping4'].map((k) => (
              <Typography key={k} variant="caption" color="text.secondary">· {t(k)}</Typography>
            ))}
          </Stack>
        </PlaceholderPanel>

        <PlaceholderPanel
          title={t('edges.liveTitle')}
          subtitle={t('edges.liveSubtitle')}
          note={t('edges.liveNote')}
        >
          <Stack spacing={0.75}>
            {['edges.live1', 'edges.live2', 'edges.live3', 'edges.live4'].map((k) => (
              <Typography key={k} variant="caption" color="text.secondary">· {t(k)}</Typography>
            ))}
          </Stack>
        </PlaceholderPanel>

        <PlaceholderPanel
          title={t('edges.loadTitle')}
          subtitle={t('edges.loadSubtitle')}
          note={t('edges.loadNote')}
        >
          <Stack spacing={0.75}>
            {['edges.load1', 'edges.load2', 'edges.load3', 'edges.load4'].map((k) => (
              <Typography key={k} variant="caption" color="text.secondary">· {t(k)}</Typography>
            ))}
          </Stack>
        </PlaceholderPanel>
      </Box>
    </Stack>
  )
}
