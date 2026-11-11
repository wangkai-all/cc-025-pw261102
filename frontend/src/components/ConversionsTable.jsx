import { useEffect, useState } from 'react'
import { api } from '../api'
import { channelColor, fen, fmtTime } from '../format'

const STATUS_LABELS = {
  credited: '参与分摊',
  in_window_not_credited: '窗口内·未选中',
  binding_after_conversion: '绑定晚于成交·未纳入',
  after_conversion: '晚于成交·未纳入',
  outside_window: '超出回看窗口',
}

function ChannelChips({ byChannel }) {
  const entries = Object.entries(byChannel)
  return (
    <span className="chips">
      {entries.map(([ch, cents]) => (
        <span key={ch} className="chip" style={{ borderColor: channelColor(ch) }}>
          {ch} {fen(cents)}
        </span>
      ))}
    </span>
  )
}

function Detail({ orderId, model, days }) {
  const [detail, setDetail] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => {
    api.detail(orderId, model, days).then(setDetail).catch((e) => setErr(e.message))
  }, [orderId, model, days])
  if (err) return <div className="error">{err}</div>
  if (!detail) return <div className="loading">加载中…</div>
  const o = detail.order
  return (
    <div className="detail">
      <div className="detail-grid">
        <div>
          <h4>成交与窗口</h4>
          <p>
            用户 {o.user_id} · 成交 {fmtTime(o.ts)} · 总额 {fen(o.gross_cents)}
            {o.refund_cents > 0 && <> · 退款 {fen(o.refund_cents)}</>}
            {o.reversed && <> · <b className="rev">已撤销</b></>}
            {' '}· 净额 <b>{fen(o.net_cents)}</b>
          </p>
          <p>
            回看窗口 {fmtTime(detail.window.start)} ~ {fmtTime(detail.window.end)}({detail.window.days} 天)
          </p>
          {detail.refunds.length > 0 && (
            <p>退款明细:{detail.refunds.map((r) => `${r.refund_id} ${fen(r.amount_cents)}`).join('、')}</p>
          )}
          <h4>身份绑定(仅成交前建立的生效)</h4>
          {detail.bindings.length === 0 && <p>无绑定记录</p>}
          <ul>
            {detail.bindings.map((b) => (
              <li key={b.anon_id} className={b.usable ? '' : 'excluded'}>
                {b.anon_id} → {o.user_id},绑定于 {fmtTime(b.bound_at)}
                {b.usable ? ' ✓ 生效' : ' ✗ 晚于成交,不生效'}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h4>触点路径(按时间、编号排序)</h4>
          {detail.touchpoints.length === 0 && <p>该用户没有任何触点记录 → 归入{detail.unknown_channel}</p>}
          <ul className="path">
            {detail.touchpoints.map((t) => (
              <li key={t.touchpoint_id} className={`tp ${t.status}`}>
                <span className="dot" style={{ background: channelColor(t.channel) }} />
                <span className="tp-id">#{t.touchpoint_id}</span>
                <span className="tp-ch">{t.channel}{t.is_direct && <em>(直接)</em>}</span>
                <span className="tp-ts">{fmtTime(t.ts)}</span>
                <span className="tp-status">{STATUS_LABELS[t.status]}</span>
                {t.status === 'credited' && (
                  <span className="tp-alloc">权重 {t.weight} → {fen(t.cents)}</span>
                )}
              </li>
            ))}
          </ul>
          <h4>分摊结果</h4>
          <ul>
            {detail.allocations.map((a, i) => (
              <li key={i}>
                {a.touchpoint_id === null ? detail.unknown_channel : `#${a.touchpoint_id} ${a.channel}`}
                :权重 {a.weight} → <b>{fen(a.cents)}</b>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}

export default function ConversionsTable({ orders, model, days }) {
  const [open, setOpen] = useState(null)
  return (
    <table className="tbl">
      <thead>
        <tr>
          <th>订单</th>
          <th>用户</th>
          <th>成交时间</th>
          <th className="num">总额</th>
          <th className="num">退款</th>
          <th className="num">净额</th>
          <th className="num">窗口内触点</th>
          <th>渠道分摊</th>
        </tr>
      </thead>
      <tbody>
        {orders.map((o) => (
          <>
            <tr
              key={o.order_id}
              className={`order-row ${open === o.order_id ? 'open' : ''} ${o.reversed ? 'rev' : ''}`}
              onClick={() => setOpen(open === o.order_id ? null : o.order_id)}
            >
              <td>{open === o.order_id ? '▾' : '▸'} {o.order_id}{o.reversed && <span className="tag">已撤销</span>}</td>
              <td>{o.user_id}</td>
              <td>{fmtTime(o.ts)}</td>
              <td className="num">{fen(o.gross_cents)}</td>
              <td className="num">{o.refund_cents ? fen(o.refund_cents) : '-'}</td>
              <td className="num"><b>{fen(o.net_cents)}</b></td>
              <td className="num">{o.touchpoint_count}</td>
              <td><ChannelChips byChannel={o.by_channel} /></td>
            </tr>
            {open === o.order_id && (
              <tr key={o.order_id + '-detail'} className="detail-row">
                <td colSpan="8">
                  <Detail orderId={o.order_id} model={model} days={days} />
                </td>
              </tr>
            )}
          </>
        ))}
      </tbody>
    </table>
  )
}
