import { Button, Menu, MenuItem, Stack, Typography } from '@mui/material'
import { useState } from 'react'
import TranslateOutlinedIcon from '@mui/icons-material/TranslateOutlined'
import { useI18n } from './i18n/I18nProvider.jsx'
import { LOCALES, SUPPORTED } from './i18n/index.js'

/**
 * 语言切换：手动选过之后会写进 localStorage，下次打开沿用。
 * 只挂三个受支持语言（zh-TW / en-US / ja-JP）。
 */
export function LocaleMenu() {
  const { locale, setLocale, t } = useI18n()
  const [anchor, setAnchor] = useState(null)

  return (
    <>
      <Button
        size="small"
        variant="outlined"
        startIcon={<TranslateOutlinedIcon fontSize="small" />}
        onClick={(e) => setAnchor(e.currentTarget)}
        sx={{ flexShrink: 0 }}
      >
        {LOCALES[locale].short}
      </Button>
      <Menu anchorEl={anchor} open={Boolean(anchor)} onClose={() => setAnchor(null)}>
        <Typography variant="caption" color="text.secondary" sx={{ px: 2, py: 0.5, display: 'block' }}>
          {t('common.language')}
        </Typography>
        {SUPPORTED.map((code) => (
          <MenuItem
            key={code}
            selected={code === locale}
            onClick={() => {
              setLocale(code)
              setAnchor(null)
            }}
          >
            <Stack direction="row" spacing={1.5} alignItems="center" sx={{ minWidth: 160 }}>
              <Typography variant="body2" sx={{ flex: 1 }}>
                {LOCALES[code].label}
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'ui-monospace, monospace' }}>
                {code}
              </Typography>
            </Stack>
          </MenuItem>
        ))}
      </Menu>
    </>
  )
}
