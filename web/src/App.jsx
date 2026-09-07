import { useCallback, useEffect, useState } from 'react'
import {
  AppBar, Box, Button, CircularProgress, Stack, Tab, Tabs, Toolbar, Typography,
} from '@mui/material'
import HubOutlinedIcon from '@mui/icons-material/HubOutlined'
import { api } from './api.js'
import { StatChip } from './ui.jsx'
import { useI18n } from './i18n/I18nProvider.jsx'
import { LocaleMenu } from './LocaleMenu.jsx'
import { DatasetMenu } from './DatasetMenu.jsx'
import SearchView from './views/Search.jsx'
import GalleryView from './views/Gallery.jsx'
import DetectView from './views/Detect.jsx'
import ArchitectureView from './views/Architecture.jsx'
import CamerasView from './views/Cameras.jsx'
import EdgesView from './views/Edges.jsx'
import MapView from './views/MapView.jsx'
import K8sView from './views/K8sView.jsx'
import SystemView from './views/System.jsx'

// 页签顺序即深链编号 #0 ~ #8
const TABS = [
  { key: 'search', view: SearchView },
  { key: 'gallery', view: GalleryView },
  { key: 'detect', view: DetectView },
  { key: 'architecture', view: ArchitectureView },
  { key: 'cameras', view: CamerasView },
  { key: 'edges', view: EdgesView },
  { key: 'map', view: MapView },
  { key: 'k8s', view: K8sView },
  { key: 'system', view: SystemView },
]

export default function App() {
  const { t } = useI18n()

  // 支持 #0 ~ #8 深链到具体页签（也方便截图/分享）
  const [tab, setTab] = useState(() => {
    const n = Number(window.location.hash.slice(1))
    return Number.isInteger(n) && n >= 0 && n < TABS.length ? n : 0
  })
  const [status, setStatus] = useState(null)
  const [error, setError] = useState('')
  // 当前数据集名：从 /api/datasets 同步回来，仅用于给视图做 key —— 换库时强制重挂载，
  // 免得旧数据集的结果残留在页面上。
  const [dataset, setDataset] = useState('')
  const [switching, setSwitching] = useState(false)

  const refresh = useCallback(async () => {
    try {
      setStatus(await api.status())
      setError('')
    } catch (e) {
      setError(String(e.message || e))
    }
  }, [])

  // 首次进入：先对齐后端当前数据集，再拉状态（否则 status 与下拉框可能不一致）
  useEffect(() => {
    api.datasets()
      .then((d) => setDataset(d.current || ''))
      .catch(() => {})
      .finally(() => refresh())
  }, [refresh])

  const onDatasetChanged = useCallback(async (name) => {
    setDataset(name || '')
    await refresh()
  }, [refresh])

  const Current = TABS[tab].view

  return (
    <Box sx={{ minHeight: '100vh' }}>
      <AppBar
        position="sticky"
        elevation={0}
        sx={{ bgcolor: 'rgba(10,14,21,0.78)', backdropFilter: 'blur(14px)', borderBottom: '1px solid', borderColor: 'divider' }}
      >
        <Toolbar sx={{ gap: 2, flexWrap: 'wrap', py: 1 }}>
          <HubOutlinedIcon color="primary" />
          <Box sx={{ flex: 1, minWidth: 220 }}>
            <Typography variant="h6" sx={{ lineHeight: 1.2 }}>
              {t('app.title')}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {t('app.subtitle')}
            </Typography>
          </Box>
          {status && (
            <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 0.75 }}>
              <StatChip label={t('status.backbone')} value={`R50 · ${status.dim}d`} tone="primary" />
              <StatChip label={t('status.device')} value={status.device} tone={status.device === 'cuda' ? 'success' : 'default'} />
              <StatChip label={t('dataset.chip')} value={status.dataset} tone="secondary" />
              <StatChip label={t('status.milvus')} value={`${status.indexed}/${status.gallery_total}`} tone="secondary" />
              <StatChip label={t('status.probe')} value={status.probe_total} />
            </Stack>
          )}
          <DatasetMenu onChanged={onDatasetChanged} onBusy={setSwitching} />
          <LocaleMenu />
          <Button size="small" variant="outlined" onClick={refresh}>{t('common.refreshStatus')}</Button>
        </Toolbar>
        <Tabs
          value={tab}
          onChange={(_, v) => { setTab(v); window.location.hash = String(v) }}
          variant="scrollable"
          scrollButtons="auto"
          sx={{ px: 2, minHeight: 46 }}
        >
          {TABS.map(({ key }) => (
            <Tab key={key} label={t(`tabs.${key}`)} />
          ))}
        </Tabs>
      </AppBar>

      {error && (
        <Box sx={{ px: 3, py: 2 }}>
          <Typography color="error" variant="body2">
            {t('common.backendDown')}：{error}
          </Typography>
        </Box>
      )}

      <Box sx={{ p: 3, maxWidth: 1600, mx: 'auto', opacity: switching ? 0.5 : 1, transition: 'opacity .15s' }}>
        {/* key 带上数据集名：切库时整个视图重挂载，清掉上一个数据集的检索结果 */}
        <Current key={dataset} status={status} refresh={refresh} />
      </Box>

      {!status && !error && (
        <Stack alignItems="center" sx={{ py: 8 }}>
          <CircularProgress size={26} />
          <Typography variant="caption" color="text.secondary" sx={{ mt: 1.5 }}>
            {t('common.loading')}
          </Typography>
        </Stack>
      )}
    </Box>
  )
}
