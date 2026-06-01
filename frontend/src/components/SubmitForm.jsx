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

export default function SubmitForm({ onSubmit, loading, error }) {
  const [form, setForm] = useState({
    member_id: 'EMP001',
    policy_id: POLICY_ID,
    claim_category: 'CONSULTATION',
    treatment_date: '',
    claimed_amount: '',
    hospital_name: '',
  })
  const [documents, setDocuments] = useState([])
  const fileRef = useRef()

  const set = (key, val) => setForm(f => ({ ...f, [key]: val }))

  const handleMemberSelect = (e) => {
    const member = SAMPLE_MEMBERS.find(m => m.member_id === e.target.value)
    if (member) {
      setForm(f => ({ ...f, member_id: member.member_id, policy_id: member.policy_id }))
    }
  }

  const handleFiles = (e) => {
    Array.from(e.target.files).forEach(file => {
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
    e.target.value = ''
  }

  const setDocType = (idx, type) =>
    setDocuments(prev => prev.map((d, i) => i === idx ? { ...d, actual_type: type || null } : d))

  const removeDoc = (idx) =>
    setDocuments(prev => prev.filter((_, i) => i !== idx))

  const handleDrop = (e) => {
    e.preventDefault()
    const dt = e.dataTransfer
    if (dt.files.length) handleFiles({ target: dt, preventDefault: () => {} })
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    onSubmit({
      ...form,
      claimed_amount: parseFloat(form.claimed_amount),
      hospital_name: form.hospital_name || null,
      documents,
    })
  }

  const isValid = form.member_id && form.policy_id && form.treatment_date && form.claimed_amount

  return (
    <form onSubmit={handleSubmit} className="card">
      <h2>Submit a Claim</h2>

      {error && <div className="error-banner">{error}</div>}

      <div className="field">
        <label>Member</label>
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

      <div className="field">
        <label>Claim Category</label>
        <select value={form.claim_category} onChange={e => set('claim_category', e.target.value)}>
          {CATEGORIES.map(c => <option key={c}>{c}</option>)}
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
          <label>Claimed Amount (₹)</label>
          <input
            type="number"
            min="0"
            step="0.01"
            placeholder="e.g. 1500"
            value={form.claimed_amount}
            onChange={e => set('claimed_amount', e.target.value)}
            required
          />
        </div>
      </div>

      <div className="field">
        <label>Hospital Name <span style={{fontWeight: 400}}>(optional — for network discount)</span></label>
        <input
          placeholder="e.g. Apollo Hospital"
          value={form.hospital_name}
          onChange={e => set('hospital_name', e.target.value)}
        />
      </div>

      <div className="section-label">Documents</div>

      {documents.length > 0 && (
        <div className="doc-list">
          {documents.map((doc, i) => (
            <div key={doc.file_id} className="doc-item">
              <span className="doc-name" title={doc.file_name}>{doc.file_name}</span>
              <select
                value={doc.actual_type || ''}
                onChange={e => setDocType(i, e.target.value)}
              >
                <option value="">Auto-detect</option>
                {DOC_TYPES.map(t => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}
              </select>
              <button type="button" onClick={() => removeDoc(i)} title="Remove">×</button>
            </div>
          ))}
        </div>
      )}

      <div
        className="drop-zone"
        onClick={() => fileRef.current.click()}
        onDrop={handleDrop}
        onDragOver={e => e.preventDefault()}
      >
        <svg width="24" height="24" fill="none" stroke="#9ca3af" strokeWidth="1.5" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636M12 8v4m0 4h.01" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 16.5V12m0-4V3m0 0L9 6m3-3l3 3" />
        </svg>
        <p>Click or drag files here (images, PDFs)</p>
        <input
          ref={fileRef}
          type="file"
          multiple
          accept="image/*,.pdf"
          style={{ display: 'none' }}
          onChange={handleFiles}
        />
      </div>

      <button type="submit" className="btn btn-primary" disabled={!isValid || loading}>
        {loading ? <><span className="spinner" />Processing…</> : 'Evaluate Claim'}
      </button>
    </form>
  )
}
