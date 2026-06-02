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
        <div className="header-logo-icon">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <path d="M12 2L3 7v10l9 5 9-5V7L12 2z" fill="rgba(255,255,255,.25)" stroke="#fff" strokeWidth="1.5" strokeLinejoin="round" />
            <path d="M12 7v10M7.5 9.5l4.5 2.5 4.5-2.5" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
        <span className="header-wordmark">Plum</span>
        <div className="header-sep" />
        <span className="header-page">Claims Processing</span>
        <div className="header-spacer" />
        <span className="header-pill">AI-Powered</span>
      </header>

      <main className="app-main">
        <SubmitForm onSubmit={handleSubmit} loading={loading} error={error} />

        <div className="results-col">
          {!decision && !loading && (
            <div className="card">
              <div className="empty-state">
                <div className="empty-icon">
                  <svg width="28" height="28" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
                <p className="empty-title">No claim submitted yet</p>
                <p className="empty-desc">Fill in the form and submit a claim to see the AI adjudication result here.</p>
              </div>
            </div>
          )}

          {loading && (
            <div className="card">
              <div className="empty-state">
                <div className="loading-ring" />
                <p className="empty-title">Processing claim</p>
                <p className="empty-desc">Running through the adjudication pipeline…</p>
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
      </main>
    </>
  )
}

export default App
