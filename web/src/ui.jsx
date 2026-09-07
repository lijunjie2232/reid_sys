import { Box, Chip, LinearProgress, Paper, Stack, Typography } from '@mui/material'
export function Panel({ title, subtitle, action, children, sx, bodySx }) {
  return (
    <Paper
      sx={{
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 3,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        ...sx,
      }}
    >
      {(title || action) && (
        <Stack
          direction="row"
          alignItems="center"
          justifyContent="space-between"
          sx={{ px: 2, py: 1.5, borderBottom: '1px solid', borderColor: 'divider' }}
        >
          <Box>
            <Typography variant="subtitle1" fontWeight={650}>
              {title}
            </Typography>
            {subtitle && (
              <Typography variant="caption" color="text.secondary">
                {subtitle}
              </Typography>
            )}
          </Box>
          {action}
        </Stack>
      )}
      <Box sx={{ p: 2, flex: 1, minHeight: 0, ...bodySx }}>{children}</Box>
    </Paper>
  )
}

export function StatChip({ label, value, tone = 'default' }) {
  const color = { default: 'default', primary: 'primary', success: 'success', secondary: 'secondary' }[tone]
  return (
    <Chip
      size="small"
      color={color}
      variant="outlined"
      label={
        <Box component="span">
          <Box component="span" sx={{ opacity: 0.65, mr: 0.75 }}>
            {label}
          </Box>
          <Box component="span" sx={{ fontFamily: 'ui-monospace, monospace', fontWeight: 700 }}>
            {value}
          </Box>
        </Box>
      }
      sx={{
        borderColor: 'divider',
        bgcolor: tone === 'default' ? 'rgba(255,255,255,0.03)' : 'rgba(77,171,247,0.10)',
      }}
    />
  )
}

export function Metric({ label, value, hint }) {
  return (
    <Box sx={{ px: 2, py: 1.5, borderRadius: 2.5, bgcolor: 'rgba(255,255,255,0.03)', border: '1px solid', borderColor: 'divider' }}>
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
      <Typography variant="h5" sx={{ fontFamily: 'ui-monospace, monospace', lineHeight: 1.35 }}>
        {value}
      </Typography>
      {hint && (
        <Typography variant="caption" color="text.secondary">
          {hint}
        </Typography>
      )}
    </Box>
  )
}

/**
 * 置信度进度条。
 *
 * 普通进度条从 0% 起算，但 Re-ID 的 cosine 分数全挤在 0.95~0.99 这一小段，
 * 从 0 起算的话每一条都是「几乎满格」，看不出差别。
 * 所以这里按 [threshold, 1] 做线性映射：低于阈值 = 0%，1.0 = 100%，
 * 让高分区间的差异被拉开。左侧标注阈值，右边是换算后的相对百分比。
 *
 * 颜色按「相对百分比」分三档：>=66% 绿、>=33% 黄、其余红。
 */
export function ScoreBar({ value, label, threshold = 0.95, showRaw = true }) {
  const raw = Math.max(0, Math.min(1, value ?? 0))
  const lo = Math.max(0, Math.min(0.999, threshold))
  // 映射到 [0,1]；低于阈值时钳到 0（不显示负进度）
  const rel = raw <= lo ? 0 : (raw - lo) / (1 - lo)
  const relPct = Math.round(rel * 100)

  const { color, text } = rel >= 0.66
    ? { color: '#37d67a', text: '#37d67a' }
    : rel >= 0.33
      ? { color: '#f59e0b', text: '#f59e0b' }
      : { color: '#f4645f', text: '#f4645f' }

  return (
    <Box sx={{ width: '100%' }}>
      <Stack direction="row" alignItems="center" spacing={1}>
        <Typography
          variant="caption"
          sx={{ fontFamily: 'ui-monospace, monospace', opacity: 0.55, flexShrink: 0, minWidth: 46 }}
        >
          {lo.toFixed(2)}
        </Typography>
        <LinearProgress
          variant="determinate"
          value={relPct}
          sx={{
            flex: 1,
            height: 6,
            borderRadius: 3,
            bgcolor: 'rgba(255,255,255,0.07)',
            '& .MuiLinearProgress-bar': { borderRadius: 3, backgroundColor: color, transition: 'none' },
          }}
        />
        <Typography
          variant="caption"
          sx={{ fontFamily: 'ui-monospace, monospace', color: text, flexShrink: 0, minWidth: 34, textAlign: 'right' }}
        >
          {relPct}%
        </Typography>
      </Stack>
      <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'ui-monospace, monospace' }}>
        {label ?? `cosine ${raw.toFixed(4)}`}
        {showRaw && label ? ` · cosine ${raw.toFixed(4)}` : ''}
      </Typography>
    </Box>
  )
}

export function PersonTile({ name, url, active, onClick, height = 96, badge }) {
  return (
    <Box className={`tile${active ? ' active' : ''}`} onClick={onClick} sx={{ height, position: 'relative' }}>
      <img src={url} alt={name} loading="lazy" />
      {badge != null && (
        <Box
          sx={{
            position: 'absolute',
            top: 4,
            left: 4,
            px: 0.75,
            borderRadius: 1.5,
            bgcolor: 'rgba(10,14,21,0.82)',
            fontSize: 11,
            fontFamily: 'ui-monospace, monospace',
          }}
        >
          {badge}
        </Box>
      )}
    </Box>
  )
}
