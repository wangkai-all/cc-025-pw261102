import { channelColor, fen } from '../format'

export default function ChannelSummary({ channels, total }) {
  const max = Math.max(1, ...channels.map((c) => Math.abs(c.net_cents)))
  return (
    <table className="tbl">
      <thead>
        <tr>
          <th>渠道</th>
          <th className="num">归因成交数</th>
          <th className="num">归因净收入</th>
          <th style={{ width: '40%' }}></th>
        </tr>
      </thead>
      <tbody>
        {channels.map((c) => (
          <tr key={c.channel}>
            <td>
              <span className="dot" style={{ background: channelColor(c.channel) }} />
              {c.channel}
            </td>
            <td className="num">{c.orders}</td>
            <td className="num">{fen(c.net_cents)}</td>
            <td>
              <div
                className="bar"
                style={{
                  width: `${(Math.abs(c.net_cents) / max) * 100}%`,
                  background: channelColor(c.channel),
                }}
              />
            </td>
          </tr>
        ))}
        <tr className="total-row">
          <td>合计</td>
          <td className="num">{channels.reduce((a, c) => a + c.orders, 0)}</td>
          <td className="num">{fen(total)}</td>
          <td></td>
        </tr>
      </tbody>
    </table>
  )
}
