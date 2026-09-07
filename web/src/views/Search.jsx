import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Alert, Box, Button, Chip, CircularProgress, IconButton, Slider, Stack, TextField, Tooltip, Typography,
} from '@mui/material'
import SearchIcon from '@mui/icons-material/Search'
import UploadFileIcon from '@mui/icons-material/UploadFile'
import { api } from '../api.js'
import { Panel, PersonTile, ScoreBar } from '../ui.jsx'
import { useI18n } from '../i18n/I18nProvider.jsx'

// cosine 分数低于这条线的检索结果视为「不相关」——进度条从 0 起算没区分度，
// 所以 ScoreBar 以它为起点做线性映射。
const THRESHOLD = 0.95

export default function SearchView() {
  const { t } = useI18n()
  const [probes, setProbes] = useState([])
  const [filter, setFilter] = useState('')
  const [selected, setSelected] = useState(null)
  const [topk, setTopk] = useState(10)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const fileRef = useRef(null)

  useEffect(() => {
    api.probe().then((d) => {
      setProbes(d.items)
      // 支持 ?probe=<文件名> 深链，直接出结果
      const name = new URLSearchParams(window.location.search).get('probe')
      const item = d.items.find((p) => p.id === name)
      if (item) searchProbe(item)
    }).catch((e) => setError(String(e.message || e)))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const shown = useMemo(
    () => probes.filter((p) => !filter || p.id.includes(filter)),
    [probes, filter],
  )

  const run = async (fn, mark) => {
    setBusy(true)
    setError('')
    try {
      const data = await fn()
      setResult(data)
      setSelected(mark ?? null)
    } catch (e) {
      setError(String(e.message || e))
    } finally {
      setBusy(false)
    }
  }

  const searchProbe = (item) =>
    run(() => api.searchProbe(item.id, topk).then((d) => ({ ...d, kind: 'probe' })), item)

  const onUpload = (e) => {
    const file = e.target.files?.[0]
    if (file) run(() => api.searchUpload(file, topk).then((d) => ({ ...d, kind: 'upload' })))
    e.target.value = ''
  }

  const truth = result?.kind === 'probe' ? result.truth : null
  const hit1 = truth && result?.hits?.[0]?.person_id === truth
  const firstRank = truth ? result.hits.findIndex((h) => h.person_id === truth) + 1 : 0

  return (
    <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '380px 1fr' }, gap: 2.5 }}>
      <Panel
        title={t('search.probeTitle')}
        subtitle={t('search.probeSubtitle', { n: probes.length })}
        action={
          <>
            <input ref={fileRef} type="file" accept="image/*" hidden onChange={onUpload} />
            <Tooltip title={t('search.uploadTip')}>
              <Button size="small" variant="contained" startIcon={<UploadFileIcon />} onClick={() => fileRef.current?.click()}>
                {t('search.upload')}
              </Button>
            </Tooltip>
          </>
        }
        sx={{ height: { lg: 'calc(100vh - 230px)' } }}
        bodySx={{ display: 'flex', flexDirection: 'column', gap: 1.5, pt: 1.5 }}
      >
        <TextField
          size="small"
          fullWidth
          placeholder={t('search.filterPlaceholder')}
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <Box
          sx={{
            flex: 1,
            minHeight: 260,
            overflowY: 'auto',
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(88px, 1fr))',
            gap: 1,
            pr: 0.5,
          }}
        >
          {shown.map((p) => (
            <Tooltip key={p.id} title={`${p.id} · person ${p.person_id}`}>
              <Box>
                <PersonTile
                  name={p.id}
                  url={p.url}
                  height={112}
                  badge={p.person_id}
                  active={selected?.id === p.id}
                  onClick={() => searchProbe(p)}
                />
              </Box>
            </Tooltip>
          ))}
        </Box>
        <Typography variant="caption" color="text.secondary">
          {t('search.clickHint')}
        </Typography>
      </Panel>

      <Stack spacing={2.5}>
        <Panel
          title={t('search.params')}
          subtitle={t('search.paramsSubtitle')}
          action={
            <Stack direction="row" spacing={2} alignItems="center" sx={{ minWidth: 240 }}>
              <Typography variant="caption" color="text.secondary">Top-K</Typography>
              <Slider
                size="small"
                min={1}
                max={30}
                value={topk}
                onChange={(_, v) => setTopk(v)}
                sx={{ width: 150 }}
              />
              <Typography variant="caption" sx={{ fontFamily: 'ui-monospace, monospace', width: 20 }}>
                {topk}
              </Typography>
            </Stack>
          }
        >
          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
          {!result && !busy && (
            <Typography variant="body2" color="text.secondary">
              {t('search.pickHint')}
            </Typography>
          )}
          {busy && (
            <Stack direction="row" spacing={1.5} alignItems="center">
              <CircularProgress size={18} />
              <Typography variant="body2" color="text.secondary">{t('search.searching')}</Typography>
            </Stack>
          )}
          {result && !busy && (
            <Stack direction={{ xs: 'column', md: 'row' }} spacing={2.5} alignItems="flex-start">
              <Box sx={{ width: 132, flexShrink: 0 }}>
                <Box className="tile" sx={{ height: 264, cursor: 'default' }}>
                  <img src={result.kind === 'probe' ? result.query.url : result.query_image} alt="query" />
                </Box>
                <Typography variant="caption" color="text.secondary" sx={{ mt: 0.75, display: 'block', wordBreak: 'break-all' }}>
                  {result.kind === 'probe' ? result.query.id : t('search.localUpload')}
                </Typography>
              </Box>
              <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 1 }}>
                <Chip size="small" label={t('search.returned', { n: result.hits.length })} />
                {truth && (
                  <Chip
                    size="small"
                    color={hit1 ? 'success' : 'warning'}
                    label={
                      hit1
                        ? t('search.rank1Hit', { p: truth })
                        : t('search.truthRank', { p: truth, r: firstRank || t('search.truthNotRecalled') })
                    }
                  />
                )}
                <Chip size="small" label={t('search.top1Score', { s: result.hits[0]?.score?.toFixed(4) ?? '-' })} />
              </Stack>
            </Stack>
          )}
        </Panel>

        <Panel
          title={t('search.results')}
          subtitle={t('search.resultsSubtitle')}
          sx={{ flex: 1 }}
          bodySx={{ overflowY: 'auto', maxHeight: { lg: 'calc(100vh - 470px)' }, minHeight: 240 }}
        >
          {result?.hits?.length ? (
            <Stack spacing={1.25}>
              {result.hits.map((h, i) => {
                const isTruth = truth && h.person_id === truth
                return (
                  <Box
                    key={h.id + i}
                    sx={{
                      display: 'grid',
                      gridTemplateColumns: '44px 76px 1fr',
                      gap: 1.75,
                      alignItems: 'center',
                      p: 1,
                      borderRadius: 2.5,
                      border: '1px solid',
                      borderColor: isTruth ? 'success.main' : 'divider',
                      bgcolor: isTruth ? 'rgba(55,214,122,0.08)' : 'rgba(255,255,255,0.02)',
                    }}
                  >
                    <Typography
                      variant="h6"
                      sx={{ textAlign: 'center', fontFamily: 'ui-monospace, monospace', opacity: i === 0 ? 1 : 0.5 }}
                    >
                      {i + 1}
                    </Typography>
                    <Box className="tile" sx={{ height: 132, cursor: 'default' }}>
                      <img src={h.url} alt={h.id} loading="lazy" />
                    </Box>
                    <Box sx={{ minWidth: 0 }}>
                      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.5, flexWrap: 'wrap', gap: 0.5 }}>
                        <Typography variant="body2" sx={{ fontFamily: 'ui-monospace, monospace' }}>
                          person {h.person_id}
                        </Typography>
                        <Chip size="small" variant="outlined" label={`cam ${h.camera}`} sx={{ height: 20 }} />
                        <Chip size="small" variant="outlined" label={`frame ${h.frame}`} sx={{ height: 20 }} />
                        {isTruth && <Chip size="small" color="success" label={t('search.truth')} sx={{ height: 20 }} />}
                      </Stack>
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.75, wordBreak: 'break-all' }}>
                        {h.id}
                      </Typography>
                      <ScoreBar value={h.score} threshold={THRESHOLD} />
                    </Box>
                  </Box>
                )
              })}
            </Stack>
          ) : (
            !busy && (
              <Stack alignItems="center" spacing={1} sx={{ py: 5, opacity: 0.55 }}>
                <SearchIcon fontSize="large" />
                <Typography variant="body2">{t('search.empty')}</Typography>
              </Stack>
            )
          )}
        </Panel>
      </Stack>
    </Box>
  )
}
