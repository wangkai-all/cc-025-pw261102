import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { channelColor, fen, fmtTime } from '../format'

function fmtMap(map) {
  const entries = Object.entries(map).filter(([, v]) => v !== 0)
  if (entries.length === 0) return '—'
  return entries.map(([ch, v]) => `${ch} ${fen(v)}`).join(' + ')
}

export default function CompareView({ days, models, version }) {
  const [data, setData] = useState(null)
  const [modelA, setModelA] = useState('first_touch')
  const [modelB, setModelB] = useState('linear')

  useEffect(() => {
    api.compare(days).then(setData).catch(() => setData(null))
  }, [days, version])

  const diffs = useMemo(() => {
    if (!data) return []
    return data.orders
      .map((o) => {
        const a = o.by_model[modelA] || {}
        const b = o.by_model[modelB] || {}
        const channels = new Set([...Object.keys(a), ...Object.keys(b)])
        const changed = [...channels].some((ch) => (a[ch] || 0) !== (b[ch] || 0))
        return changed ? { ...o, a, b } : null
      })
      .filter(Boolean)
  }, [data, modelA, modelB])

  const channelDelta = useMemo(() => {
    const acc = {}
    for (const d of diffs) {
      for (const ch of new Set([...Object.keys(d.a), ...Object.keys(d.b)])) {
        acc[ch] = (acc[ch] || 0) + (d.b[ch] || 0) - (d.a[ch] || 0)
      }
    }
    return acc
  }, [diffs])

  if (!data) return <p className="loading">加载中…</p>
  const label = (k) => models.find((m) => m.key === k)?.label || k

  return (
    <div>
      <div className="compare-controls">
        <label>
          口径 A
          <select value={modelA} onChange={(e) => setModelA(e.target.value)}>
            {models.map((m) => <option key={m.key} value={m.key}>{m.label}</option>)}
          </select>
        </label>
        <span className="arrow">→</span>
        <label>
          口径 B
          <select value={modelB} onChange={(e) => setModelB(e.target.value)}>
            {models.map((m) => <option key={m.key} value={m.key}>{m.label}</option>)}
          </select>
        </label>
        <span className="hint">{diffs.length} 笔成交的渠道分摊发生变化</span>
      </div>

      {Object.keys(channelDelta).length > 0 && (
        <p className="delta-line">
          渠道金额变化(B − A):
          {Object.entries(channelDelta).map(([ch, d]) => (
            <span key={ch} className="chip" style={{ borderColor: channelColor(ch) }}>
              {ch} {d >= 0 ? '+' : ''}{fen(d)}
            </span>
          ))}
        </p>
      )}

      <table className="tbl">
        <thead>
          <tr>
            <th>订单</th>
            <th>成交时间</th>
            <th className="num">净额</th>
            <th>{label(modelA)}</th>
            <th>{label(modelB)}</th>
          </tr>
        </thead>
        <tbody>
          {diffs.length === 0 && (
            <tr><td colSpan="5" className="hint">两种口径下所有成交的分摊完全一致</td></tr>
          )}
          {diffs.map((d) => (
            <tr key={d.order_id}>
              <td>{d.order_id}</td>
              <td>{fmtTime(d.ts)}</td>
              <td className="num">{fen(d.net_cents)}</td>
              <td>{fmtMap(d.a)}</td>
              <td className="changed">{fmtMap(d.b)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
