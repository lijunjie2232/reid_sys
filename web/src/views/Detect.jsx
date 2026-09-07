import { useRef, useState } from 'react'
import {
  Alert, Box, Button, Chip, CircularProgress, Divider, Slider, Stack, Typography,
} from '@mui/material'
import UploadFileIcon from '@mui/icons-material/UploadFile'
import PlayCircleOutlineIcon from '@mui/icons-material/PlayCircleOutline'
import { api } from '../api.js'
import { Metric, Panel, ScoreBar } from '../ui.jsx'
import { useI18n } from '../i18n/I18nProvider.jsx'

const THRESHOLD = 0.95

const REASON_COLOR = { enter: '#4dabf7', interval: '#a78bfa', exit: '#f59e0b' }

function dataUrlToFile(dataUrl, name) {
  const [meta, b64] = dataUrl.split(',')
  const mime = meta.match(/data:(.*?);/)[1]
  const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0))
  return new File([bytes], name, { type: mime })
}

export default function DetectView() {
  const { t } = useI18n()
  const [img, setImg] = useState(null)
  const [det, setDet] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const [persons, setPersons] = useState(3)
  const [frames, setFrames] = useState(90)
  const [interval, setInterval] = useState(30)
  const [track, setTrack] = useState(null)
  const [trackBusy, setTrackBusy] = useState(false)

  const [search, setSearch] = useState(null)
  const fileRef = useRef(null)

  const onUpload = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setBusy(true); setError(''); setDet(null); setSearch(null)
    try {
      const data = await api.detect(file)
      setImg(data.image)
      setDet(data)
    } catch (err) {
      setError(String(err.message || err))
    } finally {
      setBusy(false)
    }
  }

  const runTrack = async () => {
    setTrackBusy(true); setError('')
    try {
      setTrack(await api.trackDemo(persons, frames, interval))
    } catch (err) {
      setError(String(err.message || err))
    } finally {
      setTrackBusy(false)
    }
  }

  const searchCrop = async (crop, i) => {
    try {
      const data = await api.searchUpload(dataUrlToFile(crop, `crop_${i}.jpg`), 6)
      setSearch({ index: i, ...data })
    } catch (err) {
      setError(String(err.message || err))
    }
  }

  const byTrack = track
    ? Object.values(
        track.timeline.reduce((acc, e) => {
          ;(acc[e.track_id] ||= { id: e.track_id, marks: {} }).marks[e.frame] = e.reason
          return acc
        }, {}),
      )
    : []

  return (
    <Stack spacing={2.5}>
      {error && <Alert severity="error">{error}</Alert>}

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '1.15fr 1fr' }, gap: 2.5 }}>
        <Panel
          title={t('detect.singleTitle')}
          subtitle={t('detect.singleSubtitle')}
          action={
            <>
              <input ref={fileRef} type="file" accept="image/*" hidden onChange={onUpload} />
              <Button size="small" variant="contained" startIcon={<UploadFileIcon />} onClick={() => fileRef.current?.click()}>
                {t('detect.uploadImage')}
              </Button>
            </>
          }
        >
          {busy && <Stack direction="row" spacing={1.5} alignItems="center"><CircularProgress size={18} /><Typography variant="body2">{t('detect.detecting')}</Typography></Stack>}
          {!img && !busy && (
            <Typography variant="body2" color="text.secondary">
              {t('detect.uploadHint')}
            </Typography>
          )}
          {img && !busy && (
            <>
              <Box sx={{ position: 'relative', borderRadius: 2, overflow: 'hidden', border: '1px solid', borderColor: 'divider' }}>
                <img src={img} alt="detect" style={{ display: 'block', width: '100%' }} />
                {det.persons.map((p, i) => (
                  <Box
                    key={i}
                    sx={{
                      position: 'absolute',
                      left: `${(p.box[0] / det.width) * 100}%`,
                      top: `${(p.box[1] / det.height) * 100}%`,
                      width: `${((p.box[2] - p.box[0]) / det.width) * 100}%`,
                      height: `${((p.box[3] - p.box[1]) / det.height) * 100}%`,
                      border: '2px solid #4dabf7',
                      borderRadius: '4px',
                      boxShadow: '0 0 0 1px rgba(0,0,0,0.45) inset',
                    }}
                  >
                    <Box sx={{ position: 'absolute', top: -20, left: -2, px: 0.75, bgcolor: '#4dabf7', color: '#08111f', fontSize: 11, fontWeight: 700, borderRadius: '4px 4px 0 0', fontFamily: 'ui-monospace, monospace' }}>
                      #{i + 1} {p.score.toFixed(2)}
                    </Box>
                  </Box>
                ))}
              </Box>
              <Stack direction="row" spacing={1} sx={{ mt: 1.5, flexWrap: 'wrap', gap: 1 }}>
                <Chip size="small" label={`${t('detect.cropTitle')}: ${det.count}`} color="primary" />
                <Chip size="small" label={`${det.width}×${det.height}`} variant="outlined" />
              </Stack>
            </>
          )}
        </Panel>

        <Panel title={t('detect.cropTitle')} subtitle={t('detect.cropSubtitle')}>
          {!det?.persons?.length && <Typography variant="body2" color="text.secondary">{t('detect.noCrop')}</Typography>}
          {det?.persons?.length > 0 && (
            <Stack spacing={1.25} sx={{ maxHeight: 420, overflowY: 'auto' }}>
              {det.persons.map((p, i) => (
                <Box key={i} sx={{ display: 'grid', gridTemplateColumns: '64px 1fr auto', gap: 1.5, alignItems: 'center' }}>
                  <Box className="tile" sx={{ height: 112, cursor: 'default' }}>
                    <img src={p.crop} alt={`crop-${i}`} />
                  </Box>
                  <Box>
                    <Typography variant="body2" sx={{ fontFamily: 'ui-monospace, monospace' }}>
                      box {p.box.join(', ')}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">score {p.score.toFixed(4)}</Typography>
                  </Box>
                  <Button size="small" variant="outlined" onClick={() => searchCrop(p.crop, i)}>{t('detect.searchPerson')}</Button>
                </Box>
              ))}
            </Stack>
          )}
          {search && (
            <>
              <Divider sx={{ my: 2 }} />
              <Typography variant="subtitle2" sx={{ mb: 1 }}>{t('detect.cropSearchTitle', { n: search.index + 1 })}</Typography>
              <Stack direction="row" spacing={1} sx={{ overflowX: 'auto', pb: 1 }}>
                {search.hits.map((h, i) => (
                  <Box key={h.id} sx={{ width: 78, flexShrink: 0 }}>
                    <Box className="tile" sx={{ height: 108, cursor: 'default' }}>
                      <img src={h.url} alt={h.id} loading="lazy" />
                    </Box>
                    <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'ui-monospace, monospace' }}>
                      #{i + 1} {h.score.toFixed(3)}
                    </Typography>
                    <ScoreBar value={h.score} label={`p${h.person_id}`} threshold={THRESHOLD} />
                  </Box>
                ))}
              </Stack>
            </>
          )}
        </Panel>
      </Box>

      <Panel
        title={t('detect.trackTitle')}
        subtitle={t('detect.trackSubtitle')}
        action={
          <Button size="small" variant="contained" startIcon={<PlayCircleOutlineIcon />} onClick={runTrack} disabled={trackBusy}>
            {trackBusy ? t('detect.running') : t('detect.runDemo')}
          </Button>
        }
      >
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'repeat(3, 1fr)' }, gap: 2.5, mb: 2.5 }}>
          {[
            { label: t('detect.persons'), value: persons, set: setPersons, min: 1, max: 6 },
            { label: t('detect.frames'), value: frames, set: setFrames, min: 30, max: 300, step: 30 },
            { label: t('detect.interval'), value: interval, set: setInterval, min: 5, max: 120, step: 5 },
          ].map((s) => (
            <Box key={s.label}>
              <Stack direction="row" justifyContent="space-between">
                <Typography variant="caption" color="text.secondary">{s.label}</Typography>
                <Typography variant="caption" sx={{ fontFamily: 'ui-monospace, monospace' }}>{s.value}</Typography>
              </Stack>
              <Slider size="small" min={s.min} max={s.max} step={s.step || 1} value={s.value} onChange={(_, v) => s.set(v)} />
            </Box>
          ))}
        </Box>

        {trackBusy && <Stack direction="row" spacing={1.5} alignItems="center"><CircularProgress size={18} /><Typography variant="body2">{t('detect.trackRunning')}</Typography></Stack>}

        {track && !trackBusy && (
          <>
            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(4, 1fr)' }, gap: 2, mb: 2.5 }}>
              <Metric label={t('detect.statDetections')} value={track.stats.detections} hint={t('detect.statDetectionsHint', { n: track.stats.frames })} />
              <Metric label={t('detect.statEmits')} value={track.stats.emits} hint={`enter ${track.stats.by_reason.enter} / interval ${track.stats.by_reason.interval} / exit ${track.stats.by_reason.exit}`} />
              <Metric label={t('detect.statDedup')} value={`${(track.stats.dedup_rate * 100).toFixed(1)}%`} hint={t('detect.statDedupHint')} />
              <Metric label={t('detect.statTracks')} value={byTrack.length} hint={t('detect.statTracksHint')} />
            </Box>

            <Typography variant="subtitle2" sx={{ mb: 1 }}>{t('detect.timeline')}</Typography>
            <Stack spacing={1} sx={{ mb: 2.5 }}>
              {byTrack.map((t) => (
                <Stack key={t.id} direction="row" spacing={1.5} alignItems="center">
                  <Typography variant="caption" sx={{ width: 74, fontFamily: 'ui-monospace, monospace' }}>track {t.id}</Typography>
                  <Box sx={{ flex: 1, display: 'flex', gap: '2px', height: 16, alignItems: 'center' }}>
                    {Array.from({ length: track.stats.frames }, (_, f) => (
                      <Box
                        key={f}
                        title={t.marks[f] ? `frame ${f} · ${t.marks[f]}` : `frame ${f}`}
                        sx={{
                          flex: 1,
                          height: t.marks[f] ? 16 : 4,
                          borderRadius: 1,
                          bgcolor: t.marks[f] ? REASON_COLOR[t.marks[f]] : 'rgba(255,255,255,0.10)',
                        }}
                      />
                    ))}
                  </Box>
                </Stack>
              ))}
            </Stack>

            <Stack direction="row" spacing={1} sx={{ mb: 1.5 }}>
              {Object.entries(REASON_COLOR).map(([k, c]) => (
                <Chip key={k} size="small" label={{ enter: t('detect.legendEnter'), interval: t('detect.legendInterval'), exit: t('detect.legendExit') }[k]} sx={{ bgcolor: `${c}22`, color: c, border: `1px solid ${c}66` }} />
              ))}
            </Stack>

            <Typography variant="subtitle2" sx={{ mb: 1 }}>{t('detect.emitSamples')}</Typography>
            <Stack direction="row" spacing={1.25} sx={{ overflowX: 'auto', pb: 1 }}>
              {track.samples.map((s, i) => (
                <Box key={i} sx={{ width: 68, flexShrink: 0 }}>
                  <Box className="tile" sx={{ height: 112, cursor: 'default' }}>
                    <img src={s.crop} alt={`emit-${i}`} loading="lazy" />
                  </Box>
                  <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'ui-monospace, monospace' }}>
                    f{s.frame} {s.reason}
                  </Typography>
                </Box>
              ))}
            </Stack>
          </>
        )}
      </Panel>
    </Stack>
  )
}
