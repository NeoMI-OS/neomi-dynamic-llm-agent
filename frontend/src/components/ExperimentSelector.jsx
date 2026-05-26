import React, { useState } from 'react'

const styles = {
  wrapper: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  select: {
    width: '100%',
    padding: '9px 12px',
    background: '#1a1a1a',
    border: '1px solid #2a2a2a',
    borderRadius: '4px',
    color: '#e0e0e0',
    fontFamily: "'JetBrains Mono', 'Courier New', monospace",
    fontSize: '12px',
    cursor: 'pointer',
    outline: 'none',
    appearance: 'none',
    backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath fill='%23555' d='M0 0l5 6 5-6z'/%3E%3C/svg%3E")`,
    backgroundRepeat: 'no-repeat',
    backgroundPosition: 'right 12px center',
    paddingRight: '32px',
  },
  selectDisabled: {
    width: '100%',
    padding: '9px 12px',
    background: '#141414',
    border: '1px solid #1e1e1e',
    borderRadius: '4px',
    color: '#444444',
    fontFamily: "'JetBrains Mono', 'Courier New', monospace",
    fontSize: '12px',
    cursor: 'not-allowed',
    outline: 'none',
  },
  descriptionBox: {
    background: '#141414',
    border: '1px solid #222222',
    borderRadius: '4px',
    padding: '10px 12px',
  },
  descriptionText: {
    fontSize: '11px',
    color: '#888888',
    lineHeight: '1.6',
    marginBottom: '8px',
  },
  nodesLabel: {
    fontSize: '10px',
    color: '#444444',
    letterSpacing: '0.1em',
    textTransform: 'uppercase',
    marginBottom: '6px',
  },
  nodesList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '3px',
  },
  nodeItem: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '4px 8px',
    background: '#1a1a1a',
    borderRadius: '3px',
  },
  nodeName: {
    fontSize: '11px',
    color: '#cccccc',
  },
  nodeModel: {
    fontSize: '10px',
    color: '#555555',
    fontStyle: 'italic',
  },
  errorText: {
    fontSize: '11px',
    color: '#ff6666',
    padding: '8px 0',
  },
  loadingText: {
    fontSize: '11px',
    color: '#555555',
    padding: '8px 0',
  },
}

export default function ExperimentSelector({ experiments, loading, error, selected, onSelect }) {
  const handleChange = (e) => {
    const id = e.target.value
    const exp = experiments.find(ex => (ex.id || ex.name) === id)
    if (exp) onSelect(exp)
  }

  if (loading) {
    return (
      <div style={styles.wrapper}>
        <div style={styles.loadingText}>Kísérletek betöltése...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div style={styles.wrapper}>
        <div style={styles.errorText}>{error}</div>
      </div>
    )
  }

  if (!experiments || experiments.length === 0) {
    return (
      <div style={styles.wrapper}>
        <div style={styles.loadingText}>Nincsenek elérhető kísérletek.</div>
      </div>
    )
  }

  const selectedId = selected ? (selected.id || selected.name) : ''
  const nodes = selected?.nodes || selected?.pipeline_nodes || []

  return (
    <div style={styles.wrapper}>
      <select
        style={styles.select}
        value={selectedId}
        onChange={handleChange}
      >
        {experiments.map(exp => {
          const expId = exp.id || exp.name || '?'
          return (
            <option key={expId} value={expId}>
              {exp.name || exp.id || expId}
            </option>
          )
        })}
      </select>

      {selected && (
        <div style={styles.descriptionBox}>
          {selected.description && (
            <div style={styles.descriptionText}>{selected.description}</div>
          )}

          {nodes.length > 0 && (
            <>
              <div style={styles.nodesLabel}>Csomópontok ({nodes.length})</div>
              <div style={styles.nodesList}>
                {nodes.map((node, idx) => {
                  const nodeName = node.name || node.node_name || node.id || `node_${idx}`
                  const nodeModel = node.model || node.llm_model || ''
                  return (
                    <div key={idx} style={styles.nodeItem}>
                      <span style={styles.nodeName}>{nodeName}</span>
                      {nodeModel && <span style={styles.nodeModel}>{nodeModel}</span>}
                    </div>
                  )
                })}
              </div>
            </>
          )}

          {!selected.description && nodes.length === 0 && (
            <div style={styles.descriptionText}>
              ID: {selected.id || selected.name || 'ismeretlen'}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
