import { Box, Chip, Divider, Stack, Typography } from '@mui/material'
import MemoryIcon from '@mui/icons-material/Memory'
import StorageIcon from '@mui/icons-material/Storage'
import CloudQueueIcon from '@mui/icons-material/CloudQueue'
import HubIcon from '@mui/icons-material/Hub'
import DevicesIcon from '@mui/icons-material/Devices'
import AccountTreeIcon from '@mui/icons-material/AccountTree'
import { Metric, Panel } from '../ui.jsx'
import { useI18n } from '../i18n/I18nProvider.jsx'
import { DemoNotice } from '../components.jsx'

// 全部取自 docs/SYSTEM.md，用固定中文术语 + 可翻的标题
// 数值取自 docs/SYSTEM.md；label / unit / detail 由 i18n 提供
const SPECS = [
  { k: 'ipc', value: '10,000' },
  { k: 'edge', value: '33' },
  { k: 'cloud', value: '24' },
  { k: 'qps', value: '15,000' },
  { k: 'bw', value: '1.8' },
  { k: 'cost', value: '392.2' },
]

const TIERS = [
  {
    icon: <MemoryIcon fontSize="small" />,
    tone: '#4dabf7',
    titleKey: 'system.tierEnd',
    module: 'reid_sys/detect.py',
    icon2: <DevicesIcon fontSize="small" />,
    points: ['tierEnd1', 'tierEnd2', 'tierEnd3', 'tierEnd4'],
  },
  {
    icon: <StorageIcon fontSize="small" />,
    tone: '#a78bfa',
    titleKey: 'system.tierEdge',
    module: 'backbone',
    icon2: <HubIcon fontSize="small" />,
    points: ['tierEdge1', 'tierEdge2', 'tierEdge3', 'tierEdge4'],
  },
  {
    icon: <CloudQueueIcon fontSize="small" />,
    tone: '#37d67a',
    titleKey: 'system.tierCloud',
    module: 'reid_sys/store.py',
    icon2: <AccountTreeIcon fontSize="small" />,
    points: ['tierCloud1', 'tierCloud2', 'tierCloud3', 'tierCloud4'],
  },
]

function Section({ title, children, dense }) {
  return (
    <Panel title={title} bodySx={dense ? { p: 2 } : undefined}>
      {children}
    </Panel>
  )
}

/** Two-column key/value list (keys are i18n keys, resolved via t). */
function Rows({ items, t }) {
  return (
    <Stack spacing={1.25}>
      {items.map(([k, v]) => (
        <Box key={k} sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '190px 1fr' }, gap: 1.5 }}>
          <Typography variant="caption" color="text.secondary">{t(`architecture.${k}`)}</Typography>
          <Typography variant="body2">{t(`architecture.${v}`)}</Typography>
        </Box>
      ))}
    </Stack>
  )
}

export default function ArchitectureView() {
  const { t } = useI18n()

  return (
    <Stack spacing={2.5}>
      <DemoNotice detail={t('architecture.demoDetail')} />

      <Panel title={t('system.tiers')} subtitle={t('system.tiersSubtitle')}>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'repeat(3, 1fr)' }, gap: 2 }}>
          {TIERS.map((tier, i) => (
            <Box key={tier.titleKey} sx={{ position: 'relative', p: 2, borderRadius: 3, border: '1px solid', borderColor: 'divider', bgcolor: 'rgba(255,255,255,0.02)' }}>
              <Stack direction="row" spacing={1} alignItems="center" sx={{ color: tier.tone, mb: 1 }}>
                {tier.icon}
                <Typography variant="subtitle2" sx={{ color: 'text.primary' }}>{t(tier.titleKey)}</Typography>
              </Stack>
              <Chip size="small" variant="outlined" label={tier.module} sx={{ mb: 1.5, fontFamily: 'ui-monospace, monospace', borderColor: `${tier.tone}55`, color: tier.tone }} />
              <Stack spacing={0.75}>
                {tier.points.map((key) => (
                  <Stack key={key} direction="row" spacing={1} alignItems="flex-start">
                    <Box sx={{ width: 5, height: 5, borderRadius: '50%', bgcolor: tier.tone, flexShrink: 0, mt: 0.75 }} />
                    <Typography variant="caption" color="text.secondary">{t(`architecture.${key}`)}</Typography>
                  </Stack>
                ))}
              </Stack>
              {i < TIERS.length - 1 && (
                <Typography sx={{ position: 'absolute', right: -14, top: '50%', transform: 'translateY(-50%)', display: { xs: 'none', md: 'block' }, opacity: 0.4 }}>→</Typography>
              )}
            </Box>
          ))}
        </Box>
        <Divider sx={{ my: 2.5 }} />
        <Typography variant="caption" color="text.secondary">{t('system.tiersFootnote')}</Typography>
      </Panel>

      <Panel title={t('architecture.scaleTitle')} subtitle={t('architecture.scaleSubtitle')}>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(3, 1fr)' }, gap: 2 }}>
          {SPECS.map((s) => (
            <Metric key={s.k} label={t(`architecture.spec_${s.k}_label`)} value={`${s.value} ${t(`architecture.spec_${s.k}_unit`)}`} hint={t(`architecture.spec_${s.k}_detail`)} />
          ))}
        </Box>
      </Panel>

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '1fr 1fr' }, gap: 2.5 }}>
        <Section title={t('architecture.dualDcTitle')}>
          <Rows t={t}
            items={[
              ['dcComputeRole', 'dcComputeRoleV'],
              ['dcBusinessRole', 'dcBusinessRoleV'],
              ['dcComputeData', 'dcComputeDataV'],
              ['dcBusinessData', 'dcBusinessDataV'],
              ['dcComputeNet', 'dcComputeNetV'],
              ['dcBusinessNet', 'dcBusinessNetV'],
            ]}
          />
        </Section>

        <Section title={t('architecture.scheduleTitle')}>
          <Stack spacing={1.5}>
            {['sched1', 'sched2', 'sched3', 'sched4'].map((key) => (
              <Box key={key} sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '130px 1fr' }, gap: 1.5 }}>
                <Typography variant="caption" sx={{ fontFamily: 'ui-monospace, monospace', color: 'primary.main' }}>{t(`architecture.${key}_time`)}</Typography>
                <Typography variant="caption" color="text.secondary">{t(`architecture.${key}_desc`)}</Typography>
              </Box>
            ))}
          </Stack>
        </Section>
      </Box>

      <Panel title={t('architecture.rackTitle')} subtitle={t('architecture.rackSubtitle')}>
        <Stack direction="row" spacing={1} sx={{ mb: 2, flexWrap: 'wrap', gap: 1 }}>
          <Chip size="small" label={t('architecture.rackA')} sx={{ bgcolor: 'rgba(77,171,247,0.14)' }} />
          <Chip size="small" label={t('architecture.rackB')} sx={{ bgcolor: 'rgba(55,214,122,0.14)' }} />
          <Chip size="small" label={t('architecture.rackC')} sx={{ bgcolor: 'rgba(167,139,250,0.14)' }} />
        </Stack>
        <Box sx={{ overflowX: 'auto' }}>
          <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(8, minmax(96px, 1fr))', gap: 1, minWidth: 820 }}>
            {['Rack 01', 'Rack 02', 'Rack 03', 'Rack 04', 'Rack 05', 'Rack 06', 'Rack 07', 'Rack 08'].map((rack, i) => {
              const slots = i < 4
                ? [[t('architecture.rackCtrl'), '#a78bfa'], [`${t('architecture.rackGpu')}-${i + 1}`, '#4dabf7'], [`${t('architecture.rackStore')}-${i + 1}`, '#37d67a'], [t('architecture.rackReserved'), null]]
                : [[`${t('architecture.rackGpu')}-${i * 2 - 3}`, '#4dabf7'], [`${t('architecture.rackGpu')}-${i * 2 - 2}`, '#4dabf7'], [`${t('architecture.rackStore')}-${i + 1}`, '#37d67a'], [t('architecture.rackReserved'), null]]
              return (
                <Box key={rack}>
                  <Typography variant="caption" sx={{ fontFamily: 'ui-monospace, monospace', display: 'block', mb: 0.5 }}>{rack}</Typography>
                  <Stack spacing={0.5}>
                    {slots.map(([label, tone], j) => (
                      <Box key={j} sx={{ px: 0.75, py: 0.6, borderRadius: 1.5, border: '1px solid', borderColor: tone ? `${tone}55` : 'divider', bgcolor: tone ? `${tone}18` : 'transparent', color: tone || 'text.disabled', fontSize: 10.5, textAlign: 'center', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {label}
                      </Box>
                    ))}
                  </Stack>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5, fontSize: 10 }}>
                    {i < 4 ? '~2.2 kW' : '~2.5 kW'}
                  </Typography>
                </Box>
              )
            })}
          </Box>
        </Box>
      </Panel>

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '1fr 1fr' }, gap: 2.5 }}>
        <Section title={t('architecture.mambaTitle')}>
          <Typography variant="body2" sx={{ fontFamily: 'ui-monospace, monospace', p: 1.5, borderRadius: 2, bgcolor: 'rgba(255,255,255,0.03)', mb: 2 }}>
            S_final = S_visual × σ(W · S_mamba + b)
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 2 }}>
            {t('architecture.mambaExplain')}
          </Typography>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>{t('architecture.coldStartTitle')}</Typography>
          <Rows t={t}
            items={[
              ['coldGeomMask', 'coldGeomMaskV'],
              ['coldRoadPath', 'coldRoadPathV'],
              ['coldGeoEmbed', 'coldGeoEmbedV'],
            ]}
          />
        </Section>

        <Section title={t('architecture.watchlistTitle')}>
          <Rows t={t}
            items={[
              ['wlBroadcast', 'wlBroadcastV'],
              ['wlGemm', 'wlGemmV'],
              ['wlEdge', 'wlEdgeV'],
              ['wlDebounce', 'wlDebounceV'],
              ['wlLatency', 'wlLatencyV'],
            ]}
          />
        </Section>
      </Box>

      <Section title={t('architecture.gatewayTitle')}>
        <Rows t={t}
          items={[
            ['gwSceneA', 'gwSceneAV'],
            ['gwSceneB', 'gwSceneBV'],
            ['gwSceneC', 'gwSceneCV'],
          ]}
        />
        <Divider sx={{ my: 2 }} />
        <Typography variant="caption" color="text.secondary">
          {t('architecture.gatewayFootnote')}
        </Typography>
      </Section>

      <Section title={t('architecture.opsTitle')}>
        <Rows t={t}
          items={[
            ['opsBuffer', 'opsBufferV'],
            ['opsHa', 'opsHaV'],
            ['opsOta', 'opsOtaV'],
          ]}
        />
      </Section>
    </Stack>
  )
}
