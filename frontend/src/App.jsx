import React, { useState, useEffect } from 'react'
import ExperimentSelector from './components/ExperimentSelector.jsx'
import InputForm from './components/InputForm.jsx'
import PipelineTrace from './components/PipelineTrace.jsx'
import CriticSummary from './components/CriticSummary.jsx'

const API_BASE = 'https://dynamic-llm-agent-dev-643234238822.europe-west1.run.app'

const styles = {
  root: {
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    background: '#0d0d0d',
    fontFamily: "'JetBrains Mono', 'Courier New', monospace",
    color: '#e0e0e0',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '16px 24px',
    borderBottom: '1px solid #2a2a2a',
    background: '#111111',
    flexShrink: 0,
  },
  headerAccent: {
    width: '8px',
    height: '8px',
    borderRadius: '50%',
    background: '#00ff88',
    boxShadow: '0 0 8px #00ff88',
  },
  headerTitle: {
    fontSize: '15px',
    fontWeight: '700',
    color: '#ffffff',
    letterSpacing: '0.05em',
  },
  headerSubtitle: {
    fontSize: '11px',
    color: '#555555',
    marginLeft: 'auto',
    letterSpacing: '0.08em',
  },
  body: {
    display: 'flex',
    flex: 1,
    overflow: 'hidden',
  },
  leftPanel: {
    width: '360px',
    minWidth: '320px',
    maxWidth: '400px',
    display: 'flex',
    flexDirection: 'column',
    borderRight: '1px solid #2a2a2a',
    overflow: 'hidden',
  },
  leftPanelInner: {
    flex: 1,
    overflowY: 'auto',
    padding: '20px',
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },
  rightPanel: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  },
  rightPanelInner: {
    flex: 1,
    overflowY: 'auto',
    padding: '20px',
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },
  runButton: {
    width: '100%',
    padding: '12px 20px',
    background: '#00ff88',
    color: '#0d0d0d',
    border: 'none',
    borderRadius: '4px',
    fontSize: '13px',
    fontWeight: '700',
    fontFamily: "'JetBrains Mono', 'Courier New', monospace",
    cursor: 'pointer',
    letterSpacing: '0.08em',
    textTransform: 'uppercase',
    transition: 'opacity 0.15s',
  },
  runButtonDisabled: {
    width: '100%',
    padding: '12px 20px',
    background: '#1a3a2a',
    color: '#2a6a4a',
    border: '1px solid #2a4a3a',
    borderRadius: '4px',
    fontSize: '13px',
    fontWeight: '700',
    fontFamily: "'JetBrains Mono', 'Courier New', monospace",
    cursor: 'not-allowed',
    letterSpacing: '0.08em',
    textTransform: 'uppercase',
  },
  runButtonArea: {
    padding: '16px 20px',
    borderTop: '1px solid #2a2a2a',
    background: '#0d0d0d',
    flexShrink: 0,
  },
  errorBox: {
    background: '#1a0a0a',
    border: '1px solid #4a1a1a',
    borderRadius: '4px',
    padding: '12px 16px',
    color: '#ff6666',
    fontSize: '12px',
    lineHeight: '1.6',
  },
  errorLabel: {
    color: '#ff4444',
    fontWeight: '700',
    marginBottom: '4px',
    fontSize: '11px',
    letterSpacing: '0.08em',
  },
  emptyState: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100%',
    gap: '12px',
    color: '#333333',
  },
  emptyIcon: {
    fontSize: '40px',
    opacity: 0.3,
  },
  emptyText: {
    fontSize: '13px',
    color: '#3a3a3a',
    textAlign: 'center',
    lineHeight: '1.6',
  },
  loadingState: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100%',
    gap: '20px',
  },
  loadingTitle: {
    fontSize: '14px',
    color: '#00ff88',
    fontWeight: '600',
    letterSpacing: '0.05em',
  },
  loadingSubtext: {
    fontSize: '11px',
    color: '#555555',
    textAlign: 'center',
    lineHeight: '1.8',
  },
  loadingDots: {
    display: 'flex',
    gap: '8px',
    alignItems: 'center',
  },
  loadingDot: {
    width: '6px',
    height: '6px',
    borderRadius: '50%',
    background: '#00ff88',
  },
  sectionLabel: {
    fontSize: '10px',
    fontWeight: '700',
    color: '#555555',
    letterSpacing: '0.12em',
    textTransform: 'uppercase',
    marginBottom: '2px',
  },
}

// Simple loading dots animation via React state
function LoadingDots() {
  const [frame, setFrame] = useState(0)

  useEffect(() => {
    const interval = setInterval(() => {
      setFrame(f => (f + 1) % 3)
    }, 400)
    return () => clearInterval(interval)
  }, [])

  return (
    <div style={styles.loadingDots}>
      {[0, 1, 2].map(i => (
        <div
          key={i}
          style={{
            ...styles.loadingDot,
            opacity: frame === i ? 1 : 0.2,
          }}
        />
      ))}
    </div>
  )
}

export default function App() {
  const [experiments, setExperiments] = useState([])
  const [experimentsLoading, setExperimentsLoading] = useState(true)
  const [experimentsError, setExperimentsError] = useState(null)
  const [selectedExperiment, setSelectedExperiment] = useState(null)

  const [inputData, setInputData] = useState({
    company_name: '',
    company_type: 'IT hardware értékesítő (szerverek)',
    target_audience: 'Középvezetők',
    goal: 'AI stratégiai gondolkodás fejlesztése',
    context: '',
  })

  const [pipelineResult, setPipelineResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Fetch experiments on load
  useEffect(() => {
    setExperimentsLoading(true)
    setExperimentsError(null)
    fetch(`${API_BASE}/pipeline/experiments`)
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`)
        return res.json()
      })
      .then(data => {
        const list = Array.isArray(data) ? data : (data.experiments || data.data || [])
        setExperiments(list)
        if (list.length > 0) setSelectedExperiment(list[0])
      })
      .catch(err => {
        setExperimentsError(`Kísérletek betöltése sikertelen: ${err.message}`)
      })
      .finally(() => {
        setExperimentsLoading(false)
      })
  }, [])

  const handleRun = async () => {
    if (!selectedExperiment) return
    setLoading(true)
    setError(null)
    setPipelineResult(null)

    try {
      const payload = {
        experiment_id: selectedExperiment.id || selectedExperiment.name,
        input: {
          company_name: inputData.company_name,
          company_type: inputData.company_type,
          target_audience: inputData.target_audience,
          goal: inputData.goal,
          context: inputData.context,
        },
      }

      const res = await fetch(`${API_BASE}/pipeline/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`HTTP ${res.status}: ${errText || res.statusText}`)
      }

      const result = await res.json()
      setPipelineResult(result)
    } catch (err) {
      setError(`Pipeline futtatása sikertelen: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  const canRun = selectedExperiment && !loading && inputData.company_name.trim() !== ''

  return (
    <div style={styles.root}>
      {/* Header */}
      <header style={styles.header}>
        <div style={styles.headerAccent} />
        <span style={styles.headerTitle}>NEOMI Pipeline Runner</span>
        <span style={styles.headerSubtitle}>
          {selectedExperiment
            ? `// ${selectedExperiment.id || selectedExperiment.name || 'ismeretlen kísérlet'}`
            : '// válasszon kísérletet'}
        </span>
      </header>

      {/* Main body */}
      <div style={styles.body}>
        {/* Left panel */}
        <div style={styles.leftPanel}>
          <div style={styles.leftPanelInner}>
            <div>
              <div style={styles.sectionLabel}>Kísérlet</div>
              <ExperimentSelector
                experiments={experiments}
                loading={experimentsLoading}
                error={experimentsError}
                selected={selectedExperiment}
                onSelect={setSelectedExperiment}
              />
            </div>

            <div>
              <div style={styles.sectionLabel}>Bemeneti adatok</div>
              <InputForm inputData={inputData} onChange={setInputData} disabled={loading} />
            </div>

            {error && (
              <div style={styles.errorBox}>
                <div style={styles.errorLabel}>HIBA</div>
                {error}
              </div>
            )}
          </div>

          <div style={styles.runButtonArea}>
            <button
              style={canRun ? styles.runButton : styles.runButtonDisabled}
              onClick={handleRun}
              disabled={!canRun}
            >
              {loading ? 'Pipeline fut...' : 'Pipeline futtatása'}
            </button>
            {!inputData.company_name.trim() && !loading && (
              <div style={{ marginTop: '8px', fontSize: '11px', color: '#444444', textAlign: 'center' }}>
                A cég neve kötelező
              </div>
            )}
          </div>
        </div>

        {/* Right panel */}
        <div style={styles.rightPanel}>
          <div style={styles.rightPanelInner}>
            {loading && (
              <div style={styles.loadingState}>
                <LoadingDots />
                <div style={styles.loadingTitle}>Pipeline fut...</div>
                <div style={styles.loadingSubtext}>
                  A pipeline futtatása 30–60 másodpercet vehet igénybe.<br />
                  Az ügynökök feldolgozzák a bemeneti adatokat.
                </div>
              </div>
            )}

            {!loading && !pipelineResult && !error && (
              <div style={styles.emptyState}>
                <div style={styles.emptyIcon}>▶</div>
                <div style={styles.emptyText}>
                  Töltse ki az adatokat és<br />
                  futtassa a pipeline-t az eredmények megtekintéséhez.
                </div>
              </div>
            )}

            {!loading && pipelineResult && (
              <>
                {pipelineResult.node_traces && pipelineResult.node_traces.length > 0 && (
                  <div>
                    <div style={styles.sectionLabel}>Pipeline nyomkövetés</div>
                    <PipelineTrace traces={pipelineResult.node_traces} />
                  </div>
                )}

                {pipelineResult.critique && (
                  <div>
                    <div style={styles.sectionLabel}>Kritikai összefoglaló</div>
                    <CriticSummary critique={pipelineResult.critique} />
                  </div>
                )}

                {!pipelineResult.node_traces && !pipelineResult.critique && (
                  <div style={styles.errorBox}>
                    <div style={styles.errorLabel}>FIGYELMEZTETÉS</div>
                    A válasz megérkezett, de nem tartalmaz node_traces vagy critique mezőt.
                    <pre style={{ marginTop: '8px', fontSize: '11px', color: '#888888', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                      {JSON.stringify(pipelineResult, null, 2)}
                    </pre>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
