import { useState } from 'react'
import axios from 'axios'
import './App.css'
import SubmitForm from './components/SubmitForm'
import DecisionCard from './components/DecisionCard'
import TraceViewer from './components/TraceViewer'

function App() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [decision, setDecision] = useState(null)

  const handleSubmit = async (payload) => {
    setLoading(true)
    setError(null)
    setDecision(null)
    try {
      const { data } = await axios.post('/claims/evaluate', payload)
      setDecision(data)
    } catch (err) {
      const msg = err.response?.data?.detail || err.response?.data?.error || err.message
      setError(`Request failed: ${msg}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <header className="app-header">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
          <path d="M12 2L3 7v10l9 5 9-5V7L12 2z" fill="rgba(255,255,255,.25)" stroke="#fff" strokeWidth="1.5" strokeLinejoin="round" />
          <path d="M12 7v10M7.5 9.5l4.5 2.5 4.5-2.5" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <h1>Plum Claims Processing</h1>
        <span className="tagline">Health Insurance · AI-Powered Adjudication</span>
      </header>

      <div className="app-body">
        <SubmitForm onSubmit={handleSubmit} loading={loading} error={error} />

        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          {!decision && !loading && (
            <div className="card">
              <div className="empty-state">
                <svg width="48" height="48" fill="none" stroke="currentColor" strokeWidth="1.2" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <p>Submit a claim to see the decision and full trace here.</p>
              </div>
            </div>
          )}

          {loading && (
            <div className="card">
              <div className="empty-state">
                <div style={{ width: 32, height: 32, border: '3px solid #e5e7eb', borderTopColor: '#7c3aed', borderRadius: '50%', animation: 'spin .7s linear infinite' }} />
                <p>Processing claim through the pipeline…</p>
              </div>
            </div>
          )}

          {decision && (
            <>
              <DecisionCard decision={decision} />
              <TraceViewer trace={decision.trace} />
            </>
          )}
        </div>
      </div>
    </>
  )
}

export default App
