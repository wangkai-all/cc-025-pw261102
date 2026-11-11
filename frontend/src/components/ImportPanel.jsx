import { useState } from 'react'
import { api } from '../api'

const EXAMPLES = {
  touchpoints: [
    { touchpoint_id: 101, anon_id: 'AX', channel: '抖音广告', is_direct: false, ts: '2026-11-09T10:00:00' },
  ],
  identity_bindings: [
    { anon_id: 'AX', user_id: 'UX', bound_at: '2026-11-09T11:00:00' },
  ],
  conversions: [
    { order_id: 'OX', user_id: 'UX', gross_cents: 9900, ts: '2026-11-10T12:00:00', reversed: false },
  ],
  refunds: [
    { refund_id: 'RX1', order_id: 'OX', amount_cents: 1000, ts: '2026-11-11T09:00:00' },
  ],
}

const LABELS = {
  touchpoints: '触点',
  identity_bindings: '身份绑定',
  conversions: '成交',
  refunds: '退款',
}

export default function ImportPanel({ onDone, onError }) {
  const [texts, setTexts] = useState(() =>
    Object.fromEntries(Object.entries(EXAMPLES).map(([k, v]) => [k, JSON.stringify(v, null, 2)]))
  )
  const [msg, setMsg] = useState('')

  async function submit(entity) {
    try {
      const rows = JSON.parse(texts[entity])
      const res = await api.importData(entity, rows)
      setMsg(`${LABELS[entity]}导入 ${res.imported} 条(重复主键自动覆盖,不累加)`)
      onDone()
    } catch (e) {
      onError(`${LABELS[entity]}导入失败: ${e.message}`)
    }
  }

  return (
    <div className="import-panel">
      <p className="hint">
        粘贴 JSON 数组导入。同一主键重复导入会覆盖而非累加;成交的 reversed=true 表示撤销。
      </p>
      <div className="import-grid">
        {Object.keys(EXAMPLES).map((entity) => (
          <div key={entity} className="import-box">
            <div className="import-head">
              <b>{LABELS[entity]}</b>
              <button onClick={() => submit(entity)}>导入</button>
            </div>
            <textarea
              rows="6"
              value={texts[entity]}
              onChange={(e) => setTexts({ ...texts, [entity]: e.target.value })}
            />
          </div>
        ))}
      </div>
      {msg && <p className="ok">{msg}</p>}
    </div>
  )
}
