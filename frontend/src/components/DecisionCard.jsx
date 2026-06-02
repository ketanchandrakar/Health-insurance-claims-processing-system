const fmt = (amount) =>
  amount != null ? `₹${Number(amount).toLocaleString('en-IN', { minimumFractionDigits: 0 })}` : '—'

function confidenceColor(score) {
  if (score >= 0.8) return 'var(--green)'
  if (score >= 0.5) return 'var(--amber)'
  return 'var(--red)'
}

const STATUS_LABELS = {
  APPROVED:      'Approved',
  PARTIAL:       'Partially Approved',
  REJECTED:      'Rejected',
  MANUAL_REVIEW: 'Manual Review',
  STOPPED:       'Stopped',
}

const STATUS_ICONS = {
  APPROVED:      <CheckIcon />,
  PARTIAL:       <PartialIcon />,
  REJECTED:      <XIcon />,
  MANUAL_REVIEW: <FlagIcon />,
  STOPPED:       <StopIcon />,
}

function CheckIcon()   { return <svg width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12" /></svg> }
function XIcon()       { return <svg width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg> }
function FlagIcon()    { return <svg width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1zM4 22v-7" /></svg> }
function PartialIcon() { return <svg width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24"><line x1="5" y1="12" x2="19" y2="12" /></svg> }
function StopIcon()    { return <svg width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" /><line x1="4.93" y1="4.93" x2="19.07" y2="19.07" /></svg> }
function WarnIcon()    { return <svg width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" /><line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" /></svg> }
function InfoIcon()    { return <svg width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" /><line x1="12" y1="16" x2="12" y2="12" /><line x1="12" y1="8" x2="12.01" y2="8" /></svg> }

function extractCalcTrace(trace) {
  if (!trace) return []
  const adjEvent = trace.find(e => e.component === 'adjudicator')
  return adjEvent?.detail?.calc_trace || []
}

export default function DecisionCard({ decision }) {
  const {
    status,
    approved_amount,
    reason,
    confidence,
    rejection_reasons = [],
    line_item_breakdown = [],
    recommend_manual_review,
    message_to_member,
    trace,
  } = decision

  const pct = Math.round(confidence * 100)
  const calcTrace = extractCalcTrace(trace)

  const hasAmount = approved_amount != null && approved_amount > 0

  return (
    <div className="card">
      {/* Status banner */}
      <div className={`decision-banner ${status}`}>
        <div className="decision-banner-top">
          <span className={`badge badge-${status}`}>
            {STATUS_ICONS[status]}
            {STATUS_LABELS[status] || status}
          </span>
        </div>

        <div className={`decision-amount ${hasAmount ? status : 'nil'}`}>
          {hasAmount ? fmt(approved_amount) : '—'}
        </div>
        {hasAmount && <div className="decision-amount-label">Approved amount</div>}
        <div className="decision-reason">{reason}</div>
      </div>

      {/* Body */}
      <div className="decision-body">
        {/* Confidence */}
        <div>
          <div className="section-label">Confidence</div>
          <div className="confidence-row">
            <span className="conf-label">Score</span>
            <div className="conf-bar-wrap">
              <div
                className="conf-bar-fill"
                style={{ width: `${pct}%`, background: confidenceColor(confidence) }}
              />
            </div>
            <span className="conf-pct" style={{ color: confidenceColor(confidence) }}>{pct}%</span>
          </div>
        </div>

        {/* Manual review flag */}
        {recommend_manual_review && (
          <div className="info-box warning">
            <WarnIcon />
            <span>This claim is flagged for manual review by your operations team.</span>
          </div>
        )}

        {/* Message to member */}
        {message_to_member && (
          <div className="info-box info">
            <InfoIcon />
            <span><strong>Action required: </strong>{message_to_member}</span>
          </div>
        )}

        {/* Rejection reasons */}
        {rejection_reasons.length > 0 && (
          <div>
            <div className="section-label">Rejection Reasons</div>
            <div className="rejection-tags">
              {rejection_reasons.map((r, i) => (
                <span key={i} className="rejection-tag">
                  <XIcon />
                  {r.replace(/_/g, ' ')}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Line items */}
        {line_item_breakdown.length > 0 && (
          <div>
            <div className="section-label">Line Items</div>
            <table className="line-items-table">
              <thead>
                <tr>
                  <th>Description</th>
                  <th style={{ width: 80 }}>Status</th>
                  <th style={{ width: 70 }}>Amount</th>
                </tr>
              </thead>
              <tbody>
                {line_item_breakdown.map((item, i) => (
                  <tr key={i}>
                    <td>
                      <div className="li-desc-main">{item.description}</div>
                      {item.reason && <div className="li-desc-sub">{item.reason}</div>}
                    </td>
                    <td><span className={`li-tag li-tag-${item.classification}`}>{item.classification}</span></td>
                    <td>{fmt(item.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Financial breakdown */}
        {calcTrace.length > 0 && (
          <div>
            <div className="section-label">Financial Breakdown</div>
            <table className="calc-trace-table">
              <tbody>
                {calcTrace.map((step, i) => (
                  <tr key={i}>
                    <td style={{ color: 'var(--text-secondary)' }}>{step.label}</td>
                    <td>{fmt(step.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
