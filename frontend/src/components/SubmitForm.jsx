import { useState, useRef } from 'react'

const CATEGORIES = [
  'CONSULTATION', 'DIAGNOSTIC', 'PHARMACY',
  'DENTAL', 'VISION', 'ALTERNATIVE_MEDICINE',
]

const DOC_TYPES = [
  'PRESCRIPTION', 'HOSPITAL_BILL', 'PHARMACY_BILL',
  'LAB_REPORT', 'DIAGNOSTIC_REPORT', 'DENTAL_REPORT',
  'DISCHARGE_SUMMARY', 'UNKNOWN',
]

const POLICY_ID = 'PLUM_GHI_2024'

const SAMPLE_MEMBERS = [
  { member_id: 'EMP001', policy_id: POLICY_ID, label: 'Rajesh Kumar (EMP001)' },
  { member_id: 'EMP002', policy_id: POLICY_ID, label: 'Priya Singh (EMP002)' },
  { member_id: 'EMP003', policy_id: POLICY_ID, label: 'Amit Verma (EMP003)' },
  { member_id: 'EMP004', policy_id: POLICY_ID, label: 'Sneha Reddy (EMP004)' },
  { member_id: 'EMP005', policy_id: POLICY_ID, label: 'Vikram Joshi (EMP005)' },
  { member_id: 'EMP006', policy_id: POLICY_ID, label: 'Kavita Nair (EMP006)' },
]

function FileIcon() {
  return (
    <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
  )
}

export default function SubmitForm({ onSubmit, loading, error }) {
  const [form, setForm] = useState({
    member_id: 'EMP001',
    policy_id: POLICY_ID,
    claim_category: 'CONSULTATION',
    treatment_date: '',
    claimed_amount: '',
    hospital_name: '',
    pre_auth_number: '',
  })
  const [documents, setDocuments] = useState([])
  const [dragOver, setDragOver] = useState(false)
  const fileRef = useRef()

  const set = (key, val) => setForm(f => ({ ...f, [key]: val }))

  const handleMemberSelect = (e) => {
    const member = SAMPLE_MEMBERS.find(m => m.member_id === e.target.value)
    if (member) setForm(f => ({ ...f, member_id: member.member_id, policy_id: member.policy_id }))
  }

  const addFiles = (files) => {
    Array.from(files).forEach(file => {
      const reader = new FileReader()
      reader.onload = (ev) => {
        const b64 = ev.target.result.split(',')[1]
        setDocuments(prev => [...prev, {
          file_id: `upload_${Date.now()}_${Math.random().toString(36).slice(2)}`,
          file_name: file.name,
          content_b64: b64,
          actual_type: null,
        }])
      }
      reader.readAsDataURL(file)
    })
  }

  const handleFiles = (e) => { addFiles(e.target.files); e.target.value = '' }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files)
  }

  const setDocType = (idx, type) =>
    setDocuments(prev => prev.map((d, i) => i === idx ? { ...d, actual_type: type || null } : d))

  const removeDoc = (idx) => setDocuments(prev => prev.filter((_, i) => i !== idx))

  const handleSubmit = (e) => {
    e.preventDefault()
    onSubmit({
      ...form,
      claimed_amount: parseFloat(form.claimed_amount),
      hospital_name: form.hospital_name || null,
      pre_auth_number: form.pre_auth_number || null,
      documents,
    })
  }

  const isValid = form.member_id && form.policy_id && form.treatment_date && form.claimed_amount

  return (
    <form onSubmit={handleSubmit} className="card">
      <div className="card-head">
        <svg width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" style={{ color: 'var(--brand-600)', flexShrink: 0 }}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
        </svg>
        <span className="card-head-title">New Claim</span>
      </div>

      {error && (
        <div className="error-banner">
          <svg width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" style={{ flexShrink: 0, marginTop: 1 }}>
            <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          {error}
        </div>
      )}

      {/* Member */}
      <div className="form-section">
        <div className="form-section-label">Member</div>

        <div className="field">
          <label>Select member</label>
          <select value={form.member_id} onChange={handleMemberSelect}>
            {SAMPLE_MEMBERS.map(m => (
              <option key={m.member_id} value={m.member_id}>{m.label}</option>
            ))}
          </select>
        </div>

        <div className="field-row">
          <div className="field">
            <label>Member ID</label>
            <input value={form.member_id} onChange={e => set('member_id', e.target.value)} required />
          </div>
          <div className="field">
            <label>Policy ID</label>
            <input value={form.policy_id} onChange={e => set('policy_id', e.target.value)} required />
          </div>
        </div>
      </div>

      {/* Claim details */}
      <div className="form-section">
        <div className="form-section-label">Claim Details</div>

        <div className="field">
          <label>Category</label>
          <select value={form.claim_category} onChange={e => set('claim_category', e.target.value)}>
            {CATEGORIES.map(c => <option key={c}>{c.replace(/_/g, ' ')}</option>)}
          </select>
        </div>

        <div className="field-row">
          <div className="field">
            <label>Treatment Date</label>
            <input
              type="date"
              value={form.treatment_date}
              onChange={e => set('treatment_date', e.target.value)}
              required
            />
          </div>
          <div className="field">
            <label>Claimed Amount</label>
            <div className="prefix-wrap">
              <span className="prefix-sym">₹</span>
              <input
                type="number" min="0" step="0.01" placeholder="e.g. 1500"
                value={form.claimed_amount}
                onChange={e => set('claimed_amount', e.target.value)}
                required
              />
            </div>
          </div>
        </div>

        <div className="field">
          <label>
            Hospital Name
            <span className="opt">(optional — for network discount)</span>
          </label>
          <input
            placeholder="e.g. Apollo Hospital"
            value={form.hospital_name}
            onChange={e => set('hospital_name', e.target.value)}
          />
        </div>

        {form.claim_category === 'DIAGNOSTIC' && (
          <div className="field">
            <label>
              Pre-Authorization Number
              <span className="opt">(required for diagnostic claims ≥ ₹10,000)</span>
            </label>
            <input
              placeholder="e.g. PA-2024-00123"
              value={form.pre_auth_number}
              onChange={e => set('pre_auth_number', e.target.value)}
            />
          </div>
        )}
      </div>

      {/* Documents */}
      <div className="form-section">
        <div className="form-section-label">Supporting Documents</div>

        {documents.length > 0 && (
          <div className="doc-list">
            {documents.map((doc, i) => (
              <div key={doc.file_id} className="doc-item">
                <div className="doc-file-icon"><FileIcon /></div>
                <span className="doc-name" title={doc.file_name}>{doc.file_name}</span>
                <select
                  value={doc.actual_type || ''}
                  onChange={e => setDocType(i, e.target.value)}
                >
                  <option value="">Auto-detect</option>
                  {DOC_TYPES.map(t => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}
                </select>
                <button type="button" className="doc-remove" onClick={() => removeDoc(i)} title="Remove">
                  <svg width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        )}

        <div
          className={`drop-zone${dragOver ? ' over' : ''}`}
          onClick={() => fileRef.current.click()}
          onDrop={handleDrop}
          onDragOver={e => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
        >
          <div className="dz-icon">
            <svg width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
              <polyline points="16 16 12 12 8 16" /><line x1="12" y1="12" x2="12" y2="21" />
              <path d="M20.39 18.39A5 5 0 0018 9h-1.26A8 8 0 103 16.3" />
            </svg>
          </div>
          <p className="dz-label">Click or drag files here</p>
          <p className="dz-hint">Images or PDFs accepted</p>
          <input
            ref={fileRef} type="file" multiple accept="image/*,.pdf"
            style={{ display: 'none' }} onChange={handleFiles}
          />
        </div>

        <button type="submit" className="btn btn-primary" style={{ marginTop: 14 }} disabled={!isValid || loading}>
          {loading
            ? <><span className="spinner" /> Processing…</>
            : <>
                <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.2" viewBox="0 0 24 24">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
                Evaluate Claim
              </>
          }
        </button>
      </div>
    </form>
  )
}
