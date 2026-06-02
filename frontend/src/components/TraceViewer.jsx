import { useState } from 'react'

function ChevronIcon({ open }) {
  return (
    <svg
      width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"
      className={`trace-chevron${open ? ' open' : ''}`}
    >
      <polyline points="6 9 12 15 18 9" />
    </svg>
  )
}

const STATUS_COLOR = {
  OK:      'var(--green)',
  FAILED:  'var(--red)',
  SKIPPED: 'var(--n300)',
  DEGRADED:'var(--amber)',
}

function TraceItem({ event }) {
  const [open, setOpen] = useState(false)
  const hasDetail = event.detail && Object.keys(event.detail).length > 0

  return (
    <div className="trace-item">
      <div
        className={`trace-row${hasDetail ? '' : ' no-detail'}`}
        onClick={() => hasDetail && setOpen(o => !o)}
      >
        <div className="trace-dot-col">
          <span className={`trace-dot dot-${event.status}`} />
        </div>

        <span className="trace-component">{event.component}</span>
        <span className="trace-summary-text">{event.summary}</span>

        <div className="trace-meta">
          {event.duration_ms > 0 && (
            <span className="trace-duration">{event.duration_ms}ms</span>
          )}
          {hasDetail && <ChevronIcon open={open} />}
        </div>
      </div>

      {open && hasDetail && (
        <div className="trace-detail-wrap">
          <div className="trace-detail">
            {JSON.stringify(event.detail, null, 2)}
          </div>
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

  const totalMs = trace.reduce((s, e) => s + (e.duration_ms || 0), 0)

  return (
    <div className="card">
      <div className="card-head">
        <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" style={{ color: 'var(--brand-600)', flexShrink: 0 }}>
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
        </svg>
        <span className="card-head-title">Decision Trace</span>
        <div className="card-head-spacer" />

        <div className="trace-summary-pills">
          {Object.entries(counts).map(([status, n]) => (
            <span key={status} className="trace-stat">
              <span className="trace-dot" style={{
                background: STATUS_COLOR[status] || 'var(--n300)',
                color: STATUS_COLOR[status] || 'var(--n300)',
                boxShadow: 'none',
                border: 'none',
                display: 'inline-block',
                width: 7, height: 7, borderRadius: '50%',
              }} />
              {n} {status}
            </span>
          ))}
          {totalMs > 0 && (
            <span className="trace-stat" style={{ color: 'var(--text-subtle)' }}>
              {totalMs}ms total
            </span>
          )}
        </div>
      </div>

      <div className="trace-timeline">
        {trace.map((event, i) => (
          <TraceItem key={i} event={event} />
        ))}
      </div>
    </div>
  )
}
