import { useEffect, useState } from 'react'
import {
  Box, Button, Chip, Menu, MenuItem, Stack, Tooltip, Typography,
} from '@mui/material'
import StorageOutlinedIcon from '@mui/icons-material/StorageOutlined'
import { api } from './api.js'
import { useI18n } from './i18n/I18nProvider.jsx'

/**
 * 数据集切换。
 *
 * 数据来源是后端 `/api/datasets`：它扫描 `data/` 下所有含
 * `query/ + gallery/ + meta.json` 的目录，每个目录对应一个 Milvus collection
 * （见 `reid_sys/datasets.py`）。所以后端加了新数据集，这里会自动出现，
 * 前端不需要改动。
 *
 * 切换动作分两步：
 *   1. `api.selectDataset(name)` —— 先把名字写进 api 模块，之后所有请求自动带
 *      `?dataset=<name>`；
 *   2. `onChanged()` —— 通知 App 重新拉 status，并让当前 view 重挂载（React key
 *      变化触发）；`onBusy` 则用来展示「切库中」的转圈。
 *
 * 索引未就绪的数据集仍然可选 —— 后端会返回 indexed < gallery_total，
 * 在菜单项里直接标注出来，避免切过去一片空结果还以为坏了。
 */
export function DatasetMenu({ onChanged, onBusy }) {
  const { t } = useI18n()
  const [anchor, setAnchor] = useState(null)
  const [list, setList] = useState(null)
  const [current, setCurrent] = useState(null)
  const [busy, setBusy] = useState(false)

  const load = async () => {
    try {
      const d = await api.datasets()
      setList(d.items || [])
      setCurrent(d.current)
    } catch {
      setList([])
    }
  }

  // 首次挂载拉一次；切完数据集后由父组件通过 onChanged 反向触发刷新
  useEffect(() => { load() }, [])

  const pick = async (name) => {
    setAnchor(null)
    if (name === current) return
    setBusy(true)
    onBusy?.(true)
    try {
      await api.selectDataset(name)
      setCurrent(name)
      await load()
      await onChanged?.(name)
    } finally {
      setBusy(false)
      onBusy?.(false)
    }
  }

  const active = list?.find((d) => d.name === current)
  // 列表还没拉回来时 active 是 undefined —— 此时不要急着打「未索引」标，否则会闪一下
  const notReady = Boolean(active) && !(active.indexed >= active.gallery_total && active.gallery_total > 0)

  return (
    <>
      <Tooltip title={t('dataset.switchHint')}>
        <Button
          size="small"
          variant="outlined"
          startIcon={<StorageOutlinedIcon fontSize="small" />}
          onClick={(e) => setAnchor(e.currentTarget)}
          disabled={busy}
          sx={{ flexShrink: 0 }}
        >
          <Box component="span" sx={{ fontFamily: 'ui-monospace, monospace' }}>
            {busy ? '…' : (current || t('dataset.none'))}
          </Box>
          {!busy && notReady && (
            <Chip
              size="small"
              label={t('dataset.notIndexed')}
              color="warning"
              variant="outlined"
              sx={{ ml: 1, height: 18, fontSize: 10 }}
            />
          )}
        </Button>
      </Tooltip>

      <Menu anchorEl={anchor} open={Boolean(anchor)} onClose={() => setAnchor(null)}>
        <Typography variant="caption" color="text.secondary" sx={{ px: 2, py: 0.5, display: 'block' }}>
          {t('dataset.title')}
        </Typography>

        {(list || []).map((d) => {
          const ok = d.gallery_total > 0 && d.indexed >= d.gallery_total
          return (
            <MenuItem key={d.name} selected={d.name === current} onClick={() => pick(d.name)} sx={{ py: 1 }}>
              <Stack sx={{ minWidth: 300 }} spacing={0.25}>
                <Stack direction="row" spacing={1} alignItems="center">
                  <Typography variant="body2" sx={{ fontFamily: 'ui-monospace, monospace', fontWeight: 700 }}>
                    {d.name}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ flex: 1 }}>
                    {d.title}
                  </Typography>
                  <Chip
                    size="small"
                    variant="outlined"
                    color={ok ? 'success' : 'warning'}
                    label={ok ? t('dataset.ready') : t('dataset.notIndexed')}
                    sx={{ height: 18, fontSize: 10 }}
                  />
                </Stack>
                <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'ui-monospace, monospace' }}>
                  {d.collection} · {t('dataset.counts', { q: d.query_total, g: d.gallery_total, i: d.indexed })}
                </Typography>
              </Stack>
            </MenuItem>
          )
        })}

        {list && list.length === 0 && (
          <MenuItem disabled>
            <Typography variant="caption">{t('dataset.empty')}</Typography>
          </MenuItem>
        )}
      </Menu>
    </>
  )
}
