import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import ChannelSummary from './components/ChannelSummary'
import ConversionsTable from './components/ConversionsTable'
import CompareView from './components/CompareView'
import ImportPanel from './components/ImportPanel'
import { fen } from './format'

export default function App() {
  const [meta, setMeta] = useState(null)
  const [model, setModel] = useState('last_non_direct')
  const [days, setDays] = useState(30)
  const [summary, setSummary] = useState(null)
  const [orders, setOrders] = useState(null)
  const [version, setVersion] = useState(0)
  const [error, setError] = useState(null)
  const [showImport, setShowImport] = useState(false)

  const refresh = useCallback(() => setVersion((v) => v + 1), [])

  useEffect(() => {
    api.meta().then(setMeta).catch((e) => setError(e.message))
  }, [version])

  useEffect(() => {
    setError(null)
    Promise.all([api.summary(model, days), api.conversions(model, days)])
      .then(([s, c]) => {
        setSummary(s)
        setOrders(c.orders)
      })
      .catch((e) => setError(e.message))
  }, [model, days, version])

  const models = meta?.models || []

  return (
    <div className="app">
      <header>
        <h1>多触点归因分析</h1>
        <p className="sub">
          触点 {meta?.counts.touchpoints ?? '-'} · 身份绑定 {meta?.counts.identity_bindings ?? '-'} ·
          成交 {meta?.counts.conversions ?? '-'} · 退款 {meta?.counts.refunds ?? '-'}
        </p>
      </header>

      <section className="controls">
        <div className="model-switch">
          {models.map((m) => (
            <button
              key={m.key}
              className={model === m.key ? 'active' : ''}
              onClick={() => setModel(m.key)}
            >
              {m.label}
            </button>
          ))}
        </div>
        <label className="days">
          回看窗口
          <input
            type="number"
            min="1"
            max="365"
            value={days}
            onChange={(e) => setDays(Math.max(1, Number(e.target.value) || 1))}
          />
          天
        </label>
        <div className="actions">
          <button onClick={() => api.seed().then(refresh).catch((e) => setError(e.message))}>
            载入演示数据
          </button>
          <button onClick={() => setShowImport((s) => !s)}>
            {showImport ? '收起导入' : '导入数据'}
          </button>
          <button
            className="danger"
            onClick={() => api.reset().then(refresh).catch((e) => setError(e.message))}
          >
            清空
          </button>
        </div>
      </section>

      {error && <div className="error">{error}</div>}

      {showImport && <ImportPanel onDone={refresh} onError={setError} />}

      <section>
        <h2>
          渠道汇总
          {summary && <span className="total">净额合计 {fen(summary.total_net_cents)}</span>}
        </h2>
        {summary && <ChannelSummary channels={summary.channels} total={summary.total_net_cents} />}
      </section>

      <section>
        <h2>成交列表 <span className="hint">点击行展开成交路径与分摊明细</span></h2>
        {orders && <ConversionsTable orders={orders} model={model} days={days} />}
      </section>

      <section>
        <h2>口径对比 <span className="hint">找出切换归因方式时渠道金额发生变化的具体成交</span></h2>
        <CompareView days={days} models={models} version={version} />
      </section>
    </div>
  )
}
