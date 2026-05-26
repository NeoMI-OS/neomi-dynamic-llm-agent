import React from 'react'
import NodeCard from './NodeCard.jsx'

const styles = {
  wrapper: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  statsRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '16px',
    padding: '8px 12px',
    background: '#141414',
    border: '1px solid #1e1e1e',
    borderRadius: '4px',
    marginBottom: '4px',
  },
  statItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    fontSize: '11px',
  },
  statLabel: {
    color: '#444444',
    letterSpacing: '0.08em',
    textTransform: 'uppercase',
    fontSize: '10px',
  },
  statValue: {
    color: '#888888',
    fontWeight: '600',
  },
  statValueAccent: {
    color: '#00ff88',
    fontWeight: '600',
  },
  emptyText: {
    fontSize: '12px',
    color: '#555555',
    padding: '12px 0',
  },
}

function computeStats(traces) {
  let totalDuration = 0
  let totalTokens = 0
  let hasDuration = false
  let hasTokens = false

  traces.forEach(t => {
    const durRaw = t.duration_seconds ?? t.duration ?? t.elapsed ?? null
    const durMs = t.duration_ms ?? null
    const dur = durRaw !== null ? durRaw : (durMs !== null ? durMs / 1000 : null)
    if (dur !== null && dur !== undefined) {
      totalDuration += parseFloat(dur) || 0
      hasDuration = true
    }
    const tok =
      t.token_count ?? t.tokens ?? t.total_tokens ?? t.usage?.total_tokens ?? null
    if (tok !== null && tok !== undefined) {
      totalTokens += parseInt(tok, 10) || 0
      hasTokens = true
    }
  })

  return {
    count: traces.length,
    totalDuration: hasDuration ? totalDuration : null,
    totalTokens: hasTokens ? totalTokens : null,
  }
}

export default function PipelineTrace({ traces }) {
  if (!traces || traces.length === 0) {
    return <div style={styles.emptyText}>Nincsenek csomópont nyomok.</div>
  }

  const stats = computeStats(traces)

  return (
    <div style={styles.wrapper}>
      {/* Summary stats bar */}
      <div style={styles.statsRow}>
        <div style={styles.statItem}>
          <span style={styles.statLabel}>csomópontok</span>
          <span style={styles.statValueAccent}>{stats.count}</span>
        </div>
        {stats.totalDuration !== null && (
          <div style={styles.statItem}>
            <span style={styles.statLabel}>össz. idő</span>
            <span style={styles.statValue}>{stats.totalDuration.toFixed(1)}s</span>
          </div>
        )}
        {stats.totalTokens !== null && (
          <div style={styles.statItem}>
            <span style={styles.statLabel}>össz. token</span>
            <span style={styles.statValue}>
              {stats.totalTokens >= 1000
                ? `${(stats.totalTokens / 1000).toFixed(1)}k`
                : stats.totalTokens}
            </span>
          </div>
        )}
      </div>

      {/* Node cards */}
      {traces.map((trace, idx) => (
        <NodeCard key={idx} trace={trace} index={idx} />
      ))}
    </div>
  )
}
