const fmt = (amount) =>
  amount != null ? `₹${Number(amount).toLocaleString('en-IN', { minimumFractionDigits: 0 })}` : '—'

const STATUS_ICONS = {
  APPROVED: '✓',
  PARTIAL: '~',
  REJECTED: '✕',
  MANUAL_REVIEW: '⚑',
  STOPPED: '⊘',
}

function confidenceColor(score) {
  if (score >= 0.8) return '#16a34a'
  if (score >= 0.5) return '#d97706'
  return '#dc2626'
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
  } = decision

  const pct = Math.round(confidence * 100)

  return (
    <div className="card">
      <div className="decision-header">
        <h2>Decision</h2>
        <span className={`badge badge-${status}`}>
          {STATUS_ICONS[status]} {status.replace('_', ' ')}
        </span>
      </div>

      <div className={`decision-amount ${approved_amount ? '' : 'zero'}`}>
        {approved_amount != null && approved_amount > 0 ? fmt(approved_amount) : '—'}
      </div>
      <div className="decision-reason">{reason}</div>

      <div className="confidence-bar-wrap">
        <label>
          <span>Confidence</span>
          <span style={{ color: confidenceColor(confidence) }}>{pct}%</span>
        </label>
        <div className="confidence-bar">
          <div
            className="confidence-fill"
            style={{ width: `${pct}%`, background: confidenceColor(confidence) }}
          />
        </div>
      </div>

      {recommend_manual_review && (
        <div className="info-box">
          ⚑ This claim is flagged for manual review by your operations team.
        </div>
      )}

      {message_to_member && (
        <div className="info-box member-msg">
          <strong>Message to member:</strong> {message_to_member}
        </div>
      )}

      {rejection_reasons.length > 0 && (
        <>
          <div className="section-label">Rejection Reasons</div>
          <div className="rejection-tags">
            {rejection_reasons.map((r, i) => (
              <span key={i} className="rejection-tag">{r.replace(/_/g, ' ')}</span>
            ))}
          </div>
        </>
      )}

      {line_item_breakdown.length > 0 && (
        <>
          <div className="section-label">Line Items</div>
          <div>
            {line_item_breakdown.map((item, i) => (
              <div key={i} className="line-item">
                <span className="li-desc">
                  {item.description}
                  {item.reason && (
                    <span style={{ display: 'block', fontSize: 11, color: '#6b7280', marginTop: 1 }}>
                      {item.reason}
                    </span>
                  )}
                </span>
                <span className={`li-tag li-tag-${item.classification}`}>{item.classification}</span>
                <span className="li-amount">{fmt(item.amount)}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
