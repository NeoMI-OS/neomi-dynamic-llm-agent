import React, { useState } from 'react'
import SRSBadge from './SRSBadge.jsx'

const styles = {
  card: {
    background: '#1a1a1a',
    border: '1px solid #2a2a2a',
    borderRadius: '6px',
    overflow: 'hidden',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    padding: '10px 14px',
    cursor: 'pointer',
    userSelect: 'none',
  },
  headerLeft: {
    display: 'flex',
    flexDirection: 'column',
    gap: '3px',
    flex: 1,
    minWidth: 0,
  },
  nodeName: {
    fontSize: '12px',
    fontWeight: '700',
    color: '#e0e0e0',
    letterSpacing: '0.03em',
  },
  metaRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    flexWrap: 'wrap',
  },
  metaItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
    fontSize: '10px',
    color: '#555555',
  },
  metaLabel: {
    color: '#3a3a3a',
    letterSpacing: '0.08em',
    textTransform: 'uppercase',
  },
  metaValue: {
    color: '#666666',
  },
  metaValueAccent: {
    color: '#00ff88',
    opacity: 0.8,
  },
  headerRight: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    flexShrink: 0,
  },
  expandIcon: {
    fontSize: '10px',
    color: '#444444',
    transition: 'transform 0.15s',
  },
  contentArea: {
    borderTop: '1px solid #222222',
    padding: '12px 14px',
  },
  contentLabel: {
    fontSize: '10px',
    color: '#3a3a3a',
    letterSpacing: '0.1em',
    textTransform: 'uppercase',
    marginBottom: '8px',
  },
  outputPre: {
    fontSize: '11px',
    color: '#aaaaaa',
    lineHeight: '1.7',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
    background: '#141414',
    border: '1px solid #1e1e1e',
    borderRadius: '3px',
    padding: '10px 12px',
    maxHeight: '400px',
    overflowY: 'auto',
    fontFamily: "'JetBrains Mono', 'Courier New', monospace",
  },
  statusDot: {
    width: '6px',
    height: '6px',
    borderRadius: '50%',
    flexShrink: 0,
  },
}

function formatDuration(durationSeconds) {
  if (durationSeconds === null || durationSeconds === undefined) return null
  const num = parseFloat(durationSeconds)
  if (isNaN(num)) return String(durationSeconds)
  return `${num.toFixed(1)}s`
}

function formatTokens(tokens) {
  if (tokens === null || tokens === undefined) return null
  const num = parseInt(tokens, 10)
  if (isNaN(num)) return String(tokens)
  if (num >= 1000) return `${(num / 1000).toFixed(1)}k tok`
  return `${num} tok`
}

function getNodeStatusColor(trace) {
  if (trace.error) return '#ff4444'
  if (trace.srs_score !== undefined || trace.srs !== undefined) {
    const srs = trace.srs_score ?? trace.srs
    const score = typeof srs === 'object' ? (srs?.total ?? srs?.score) : srs
    if (score >= 70) return '#00ff88'
    if (score >= 40) return '#ffcc00'
    return '#ff6644'
  }
  return '#00ff88'
}

export default function NodeCard({ trace, index }) {
  const [expanded, setExpanded] = useState(false)

  const nodeName = trace.node_name || trace.name || trace.node || `Csomópont ${index + 1}`
  const model = trace.model || trace.llm_model || trace.model_used || ''
  const durRaw = trace.duration_seconds ?? trace.duration ?? trace.elapsed ?? null
  const durMs = trace.duration_ms ?? null
  const durSec = durRaw !== null ? durRaw : (durMs !== null ? durMs / 1000 : null)
  const duration = formatDuration(durSec)

  const tokens = formatTokens(
    trace.token_count ?? trace.tokens ?? trace.total_tokens ??
    (trace.usage?.total_tokens) ?? null
  )

  const srsData = trace.model_evaluation ?? trace.srs_score ?? trace.srs ?? null
  const statusColor = getNodeStatusColor(trace)

  // Get the content output to display
  const outputContent =
    trace.output ||
    trace.content ||
    trace.result ||
    trace.response ||
    trace.text ||
    null

  const hasContent = outputContent !== null && outputContent !== undefined

  return (
    <div style={styles.card}>
      <div
        style={{
          ...styles.header,
          background: expanded ? '#1e1e1e' : '#1a1a1a',
        }}
        onClick={() => hasContent && setExpanded(e => !e)}
        role={hasContent ? 'button' : undefined}
        tabIndex={hasContent ? 0 : undefined}
        onKeyDown={hasContent ? (e) => { if (e.key === 'Enter' || e.key === ' ') setExpanded(x => !x) } : undefined}
      >
        <div
          style={{
            ...styles.statusDot,
            background: statusColor,
            boxShadow: `0 0 6px ${statusColor}55`,
          }}
        />

        <div style={styles.headerLeft}>
          <div style={styles.nodeName}>{nodeName}</div>
          <div style={styles.metaRow}>
            {model && (
              <div style={styles.metaItem}>
                <span style={styles.metaLabel}>model</span>
                <span style={styles.metaValueAccent}>{model}</span>
              </div>
            )}
            {duration && (
              <div style={styles.metaItem}>
                <span style={styles.metaLabel}>idő</span>
                <span style={styles.metaValue}>{duration}</span>
              </div>
            )}
            {tokens && (
              <div style={styles.metaItem}>
                <span style={styles.metaLabel}>tok</span>
                <span style={styles.metaValue}>{tokens}</span>
              </div>
            )}
          </div>
        </div>

        <div style={styles.headerRight}>
          {srsData !== null && <SRSBadge srs={srsData} />}
          {hasContent && (
            <span
              style={{
                ...styles.expandIcon,
                transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)',
                display: 'inline-block',
              }}
            >
              ▶
            </span>
          )}
        </div>
      </div>

      {expanded && hasContent && (
        <div style={styles.contentArea}>
          <div style={styles.contentLabel}>Kimenet</div>
          <pre style={styles.outputPre}>
            {typeof outputContent === 'string'
              ? outputContent
              : JSON.stringify(outputContent, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}
