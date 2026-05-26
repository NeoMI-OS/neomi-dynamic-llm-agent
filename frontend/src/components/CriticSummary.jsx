import React from 'react'

function getMaturityColor(score) {
  if (score >= 70) return '#00ff88'
  if (score >= 40) return '#ffcc00'
  return '#ff4444'
}

function getMaturityLabel(score) {
  if (score >= 80) return 'Kiváló'
  if (score >= 60) return 'Jó'
  if (score >= 40) return 'Közepes'
  if (score >= 20) return 'Gyenge'
  return 'Kritikus'
}

const styles = {
  card: {
    background: '#1a1a1a',
    border: '1px solid #2a2a2a',
    borderRadius: '6px',
    overflow: 'hidden',
  },
  scoreSection: {
    display: 'flex',
    alignItems: 'center',
    gap: '20px',
    padding: '20px 20px 16px',
    borderBottom: '1px solid #222222',
  },
  scoreCircle: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '2px',
    flexShrink: 0,
  },
  scoreNumber: {
    fontSize: '48px',
    fontWeight: '700',
    lineHeight: '1',
    letterSpacing: '-0.02em',
  },
  scoreMax: {
    fontSize: '11px',
    color: '#3a3a3a',
  },
  scoreInfo: {
    flex: 1,
    minWidth: 0,
  },
  maturityLabel: {
    fontSize: '14px',
    fontWeight: '700',
    letterSpacing: '0.05em',
    marginBottom: '4px',
  },
  maturitySub: {
    fontSize: '11px',
    color: '#555555',
    letterSpacing: '0.05em',
  },
  barsSection: {
    padding: '16px 20px',
    borderBottom: '1px solid #1e1e1e',
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
  },
  barRow: {
    display: 'flex',
    flexDirection: 'column',
    gap: '5px',
  },
  barHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  barLabel: {
    fontSize: '11px',
    color: '#888888',
    letterSpacing: '0.05em',
  },
  barValue: {
    fontSize: '11px',
    fontWeight: '600',
    color: '#aaaaaa',
  },
  barTrack: {
    height: '4px',
    background: '#222222',
    borderRadius: '2px',
    overflow: 'hidden',
  },
  feedbackSection: {
    padding: '16px 20px',
  },
  feedbackLabel: {
    fontSize: '10px',
    color: '#444444',
    letterSpacing: '0.1em',
    textTransform: 'uppercase',
    marginBottom: '8px',
  },
  feedbackText: {
    fontSize: '12px',
    color: '#999999',
    lineHeight: '1.7',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
  },
}

function ProgressBar({ label, value, maxValue = 100, color }) {
  const pct = Math.min(100, Math.max(0, (value / maxValue) * 100))
  const barColor = color || getMaturityColor(value)
  const displayValue = typeof value === 'number' ? value.toFixed(1) : value

  return (
    <div style={styles.barRow}>
      <div style={styles.barHeader}>
        <span style={styles.barLabel}>{label}</span>
        <span style={{ ...styles.barValue, color: barColor }}>{displayValue}</span>
      </div>
      <div style={styles.barTrack}>
        <div
          style={{
            height: '100%',
            width: `${pct}%`,
            background: barColor,
            borderRadius: '2px',
            transition: 'width 0.3s ease',
          }}
        />
      </div>
    </div>
  )
}

export default function CriticSummary({ critique }) {
  if (!critique) return null

  // Normalize fields — handle various API response shapes
  const maturityScore =
    critique.maturity_score ??
    critique.overall_score ??
    critique.score ??
    critique.total ??
    null

  const extractScore = (val) => {
    if (val === null || val === undefined) return null
    if (typeof val === 'number') return val
    if (typeof val === 'object') return val.score ?? val.value ?? null
    return null
  }

  const relevance = extractScore(
    critique.relevance ?? critique.relevance_score ?? critique.categories?.relevance
  )

  const depth = extractScore(
    critique.depth ?? critique.depth_score ?? critique.categories?.depth
  )

  const applicability = extractScore(
    critique.applicability ?? critique.applicability_score ?? critique.categories?.applicability
  )

  const feedback =
    critique.overall_feedback ??
    critique.feedback ??
    critique.summary ??
    critique.critique ??
    critique.evaluation ??
    null

  const hasScore = maturityScore !== null && maturityScore !== undefined
  const hasBars = relevance !== null || depth !== null || applicability !== null
  const hasFeedback = feedback !== null

  if (!hasScore && !hasBars && !hasFeedback) {
    // Fallback: show raw JSON
    return (
      <div style={styles.card}>
        <div style={styles.feedbackSection}>
          <div style={styles.feedbackLabel}>Nyers adat</div>
          <pre style={{ ...styles.feedbackText, fontSize: '11px', color: '#666666' }}>
            {JSON.stringify(critique, null, 2)}
          </pre>
        </div>
      </div>
    )
  }

  const color = hasScore ? getMaturityColor(maturityScore) : '#888888'
  const label = hasScore ? getMaturityLabel(maturityScore) : 'Ismeretlen'
  const displayScore = hasScore
    ? (typeof maturityScore === 'number' ? maturityScore.toFixed(1) : maturityScore)
    : '—'

  return (
    <div style={styles.card}>
      {/* Maturity score */}
      {hasScore && (
        <div style={styles.scoreSection}>
          <div style={styles.scoreCircle}>
            <span style={{ ...styles.scoreNumber, color }}>{displayScore}</span>
            <span style={styles.scoreMax}>/ 100</span>
          </div>
          <div style={styles.scoreInfo}>
            <div style={{ ...styles.maturityLabel, color }}>{label}</div>
            <div style={styles.maturitySub}>Érettségi pontszám</div>
          </div>
        </div>
      )}

      {/* Category bars */}
      {hasBars && (
        <div style={styles.barsSection}>
          {relevance !== null && (
            <ProgressBar label="Relevancia" value={relevance} />
          )}
          {depth !== null && (
            <ProgressBar label="Mélység" value={depth} />
          )}
          {applicability !== null && (
            <ProgressBar label="Alkalmazhatóság" value={applicability} />
          )}
        </div>
      )}

      {/* Feedback text */}
      {hasFeedback && (
        <div style={styles.feedbackSection}>
          <div style={styles.feedbackLabel}>Visszajelzés</div>
          <div style={styles.feedbackText}>
            {typeof feedback === 'string' ? feedback : JSON.stringify(feedback, null, 2)}
          </div>
        </div>
      )}
    </div>
  )
}
