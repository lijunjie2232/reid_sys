import { Alert, Box, Chip, Stack, Typography } from '@mui/material'
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined'
import { useI18n } from './i18n/I18nProvider.jsx'

/** 未接入服务的页面统一挂这个横幅（文案来自 i18n 的 common.demo）。 */
export function DemoNotice({ detail }) {
  const { t } = useI18n()
  return (
    <Alert
      severity="info"
      icon={<InfoOutlinedIcon fontSize="inherit" />}
      sx={{ border: '1px solid', borderColor: 'info.main', bgcolor: 'rgba(77,171,247,0.08)' }}
    >
      <Typography variant="body2" fontWeight={600}>
        {t('common.demo')}
      </Typography>
      {detail && (
        <Typography variant="caption" color="text.secondary">
          {detail}
        </Typography>
      )}
    </Alert>
  )
}

/** 表格里表示「该能力尚未接入」的灰色占位。 */
export function NotConnectedChip() {
  const { t } = useI18n()
  return <Chip size="small" variant="outlined" label={t('common.notConnected')} sx={{ height: 20, opacity: 0.6 }} />
}

/** 规划中的条目占位（比 NotConnectedChip 更偏「尚未接入、后续接入」）。 */
export function PlannedChip() {
  const { t } = useI18n()
  return <Chip size="small" variant="outlined" label={t('common.planned')} sx={{ height: 20, opacity: 0.6 }} />
}

/**
 * 未接入面板：形状像真的监控面板，但所有数值都是「—」，
 * 并且顶端挂 demo 提示。避免别人误以为这是真实数据。
 */
export function PlaceholderPanel({ title, subtitle, note, children, ...rest }) {
  return (
    <Box
      sx={{
        border: '1px dashed',
        borderColor: 'divider',
        borderRadius: 3,
        p: 2,
        bgcolor: 'rgba(255,255,255,0.015)',
      }}
    >
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 0.5 }}>
        <Typography variant="subtitle2">{title}</Typography>
        <Chip size="small" variant="outlined" label="demo" sx={{ height: 18, fontSize: 10, opacity: 0.7 }} />
      </Stack>
      {subtitle && (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1.5 }}>
          {subtitle}
        </Typography>
      )}
      {children}
      {note && (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1.5, opacity: 0.75 }}>
          {note}
        </Typography>
      )}
    </Box>
  )
}

/** 指标格：value 传 null/undefined 时显示破折号，用于未接入的指标。 */
export function MetricCell({ label, value, tone = 'default' }) {
  const color = { default: 'text.primary', muted: 'text.secondary', success: 'success.main', warn: 'warning.main' }[tone]
  return (
    <Box sx={{ px: 1.5, py: 1.25, borderRadius: 2, bgcolor: 'rgba(255,255,255,0.03)', border: '1px solid', borderColor: 'divider' }}>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
        {label}
      </Typography>
      <Typography variant="h6" sx={{ fontFamily: 'ui-monospace, monospace', color, lineHeight: 1.3 }}>
        {value ?? '—'}
      </Typography>
    </Box>
  )
}
