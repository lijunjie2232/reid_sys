import { useCallback, useEffect, useState } from 'react'
import {
  Alert, Box, Chip, CircularProgress, Divider, IconButton, Stack, Table, TableBody,
  TableCell, TableHead, TableRow, Tooltip, Typography,
} from '@mui/material'
import RefreshIcon from '@mui/icons-material/Refresh'
import { api } from '../api.js'
import { Panel } from '../ui.jsx'
import { useI18n } from '../i18n/I18nProvider.jsx'
import { DemoNotice, MetricCell, NotConnectedChip, PlaceholderPanel } from '../components.jsx'

const CLUSTER_TONE = { edge: '#a78bfa', cloud: '#4dabf7' }

// 工作负载清单来自 GET /api/k8s/workloads —— 对应 docs/SYSTEM.md 核心设计原则 5：
// Docker 镜像化 + K3s(边) / K8s(云) 统一编排。接口契约已定义，集群尚未接入。
export default function K8sView() {
  const { t } = useI18n()
  const [data, setData] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setBusy(true)
    try {
      setData(await api.k8sWorkloads())
      setError('')
    } catch (e) {
      setError(String(e.message || e))
    } finally {
      setBusy(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const workloads = data?.workloads ?? []
  const summary = data?.summary ?? {}
  const dash = (v) => (v === null || v === undefined ? '—' : v)

  return (
    <Stack spacing={2.5}>
      <DemoNotice detail={t('k8s.demoDetail')} />

      <Panel
        title={t('tabs.k8s')}
        subtitle={t('k8s.panelSubtitle')}
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

        <Typography variant="body2" sx={{ mb: 2 }}>
          {t('k8s.panelBody')}
        </Typography>

        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(4, 1fr)' }, gap: 2 }}>
          <MetricCell label={t('k8s.mCloudCluster')} value={dash(summary.cloud_cluster)} />
          <MetricCell label={t('k8s.mEdgeCluster')} value={dash(summary.edge_cluster)} />
          <MetricCell label={t('k8s.mPods')} value={dash(summary.running_pods)} />
          <MetricCell label={t('k8s.mImageConsistency')} value={dash(summary.image_consistency)} />
        </Box>

        <Divider sx={{ my: 2.5 }} />

        <Box sx={{ overflowX: 'auto' }}>
          <Table size="small" sx={{ minWidth: 900 }}>
            <TableHead>
              <TableRow>
                <TableCell>{t('k8s.colCluster')}</TableCell>
                <TableCell>{t('k8s.colNamespace')}</TableCell>
                <TableCell>{t('k8s.colWorkload')}</TableCell>
                <TableCell>{t('k8s.colKind')}</TableCell>
                <TableCell>{t('k8s.colImage')}</TableCell>
                <TableCell align="right">Ready</TableCell>
                <TableCell>{t('k8s.colRole')}</TableCell>
                <TableCell>{t('k8s.colStatus')}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {workloads.map((w) => (
                <TableRow key={`${w.cluster}-${w.name}`}>
                  <TableCell>
                    <Chip
                      size="small"
                      label={w.cluster}
                      sx={{ height: 20, bgcolor: `${CLUSTER_TONE[w.cluster]}22`, color: CLUSTER_TONE[w.cluster], border: `1px solid ${CLUSTER_TONE[w.cluster]}55` }}
                    />
                  </TableCell>
                  <TableCell sx={{ fontFamily: 'ui-monospace, monospace', fontSize: 11.5 }}>{w.namespace}</TableCell>
                  <TableCell sx={{ fontFamily: 'ui-monospace, monospace', fontSize: 11.5 }}>{w.name}</TableCell>
                  <TableCell>
                    <Typography variant="caption" color="text.secondary">{w.kind}</Typography>
                  </TableCell>
                  <TableCell sx={{ fontFamily: 'ui-monospace, monospace', fontSize: 11 }}>{w.image}</TableCell>
                  <TableCell align="right" sx={{ fontFamily: 'ui-monospace, monospace', color: 'text.disabled' }}>{dash(w.ready)}</TableCell>
                  <TableCell>
                    <Typography variant="caption" color="text.secondary">{t(`k8s.${w.role_key}`)}</Typography>
                    {w.schedule && (
                      <Typography variant="caption" sx={{ display: 'block', fontFamily: 'ui-monospace, monospace', color: 'text.disabled', fontSize: 10 }}>
                        {w.schedule}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell><NotConnectedChip /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Box>

        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 2 }}>
          {t('k8s.apiNote')}
        </Typography>
      </Panel>

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: 'repeat(3, 1fr)' }, gap: 2.5 }}>
        <PlaceholderPanel
          title={t('k8s.imageTitle')}
          subtitle={t('k8s.imageSubtitle')}
          note={t('k8s.imageNote')}
        >
          <Stack spacing={0.75}>
            {['k8s.image1', 'k8s.image2', 'k8s.image3', 'k8s.image4'].map((k) => (
              <Typography key={k} variant="caption" color="text.secondary">· {t(k)}</Typography>
            ))}
          </Stack>
        </PlaceholderPanel>

        <PlaceholderPanel
          title={t('k8s.rolloutTitle')}
          subtitle={t('k8s.rolloutSubtitle')}
          note={t('k8s.rolloutNote')}
        >
          <Stack spacing={0.75}>
            {['k8s.rollout1', 'k8s.rollout2', 'k8s.rollout3', 'k8s.rollout4'].map((k) => (
              <Typography key={k} variant="caption" color="text.secondary">· {t(k)}</Typography>
            ))}
          </Stack>
        </PlaceholderPanel>

        <PlaceholderPanel
          title={t('k8s.hpaTitle')}
          subtitle={t('k8s.hpaSubtitle')}
          note={t('k8s.hpaNote')}
        >
          <Stack spacing={0.75}>
            {['k8s.hpa1', 'k8s.hpa2', 'k8s.hpa3', 'k8s.hpa4'].map((k) => (
              <Typography key={k} variant="caption" color="text.secondary">· {t(k)}</Typography>
            ))}
          </Stack>
        </PlaceholderPanel>
      </Box>

      <Panel title={t('k8s.actualTitle')} subtitle={t('k8s.actualSubtitle')}>
        <Stack spacing={1.25}>
          {[
            ['runtime', 'actualRuntime'],
            ['orchestration', 'actualOrchestration'],
            ['vectorStore', 'actualVectorStore'],
            ['device', 'actualDevice'],
            ['model', 'actualModel'],
            ['deploy', 'actualDeploy'],
          ].map(([labelKey, valueKey]) => (
            <Box key={labelKey} sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '150px 1fr' }, gap: 1.5 }}>
              <Typography variant="caption" color="text.secondary">{t(`k8s.${labelKey}`)}</Typography>
              <Typography variant="body2">{t(`k8s.${valueKey}`)}</Typography>
            </Box>
          ))}
        </Stack>
      </Panel>
    </Stack>
  )
}
