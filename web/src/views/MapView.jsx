import { useEffect, useMemo, useRef, useState } from 'react'
import { Alert, Box, Chip, Divider, Stack, Table, TableBody, TableCell, TableHead, TableRow, Typography } from '@mui/material'
import { Panel } from '../ui.jsx'
import { useI18n } from '../i18n/I18nProvider.jsx'
import { DemoNotice, MetricCell, NotConnectedChip, PlaceholderPanel } from '../components.jsx'
import CAMERA_DB from '../config/cameras.json'

// ---------------------------------------------------------------------------
// 合规说明：本项目只允许使用白名单内的国内底图（腾讯地图 / 高德 / 百度 / 天地图），
// 坐标系为 GCJ-02。Google Maps / Apple Maps / Bing 海外 / OSM 直连 / Mapbox 一律不得使用。
// 这里用腾讯地图 GL JS，走官方 CDN + WorkBuddy 本地 key 代理（前端不出现明文 key）。
// ---------------------------------------------------------------------------

const SDK_SRC = 'https://map.qq.com/api/gljs?v=1.exp'

/** 动态加载腾讯地图 GL JS；已加载过就直接复用，避免重复注入 script。 */
let sdkPromise = null
function loadTMapSdk() {
  if (window.TMap) return Promise.resolve(window.TMap)
  if (sdkPromise) return sdkPromise

  sdkPromise = new Promise((resolve, reject) => {
    // key 代理：必须在 SDK script 之前设置，且不要额外调用 TMap.setConfig()
    window._TMapSecurityConfig = {
      serviceHost: 'http://127.0.0.1:__WB_HTTP_PORT__/_TMapService/_wbt/__WB_TMAP_SECRET__',
    }
    const s = document.createElement('script')
    s.src = SDK_SRC
    s.async = true
    s.onload = () => (window.TMap ? resolve(window.TMap) : reject(new Error('TMap SDK loaded but window.TMap is missing')))
    s.onerror = () => reject(new Error('TMap SDK failed to load'))
    document.head.appendChild(s)
  })
  return sdkPromise
}

const TONE = { A: '#4dabf7', B: '#a78bfa', C: '#37d67a' }

/** 生成内联 SVG 水滴图标，避免引用官方 demo 图片资源。 */
function dotIcon(color) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="26" height="34" viewBox="0 0 26 34">
    <path d="M13 0C5.8 0 0 5.8 0 13c0 9.7 13 21 13 21s13-11.3 13-21c0-7.2-5.8-13-13-13z" fill="${color}"/>
    <circle cx="13" cy="13" r="5.2" fill="#0a0e15"/>
  </svg>`
  return `data:image/svg+xml,${encodeURIComponent(svg)}`
}

const API_ROWS = [
  ['GET /api/cameras', 'apiList'],
  ['GET /api/cameras/{id}', 'apiDetail'],
  ['POST /api/cameras/ping', 'apiPing'],
  ['GET /api/map/track', 'apiTrack'],
]

export default function MapView() {
  const { t } = useI18n()
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const markerRef = useRef(null)
  const [sdkError, setSdkError] = useState('')
  const [ready, setReady] = useState(false)
  const [selected, setSelected] = useState(null)

  const { cameras, edge_nodes: edges, zones, center, zoom, demo_tracks: tracks } = CAMERA_DB
  const zoneName = useMemo(() => Object.fromEntries(zones.map((z) => [z.id, z.name])), [zones])
  const byId = useMemo(
    () => Object.fromEntries([...cameras, ...edges].map((d) => [d.id, d])),
    [cameras, edges],
  )

  // 初始化地图：只跑一次
  useEffect(() => {
    let cancelled = false
    loadTMapSdk()
      .then((TMap) => {
        if (cancelled || !containerRef.current || mapRef.current) return
        const map = new TMap.Map(containerRef.current, {
          center: new TMap.LatLng(center.lat, center.lng),
          zoom,
          pitch: 0,
          // 不传 mapStyleId：默认 key 不支持自定义样式，会导致底图变灰
        })
        mapRef.current = map

        // 摄像头图层
        markerRef.current = new TMap.MultiMarker({
          map,
          styles: {
            A: new TMap.MarkerStyle({ width: 26, height: 34, anchor: { x: 13, y: 34 }, src: dotIcon(TONE.A) }),
            B: new TMap.MarkerStyle({ width: 26, height: 34, anchor: { x: 13, y: 34 }, src: dotIcon(TONE.B) }),
            C: new TMap.MarkerStyle({ width: 26, height: 34, anchor: { x: 13, y: 34 }, src: dotIcon(TONE.C) }),
          },
          geometries: cameras.map((c) => ({
            id: c.id,
            styleId: c.zone,
            position: new TMap.LatLng(c.lat, c.lng),
            properties: { title: `${c.id} · ${c.name}` },
          })),
        })
        markerRef.current.on('click', (evt) => {
          const id = evt.geometry?.id
          if (id) setSelected(byId[id] ?? null)
        })

        // 边缘节点图层（圆形范围，与摄像头视觉区分）
        new TMap.MultiCircle({
          map,
          styles: {
            edge: new TMap.CircleStyle({
              color: 'rgba(167,139,250,0.16)',
              showBorder: true,
              borderColor: '#a78bfa',
              borderWidth: 2,
            }),
          },
          geometries: edges.map((e) => ({
            id: e.id,
            styleId: 'edge',
            center: new TMap.LatLng(e.lat, e.lng),
            radius: 480,
          })),
        })

        // 演示轨迹折线
        const linePoints = tracks[0].points.map((pid) => byId[pid]).filter(Boolean)
        if (linePoints.length > 1) {
          new TMap.MultiPolyline({
            map,
            styles: { track: new TMap.PolylineStyle({ color: '#f59e0b', width: 4, borderWidth: 1, borderColor: '#0a0e15', lineCap: 'round' }) },
            geometries: [{ id: 'track-1', styleId: 'track', paths: linePoints.map((p) => new TMap.LatLng(p.lat, p.lng)) }],
          })
        }

        setReady(true)
      })
      .catch((e) => setSdkError(String(e.message || e)))

    return () => { cancelled = true }
  }, [center.lat, center.lng, zoom, cameras, edges, tracks, byId])

  const offline = cameras.filter((c) => c.status === 'offline').length

  return (
    <Stack spacing={2.5}>
      <DemoNotice detail={t('map.demoDetail')} />

      <Panel
        title={t('map.title')}
        subtitle={t('map.subtitle', { district: CAMERA_DB.district, city: CAMERA_DB.city })}
        action={
          <Stack direction="row" spacing={1} alignItems="center">
            <Chip size="small" variant="outlined" label="Tencent Maps GL JS" sx={{ height: 22, opacity: 0.8 }} />
            <Chip size="small" variant="outlined" label="GCJ-02" sx={{ height: 22, opacity: 0.8 }} />
          </Stack>
        }
      >
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(4, 1fr)' }, gap: 2, mb: 2.5 }}>
          <MetricCell label={t('map.camerasRegistered')} value={cameras.length} />
          <MetricCell label={t('map.edgeRegistered')} value={edges.length} />
          <MetricCell label={t('map.offline')} value={offline} tone="warn" />
          <MetricCell label={t('map.coordinateSystem')} value={CAMERA_DB.coordinate_system} />
        </Box>

        <Divider sx={{ mb: 2 }} />

        {sdkError && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            {t('map.sdkError')}：{sdkError}
          </Alert>
        )}

        <Box
          ref={containerRef}
          sx={{
            position: 'relative',
            // 必须给固定高度，否则腾讯地图在 flex 容器里不渲染
            height: { xs: 340, md: 480 },
            borderRadius: 2.5,
            overflow: 'hidden',
            border: '1px solid',
            borderColor: 'divider',
          }}
        >
          {!ready && !sdkError && (
            <Stack alignItems="center" justifyContent="center" sx={{ position: 'absolute', inset: 0, bgcolor: 'rgba(10,14,21,0.55)', zIndex: 2 }}>
              <Typography variant="body2" color="text.secondary">{t('map.loadingBasemap')}</Typography>
            </Stack>
          )}
        </Box>

        <Stack direction="row" spacing={1.5} sx={{ mt: 2, flexWrap: 'wrap', gap: 1 }}>
          {zones.map((z) => (
            <Chip key={z.id} size="small" label={z.name} sx={{ bgcolor: `${z.color}22`, color: z.color, border: `1px solid ${z.color}55` }} />
          ))}
          <Chip size="small" label={t('map.edgeNode')} sx={{ bgcolor: 'rgba(167,139,250,0.14)', color: '#a78bfa' }} />
          <Chip size="small" label={t('map.demoTrack')} sx={{ bgcolor: 'rgba(245,158,11,0.16)', color: '#f59e0b' }} />
        </Stack>

        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 2 }}>
          {t('map.basemapNote')}
        </Typography>

        {selected && (
          <Alert severity="info" onClose={() => setSelected(null)} sx={{ mt: 2 }}>
            <Typography variant="body2" sx={{ fontFamily: 'ui-monospace, monospace' }}>{selected.id} · {selected.name}</Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
              {selected.road ? `${selected.road} · ` : ''}{t('map.zone')} {zoneName[selected.zone]} · lat {selected.lat}, lng {selected.lng}
            </Typography>
            {selected.model && (
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                {selected.model} · {selected.resolution} · {selected.mount}
              </Typography>
            )}
          </Alert>
        )}
      </Panel>

      <Panel title={t('map.ledgerTitle')} subtitle={t('map.ledgerSubtitle')}>
        <Box sx={{ overflowX: 'auto' }}>
          <Table size="small" sx={{ minWidth: 900 }}>
            <TableHead>
              <TableRow>
                <TableCell>ID</TableCell>
                <TableCell>{t('map.colName')}</TableCell>
                <TableCell>{t('map.colRoad')}</TableCell>
                <TableCell>{t('map.colZone')}</TableCell>
                <TableCell align="right">Lat</TableCell>
                <TableCell align="right">Lng</TableCell>
                <TableCell>{t('map.colMount')}</TableCell>
                <TableCell>{t('map.colEdge')}</TableCell>
                <TableCell>{t('common.notConnected')}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {cameras.map((c) => (
                <TableRow
                  key={c.id}
                  hover
                  onClick={() => setSelected(c)}
                  sx={{ cursor: 'pointer', bgcolor: selected?.id === c.id ? 'rgba(77,171,247,0.07)' : 'transparent' }}
                >
                  <TableCell sx={{ fontFamily: 'ui-monospace, monospace', fontSize: 12 }}>{c.id}</TableCell>
                  <TableCell><Typography variant="caption">{c.name}</Typography></TableCell>
                  <TableCell><Typography variant="caption" color="text.secondary">{c.road}</Typography></TableCell>
                  <TableCell>
                    <Chip size="small" label={c.zone} sx={{ height: 20, bgcolor: `${TONE[c.zone]}22`, color: TONE[c.zone], border: `1px solid ${TONE[c.zone]}55` }} />
                  </TableCell>
                  <TableCell align="right" sx={{ fontFamily: 'ui-monospace, monospace', fontSize: 11.5 }}>{c.lat}</TableCell>
                  <TableCell align="right" sx={{ fontFamily: 'ui-monospace, monospace', fontSize: 11.5 }}>{c.lng}</TableCell>
                  <TableCell><Typography variant="caption" color="text.secondary">{c.mount}</Typography></TableCell>
                  <TableCell><Typography variant="caption" color="text.secondary">{c.edge_node}</Typography></TableCell>
                  <TableCell><NotConnectedChip /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Box>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 2 }}>
          {t('map.ledgerSource')}
        </Typography>
      </Panel>

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '1fr 1fr' }, gap: 2.5 }}>
        <Panel title={t('map.apiTitle')} subtitle={t('map.apiSubtitle')}>
          <Stack spacing={1.5}>
            {API_ROWS.map(([path, key]) => (
              <Box key={path} sx={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 1.5, alignItems: 'start' }}>
                <Box>
                  <Typography variant="caption" sx={{ fontFamily: 'ui-monospace, monospace', color: 'primary.main' }}>{path}</Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>{t(`map.${key}`)}</Typography>
                </Box>
                <NotConnectedChip />
              </Box>
            ))}
          </Stack>
        </Panel>

        <PlaceholderPanel
          title={t('map.complianceTitle')}
          subtitle={t('map.complianceSubtitle')}
          note={t('map.complianceNote')}
        >
          <Stack spacing={0.75}>
            {['compliance1', 'compliance2', 'compliance3', 'compliance4'].map((k) => (
              <Typography key={k} variant="caption" color="text.secondary">· {t(`map.${k}`)}</Typography>
            ))}
          </Stack>
          <Divider sx={{ my: 1.5 }} />
          <Typography variant="caption" color="text.secondary">
            {t('map.complianceKeyNote')}
          </Typography>
        </PlaceholderPanel>
      </Box>

      <Panel title={t('map.trackTitle')} subtitle={t('map.trackSubtitle')}>
        <Box sx={{ overflowX: 'auto' }}>
          <Stack direction="row" spacing={1} alignItems="center" sx={{ minWidth: 640, py: 1 }}>
            {tracks[0].points.map((pid, i) => (
              <Stack key={pid} direction="row" spacing={1} alignItems="center">
                <Box sx={{ px: 1.25, py: 0.75, borderRadius: 2, border: '1px solid', borderColor: 'divider', textAlign: 'center' }}>
                  <Typography variant="caption" sx={{ fontFamily: 'ui-monospace, monospace', display: 'block' }}>{pid}</Typography>
                  <Typography variant="caption" color="text.disabled" sx={{ fontSize: 10 }}>— : —</Typography>
                </Box>
                {i < tracks[0].points.length - 1 && <Typography sx={{ opacity: 0.35 }}>→</Typography>}
              </Stack>
            ))}
          </Stack>
        </Box>
        <Typography variant="caption" color="text.secondary">{t('map.trackNote')}</Typography>
      </Panel>
    </Stack>
  )
}
