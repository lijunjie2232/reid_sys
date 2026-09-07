import { useCallback, useEffect, useState } from 'react'
import {
  Alert, Box, Button, CircularProgress, Pagination, Stack, TextField, Typography,
} from '@mui/material'
import { api } from '../api.js'
import { Panel, PersonTile } from '../ui.jsx'
import { useI18n } from '../i18n/I18nProvider.jsx'

const PAGE = 60

export default function GalleryView({ status }) {
  const { t } = useI18n()
  const [page, setPage] = useState(1)
  const [q, setQ] = useState('')
  const [data, setData] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async (p, query) => {
    setBusy(true)
    try {
      setData(await api.gallery((p - 1) * PAGE, PAGE, query))
      setError('')
    } catch (e) {
      setError(String(e.message || e))
    } finally {
      setBusy(false)
    }
  }, [])

  useEffect(() => { load(page, q) }, [page, q, load])

  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE)) : 1

  return (
    <Stack spacing={2.5}>
      <Panel
        title={t('gallery.title')}
        subtitle={t('gallery.subtitleDs', {
          ds: status?.dataset_title || status?.dataset || '—',
          n: status?.gallery_total ?? 0,
        })}
        action={
          <Stack direction="row" spacing={1.5} alignItems="center">
            {busy && <CircularProgress size={16} />}
            <TextField
              size="small"
              placeholder={t('gallery.filterPlaceholder')}
              value={q}
              onChange={(e) => { setPage(1); setQ(e.target.value) }}
              sx={{ width: 220 }}
            />
            <Button size="small" variant="outlined" onClick={() => load(page, q)}>{t('common.refresh')}</Button>
          </Stack>
        }
      >
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1.5 }}>
          {t('gallery.hitCount', { n: data?.total ?? 0 })}
        </Typography>
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(92px, 1fr))',
            gap: 1,
          }}
        >
          {data?.items?.map((item) => (
            <PersonTile key={item.id} name={item.id} url={item.url} height={124} badge={item.person_id} />
          ))}
        </Box>
        <Stack alignItems="center" sx={{ mt: 2.5 }}>
          <Pagination count={pages} page={page} onChange={(_, v) => setPage(v)} color="primary" shape="rounded" />
        </Stack>
      </Panel>
    </Stack>
  )
}
