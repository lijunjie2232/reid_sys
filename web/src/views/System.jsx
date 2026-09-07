import { useState } from 'react'
import {
  Alert, Box, Button, Chip, CircularProgress, Divider, Stack, Table, TableBody, TableCell,
  TableHead, TableRow, Typography,
} from '@mui/material'
import StorageIcon from '@mui/icons-material/Storage'
import MemoryIcon from '@mui/icons-material/Memory'
import CloudQueueIcon from '@mui/icons-material/CloudQueue'
import { api } from '../api.js'
import { Metric, Panel } from '../ui.jsx'
import { useI18n } from '../i18n/I18nProvider.jsx'

const TIERS = [
  {
    icon: <MemoryIcon fontSize="small" />,
    titleKey: 'system.tierEnd',
    module: 'detect',
    tone: '#4dabf7',
    points: ['sysTierEnd1', 'sysTierEnd2', 'sysTierEnd3', 'sysTierEnd4'],
  },
  {
    icon: <StorageIcon fontSize="small" />,
    titleKey: 'system.tierEdge',
    module: 'backbone',
    tone: '#a78bfa',
    points: ['sysTierEdge1', 'sysTierEdge2', 'sysTierEdge3', 'sysTierEdge4'],
  },
  {
    icon: <CloudQueueIcon fontSize="small" />,
    titleKey: 'system.tierCloud',
    module: 'store',
    tone: '#37d67a',
    points: ['sysTierCloud1', 'sysTierCloud2', 'sysTierCloud3', 'sysTierCloud4'],
  },
]

export default function SystemView({ status, refresh }) {
  const { t } = useI18n()
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [indexResult, setIndexResult] = useState(null)
  const [evalResult, setEvalResult] = useState(null)

  const run = async (key, fn) => {
    setBusy(key); setError('')
    try {
      const data = await fn()
      if (key === 'index') setIndexResult(data)
      else setEvalResult(data)
      await refresh?.()
    } catch (e) {
      setError(String(e.message || e))
    } finally {
      setBusy('')
    }
  }

  return (
    <Stack spacing={2.5}>
      {error && <Alert severity="error">{error}</Alert>}

      <Panel title={t('system.runStatus')} subtitle={t('system.runStatusSubtitle')}>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(4, 1fr)' }, gap: 2 }}>
          <Metric label={t('system.backbone')} value={`R50 / ${status?.dim ?? '-'}d`} hint={status?.backbone} />
          <Metric label={t('system.device')} value={status?.device ?? '-'} hint={t('system.deviceHint')} />
          <Metric label={t('system.indexed')} value={`${status?.indexed ?? 0} / ${status?.gallery_total ?? 0}`} hint={status?.collection} />
          <Metric label={t('system.probeSet')} value={status?.probe_total ?? 0} hint={t('system.probeSetHint')} />
        </Box>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 2, fontFamily: 'ui-monospace, monospace' }}>
          detector = {status?.detector} · milvus = {status?.milvus_uri}
        </Typography>
      </Panel>

      <Panel title={t('system.tiers')} subtitle={t('system.tiersSubtitle')}>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'repeat(3, 1fr)' }, gap: 2 }}>
          {TIERS.map((tier, i) => (
            <Box
              key={tier.titleKey}
              sx={{
                position: 'relative',
                p: 2,
                borderRadius: 3,
                border: '1px solid',
                borderColor: 'divider',
                bgcolor: 'rgba(255,255,255,0.02)',
              }}
            >
              <Stack direction="row" spacing={1} alignItems="center" sx={{ color: tier.tone, mb: 1 }}>
                {tier.icon}
                <Typography variant="subtitle2" sx={{ color: 'text.primary' }}>{t(tier.titleKey)}</Typography>
              </Stack>
              <Chip size="small" variant="outlined" label={tier.module} sx={{ mb: 1.5, fontFamily: 'ui-monospace, monospace', borderColor: `${tier.tone}55`, color: tier.tone }} />
              <Stack spacing={0.75}>
                {tier.points.map((key) => (
                  <Stack key={key} direction="row" spacing={1} alignItems="center">
                    <Box sx={{ width: 5, height: 5, borderRadius: '50%', bgcolor: tier.tone, flexShrink: 0 }} />
                    <Typography variant="caption" color="text.secondary">{t(`system.${key}`)}</Typography>
                  </Stack>
                ))}
              </Stack>
              {i < TIERS.length - 1 && (
                <Typography sx={{ position: 'absolute', right: -14, top: '50%', transform: 'translateY(-50%)', display: { xs: 'none', md: 'block' }, opacity: 0.4 }}>
                  →
                </Typography>
              )}
            </Box>
          ))}
        </Box>
        <Divider sx={{ my: 2.5 }} />
        <Typography variant="caption" color="text.secondary">{t('system.tiersFootnote')}</Typography>
      </Panel>

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '1fr 1fr' }, gap: 2.5 }}>
        <Panel
          title={t('system.indexTitle')}
          subtitle={t('system.indexSubtitle')}
          action={
            <Button size="small" variant="contained" disabled={busy === 'index'} onClick={() => run('index', api.index)}>
              {busy === 'index' ? t('system.indexing') : t('system.indexBtn')}
            </Button>
          }
        >
          {busy === 'index' && <Stack direction="row" spacing={1.5} alignItems="center"><CircularProgress size={18} /><Typography variant="body2">{t('system.indexRunning')}</Typography></Stack>}
          {indexResult && busy !== 'index' && (
            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 2 }}>
              <Metric label={t('system.metricIndexed')} value={indexResult.indexed} />
              <Metric label={t('system.metricDim')} value={indexResult.dim} />
              <Metric label={t('system.metricCount')} value={indexResult.count} />
            </Box>
          )}
          {!indexResult && busy !== 'index' && (
            <Typography variant="body2" color="text.secondary">{t('system.indexHint')}</Typography>
          )}
        </Panel>

        <Panel
          title={t('system.evalTitle')}
          subtitle={t('system.evalSubtitle', { n: status?.probe_total ?? 0 })}
          action={
            <Button size="small" variant="contained" disabled={busy === 'eval'} onClick={() => run('eval', api.evaluate)}>
              {busy === 'eval' ? t('system.evaluating') : t('system.evalBtn')}
            </Button>
          }
        >
          {busy === 'eval' && <Stack direction="row" spacing={1.5} alignItems="center"><CircularProgress size={18} /><Typography variant="body2">{t('system.evalRunning')}</Typography></Stack>}
          {evalResult && busy !== 'eval' && (
            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 2 }}>
              <Metric label={t('system.rank1')} value={`${(evalResult.rank1 * 100).toFixed(2)}%`} hint={t('system.queriesHint', { n: evalResult.queries })} />
              <Metric label={t('system.rank5')} value={`${(evalResult.rank5 * 100).toFixed(2)}%`} />
              <Metric label="mAP" value={evalResult.mAP.toFixed(4)} hint={t('system.missHint', { n: evalResult.miss })} />
            </Box>
          )}
          {!evalResult && busy !== 'eval' && (
            <Typography variant="body2" color="text.secondary">{t('system.evalHint')}</Typography>
          )}
        </Panel>
      </Box>

      {evalResult && (
        <Panel title={t('system.detailTitle')} subtitle={t('system.detailSubtitle')}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>{t('system.colProbe')}</TableCell>
                <TableCell>{t('system.colTruth')}</TableCell>
                <TableCell>{t('system.colTop1')}</TableCell>
                <TableCell align="right">{t('system.colScore')}</TableCell>
                <TableCell align="right">{t('system.colRank')}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {evalResult.samples.map((s) => (
                <TableRow key={s.probe}>
                  <TableCell sx={{ fontFamily: 'ui-monospace, monospace', fontSize: 12 }}>{s.probe}</TableCell>
                  <TableCell>{s.truth}</TableCell>
                  <TableCell>{s.top1}</TableCell>
                  <TableCell align="right" sx={{ fontFamily: 'ui-monospace, monospace' }}>{s.top1_score.toFixed(4)}</TableCell>
                  <TableCell align="right">
                    <Chip
                      size="small"
                      color={s.rank === 1 ? 'success' : s.rank ? 'warning' : 'error'}
                      label={s.rank ?? 'miss'}
                      sx={{ height: 20 }}
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Panel>
      )}
    </Stack>
  )
}
