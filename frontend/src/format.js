export function fen(cents) {
  const sign = cents < 0 ? '-' : ''
  return `${sign}¥${(Math.abs(cents) / 100).toFixed(2)}`
}

export function fenWithCents(cents) {
  return `${fen(cents)} (${cents} 分)`
}

export function fmtTime(iso) {
  return iso ? iso.replace('T', ' ').slice(0, 16) : '-'
}

export const CHANNEL_COLORS = {
  '小红书': '#e24462',
  '朋友圈广告': '#07c160',
  '搜索引擎SEM': '#3b82f6',
  '直接访问': '#9ca3af',
  '未知来源': '#6b7280',
}

export function channelColor(channel) {
  return CHANNEL_COLORS[channel] || '#8b5cf6'
}
