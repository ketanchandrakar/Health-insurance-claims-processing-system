import { useState } from 'react'

const STATUS_LABELS = {
  OK: 'OK',
  FAILED: 'FAILED',
  SKIPPED: 'SKIPPED',
  DEGRADED: 'DEGRADED',
}

function TraceItem({ event }) {
  const [open, setOpen] = useState(false)
  const hasDetail = event.detail && Object.keys(event.detail).length > 0

  return (
    <div className="trace-item">
      <div className="trace-header" onClick={() => hasDetail && setOpen(o => !o)}>
        <span className={`trace-dot dot-${event.status}`} />
        <span className="trace-component">{event.component}</span>
        <span className="trace-summary">{event.summary}</span>
        {event.duration_ms > 0 && (
          <span className="trace-duration">{event.duration_ms}ms</span>
        )}
        {hasDetail && (
          <span className="trace-chevron">{open ? '▲' : '▼'}</span>
        )}
      </div>
      {open && hasDetail && (
        <div className="trace-detail">
          {JSON.stringify(event.detail, null, 2)}
        </div>
      )}
    </div>
  )
}

export default function TraceViewer({ trace }) {
  if (!trace || trace.length === 0) return null

  const counts = trace.reduce((acc, e) => {
    acc[e.status] = (acc[e.status] || 0) + 1
    return acc
  }, {})

  return (
    <div className="card" style={{ marginTop: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
        <h2 style={{ marginBottom: 0 }}>Decision Trace</h2>
        <span style={{ fontSize: 12, color: '#6b7280', marginLeft: 'auto' }}>
          {Object.entries(counts).map(([s, n]) => (
            <span key={s} style={{ marginLeft: 8 }}>
              <span className={`trace-dot dot-${s}`} style={{ display: 'inline-block', marginRight: 3, verticalAlign: 'middle' }} />
              {n} {STATUS_LABELS[s]}
            </span>
          ))}
        </span>
      </div>

      {trace.map((event, i) => (
        <TraceItem key={i} event={event} />
      ))}
    </div>
  )
}
