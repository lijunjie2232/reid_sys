import { useCallback, useEffect, useState } from 'react'
import {
  Alert, Box, Chip, CircularProgress, Divider, IconButton, Stack, Table, TableBody,
  TableCell, TableHead, TableRow, Tooltip, Typography,
} from '@mui/material'
import RefreshIcon from '@mui/icons-material/Refresh'
import VideocamOutlinedIcon from '@mui/icons-material/VideocamOutlined'
import { api } from '../api.js'
import { Panel } from '../ui.jsx'
import { useI18n } from '../i18n/I18nProvider.jsx'
import { DemoNotice, MetricCell, NotConnectedChip, PlaceholderPanel } from '../components.jsx'

// 数据来自 GET /api/monitor/cameras —— 接口契约已定义，服务尚未接入，
// 因此返回 connected=false 且实时指标为空（null -> 显示 —）。
export default function CamerasView() {
  const { t } = useI18n()
  const [data, setData] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setBusy(true)
    try {
      setData(await api.monitorCameras())
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
      <DemoNotice detail={t('cameras.demoDetail')} />

      <Panel
        title={t('tabs.cameras')}
        subtitle={t('cameras.subtitle')}
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
          <MetricCell label={t('cameras.mOnline')} value={dash(metrics.online)} />
          <MetricCell label={t('cameras.mRtt')} value={dash(metrics.avg_rtt_ms)} />
          <MetricCell label={t('cameras.mEmitRate')} value={dash(metrics.capture_rate_fps)} />
          <MetricCell label={t('cameras.mNpu')} value={dash(metrics.avg_npu_load)} />
        </Box>

        <Divider sx={{ mb: 2 }} />

        <Box sx={{ overflowX: 'auto' }}>
          <Table size="small" sx={{ minWidth: 780 }}>
            <TableHead>
              <TableRow>
                <TableCell>{t('cameras.colDevice')}</TableCell>
                <TableCell>{t('cameras.colZone')}</TableCell>
                <TableCell align="right">{t('cameras.colPing')}</TableCell>
                <TableCell align="right">FPS</TableCell>
                <TableCell align="right">{t('cameras.colNpu')}</TableCell>
                <TableCell align="right">{t('cameras.colEmit')}</TableCell>
                <TableCell>{t('cameras.colStream')}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.map((r) => (
                <TableRow key={r.id}>
                  <TableCell sx={{ fontFamily: 'ui-monospace, monospace', fontSize: 12 }}>
                    <Stack direction="row" spacing={1} alignItems="center">
                      <VideocamOutlinedIcon fontSize="small" sx={{ opacity: 0.45 }} />
                      {r.id}
                    </Stack>
                  </TableCell>
                  <TableCell>
                    <Typography variant="caption" color="text.secondary">{r.zone ?? '—'}</Typography>
                  </TableCell>
                  <TableCell align="right" sx={{ fontFamily: 'ui-monospace, monospace', color: 'text.disabled' }}>{dash(r.ping_ms)}</TableCell>
                  <TableCell align="right" sx={{ fontFamily: 'ui-monospace, monospace', color: 'text.disabled' }}>{dash(r.fps)}</TableCell>
                  <TableCell align="right" sx={{ fontFamily: 'ui-monospace, monospace', color: 'text.disabled' }}>{dash(r.npu_load)}</TableCell>
                  <TableCell align="right" sx={{ fontFamily: 'ui-monospace, monospace', color: 'text.disabled' }}>{dash(r.emit_qps)}</TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={1}>
                      <Chip size="small" variant="outlined" label={t('cameras.offline')} sx={{ height: 20, opacity: 0.6 }} />
                      <NotConnectedChip />
                    </Stack>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Box>

        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 2 }}>
          {t('cameras.tableNote')}
        </Typography>
      </Panel>

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: 'repeat(3, 1fr)' }, gap: 2.5 }}>
        <PlaceholderPanel
          title={t('cameras.pingTitle')}
          subtitle={t('cameras.pingSubtitle')}
          note={t('cameras.pingNote')}
        >
          <Stack spacing={0.75}>
            {['cameras.ping1', 'cameras.ping2', 'cameras.ping3', 'cameras.ping4'].map((k) => (
              <Typography key={k} variant="caption" color="text.secondary">· {t(k)}</Typography>
            ))}
          </Stack>
        </PlaceholderPanel>

        <PlaceholderPanel
          title={t('cameras.liveTitle')}
          subtitle={t('cameras.liveSubtitle')}
          note={t('cameras.liveNote')}
        >
          <Stack spacing={0.75}>
            {['cameras.live1', 'cameras.live2', 'cameras.live3', 'cameras.live4'].map((k) => (
              <Typography key={k} variant="caption" color="text.secondary">· {t(k)}</Typography>
            ))}
          </Stack>
        </PlaceholderPanel>

        <PlaceholderPanel
          title={t('cameras.loadTitle')}
          subtitle={t('cameras.loadSubtitle')}
          note={t('cameras.loadNote')}
        >
          <Stack spacing={0.75}>
            {['cameras.load1', 'cameras.load2', 'cameras.load3', 'cameras.load4'].map((k) => (
              <Typography key={k} variant="caption" color="text.secondary">· {t(k)}</Typography>
            ))}
          </Stack>
        </PlaceholderPanel>
      </Box>
    </Stack>
  )
}
