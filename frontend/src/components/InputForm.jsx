import React from 'react'

const inputBaseStyle = {
  width: '100%',
  padding: '8px 10px',
  background: '#1a1a1a',
  border: '1px solid #2a2a2a',
  borderRadius: '4px',
  color: '#e0e0e0',
  fontFamily: "'JetBrains Mono', 'Courier New', monospace",
  fontSize: '12px',
  outline: 'none',
  lineHeight: '1.4',
}

const inputDisabledStyle = {
  ...inputBaseStyle,
  background: '#141414',
  color: '#444444',
  cursor: 'not-allowed',
  borderColor: '#1e1e1e',
}

const styles = {
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
  },
  field: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  label: {
    fontSize: '10px',
    fontWeight: '600',
    color: '#555555',
    letterSpacing: '0.1em',
    textTransform: 'uppercase',
  },
  requiredStar: {
    color: '#00ff88',
    marginLeft: '3px',
  },
  textarea: {
    ...inputBaseStyle,
    resize: 'vertical',
    minHeight: '80px',
    lineHeight: '1.6',
  },
  textareaDisabled: {
    ...inputDisabledStyle,
    resize: 'none',
    minHeight: '80px',
    lineHeight: '1.6',
  },
}

function Field({ label, required, children }) {
  return (
    <div style={styles.field}>
      <label style={styles.label}>
        {label}
        {required && <span style={styles.requiredStar}>*</span>}
      </label>
      {children}
    </div>
  )
}

export default function InputForm({ inputData, onChange, disabled }) {
  const handleChange = (key, value) => {
    onChange(prev => ({ ...prev, [key]: value }))
  }

  const inputStyle = disabled ? inputDisabledStyle : inputBaseStyle
  const textareaStyle = disabled ? styles.textareaDisabled : styles.textarea

  return (
    <form style={styles.form} onSubmit={e => e.preventDefault()}>
      <Field label="Cég neve" required>
        <input
          type="text"
          style={inputStyle}
          value={inputData.company_name}
          onChange={e => handleChange('company_name', e.target.value)}
          disabled={disabled}
          placeholder="pl. Acme Kft."
        />
      </Field>

      <Field label="Cég típusa">
        <input
          type="text"
          style={inputStyle}
          value={inputData.company_type}
          onChange={e => handleChange('company_type', e.target.value)}
          disabled={disabled}
          placeholder="pl. IT hardware értékesítő"
        />
      </Field>

      <Field label="Célközönség">
        <input
          type="text"
          style={inputStyle}
          value={inputData.target_audience}
          onChange={e => handleChange('target_audience', e.target.value)}
          disabled={disabled}
          placeholder="pl. Középvezetők"
        />
      </Field>

      <Field label="Cél">
        <input
          type="text"
          style={inputStyle}
          value={inputData.goal}
          onChange={e => handleChange('goal', e.target.value)}
          disabled={disabled}
          placeholder="pl. AI stratégiai gondolkodás fejlesztése"
        />
      </Field>

      <Field label="Kontextus">
        <textarea
          style={textareaStyle}
          value={inputData.context}
          onChange={e => handleChange('context', e.target.value)}
          disabled={disabled}
          placeholder="További kontextus vagy háttérinformáció (opcionális)..."
        />
      </Field>
    </form>
  )
}
