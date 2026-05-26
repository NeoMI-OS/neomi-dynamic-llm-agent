import React, { useState } from 'react'

function getScoreColor(score) {
  if (score >= 70) return '#00ff88'
  if (score >= 40) return '#ffcc00'
  return '#ff4444'
}

function getScoreBg(score) {
  if (score >= 70) return 'rgba(0, 255, 136, 0.08)'
  if (score >= 40) return 'rgba(255, 204, 0, 0.08)'
  return 'rgba(255, 68, 68, 0.08)'
}

function getScoreBorder(score) {
  if (score >= 70) return 'rgba(0, 255, 136, 0.25)'
  if (score >= 40) return 'rgba(255, 204, 0, 0.25)'
  return 'rgba(255, 68, 68, 0.25)'
}

const styles = {
  wrapper: {
    position: 'relative',
    display: 'inline-block',
  },
  badge: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '4px',
    padding: '2px 7px',
    borderRadius: '3px',
    fontSize: '11px',
    fontWeight: '600',
    fontFamily: "'JetBrains Mono', 'Courier New', monospace",
    cursor: 'default',
    userSelect: 'none',
    letterSpacing: '0.03em',
  },
  tooltip: {
    position: 'absolute',
    bottom: 'calc(100% + 6px)',
    left: '50%',
    transform: 'translateX(-50%)',
    zIndex: 100,
    background: '#1a1a1a',
    border: '1px solid #2a2a2a',
    borderRadius: '4px',
    padding: '10px 12px',
    minWidth: '180px',
    boxShadow: '0 4px 16px rgba(0,0,0,0.6)',
    pointerEvents: 'none',
  },
  tooltipTitle: {
    fontSize: '10px',
    color: '#555555',
    letterSpacing: '0.1em',
    textTransform: 'uppercase',
    marginBottom: '8px',
  },
  tooltipRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: '5px',
  },
  tooltipLabel: {
    fontSize: '11px',
    color: '#888888',
  },
  tooltipValue: {
    fontSize: '11px',
    fontWeight: '600',
  },
  tooltipArrow: {
    position: 'absolute',
    top: '100%',
    left: '50%',
    transform: 'translateX(-50%)',
    width: 0,
    height: 0,
    borderLeft: '5px solid transparent',
    borderRight: '5px solid transparent',
    borderTop: '5px solid #2a2a2a',
  },
}

export default function SRSBadge({ srs }) {
  const [hovered, setHovered] = useState(false)

  if (!srs && srs !== 0) return null

  // srs can be a number or an object with { total, knowledge, reasoning, usability }
  let total, knowledge, reasoning, usability

  if (typeof srs === 'number') {
    total = srs
  } else if (typeof srs === 'object' && srs !== null) {
    total = srs.service_readiness_score ?? srs.total ?? srs.score ?? srs.srs_score ?? null
    knowledge = srs.knowledge_score ?? srs.knowledge ?? null
    reasoning = srs.reasoning_score ?? srs.reasoning ?? null
    usability = srs.usability_score ?? srs.usability ?? null
  }

  if (total === null || total === undefined) return null

  const color = getScoreColor(total)
  const bg = getScoreBg(total)
  const border = getScoreBorder(total)
  const displayScore = typeof total === 'number' ? total.toFixed(1) : total

  const hasBreakdown = knowledge !== null || reasoning !== null || usability !== null

  return (
    <div
      style={styles.wrapper}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div
        style={{
          ...styles.badge,
          color,
          background: bg,
          border: `1px solid ${border}`,
        }}
      >
        <span style={{ opacity: 0.7, fontSize: '10px' }}>SRS</span>
        <span>{displayScore}</span>
      </div>

      {hovered && hasBreakdown && (
        <div style={styles.tooltip}>
          <div style={styles.tooltipTitle}>SRS Bontás</div>

          <div style={styles.tooltipRow}>
            <span style={styles.tooltipLabel}>Összesen</span>
            <span style={{ ...styles.tooltipValue, color }}>{displayScore}</span>
          </div>

          {knowledge !== null && (
            <div style={styles.tooltipRow}>
              <span style={styles.tooltipLabel}>Tudás</span>
              <span style={{ ...styles.tooltipValue, color: getScoreColor(knowledge) }}>
                {typeof knowledge === 'number' ? knowledge.toFixed(1) : knowledge}
              </span>
            </div>
          )}

          {reasoning !== null && (
            <div style={styles.tooltipRow}>
              <span style={styles.tooltipLabel}>Érvelés</span>
              <span style={{ ...styles.tooltipValue, color: getScoreColor(reasoning) }}>
                {typeof reasoning === 'number' ? reasoning.toFixed(1) : reasoning}
              </span>
            </div>
          )}

          {usability !== null && (
            <div style={styles.tooltipRow}>
              <span style={styles.tooltipLabel}>Használhatóság</span>
              <span style={{ ...styles.tooltipValue, color: getScoreColor(usability) }}>
                {typeof usability === 'number' ? usability.toFixed(1) : usability}
              </span>
            </div>
          )}

          <div style={styles.tooltipArrow} />
        </div>
      )}
    </div>
  )
}
