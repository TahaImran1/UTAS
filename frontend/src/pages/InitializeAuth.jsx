import React, { useState } from 'react'
import { MdLock, MdFingerprint } from 'react-icons/md'
import { initializeAuth } from '../api/client'
import toast from 'react-hot-toast'

export default function InitializeAuth({ onInitialized }) {
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)

  // Complexity states
  const hasMinLength = password.length >= 8
  const hasUpper = /[A-Z]/.test(password)
  const hasLower = /[a-z]/.test(password)
  const hasNumber = /\d/.test(password)
  const hasSpecial = /[!@#$%^&*(),.?":{}|<>]/.test(password)
  const passwordsMatch = password && password === confirmPassword
  const isStrong = hasMinLength && hasUpper && hasLower && hasNumber && hasSpecial

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!isStrong) {
      toast.error('Password does not meet all security requirements.')
      return
    }
    if (!passwordsMatch) {
      toast.error('Passwords do not match.')
      return
    }

    setLoading(true)
    try {
      const res = await initializeAuth(password)
      if (res.data.status === 'success' || res.data.access_token) {
        localStorage.setItem('utas_token', res.data.access_token)
        toast.success('Master password configured successfully!')
        onInitialized()
      } else {
        toast.error('Failed to configure master password.')
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Initialization failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="init-container">
      <div className="init-card">
        <div className="init-header">
          <div className="logo-circle"><MdFingerprint size={32} /></div>
          <h1>Initialize UTAS Setup</h1>
          <p>Enforce Master Password protection immediately after installation.</p>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label><MdLock /> Set Master Password</label>
            <input 
              type="password" 
              placeholder="Create a highly secure password" 
              value={password} 
              onChange={e => setPassword(e.target.value)}
              required
            />
          </div>

          <div className="strength-checklist">
            <div className={`checklist-item ${hasMinLength ? 'valid' : ''}`}>
              <span className="dot"></span> At least 8 characters
            </div>
            <div className={`checklist-item ${hasUpper ? 'valid' : ''}`}>
              <span className="dot"></span> At least 1 uppercase letter (A-Z)
            </div>
            <div className={`checklist-item ${hasLower ? 'valid' : ''}`}>
              <span className="dot"></span> At least 1 lowercase letter (a-z)
            </div>
            <div className={`checklist-item ${hasNumber ? 'valid' : ''}`}>
              <span className="dot"></span> At least 1 number (0-9)
            </div>
            <div className={`checklist-item ${hasSpecial ? 'valid' : ''}`}>
              <span className="dot"></span> At least 1 special character (!@#$...)
            </div>
          </div>

          <div className="form-group" style={{marginTop: '15px'}}>
            <label><MdLock /> Confirm Master Password</label>
            <input 
              type="password" 
              placeholder="Confirm password" 
              value={confirmPassword} 
              disabled={!isStrong}
              onChange={e => setConfirmPassword(e.target.value)}
              required
            />
            {confirmPassword && (
              <p className={`match-indicator ${passwordsMatch ? 'valid' : 'invalid'}`}>
                {passwordsMatch ? '✓ Passwords match' : '✗ Passwords do not match'}
              </p>
            )}
          </div>

          <button 
            type="submit" 
            className="btn btn-primary init-btn" 
            disabled={loading || !isStrong || !passwordsMatch}
          >
            {loading ? 'Configuring Security...' : 'Complete Security Setup'}
          </button>
        </form>
      </div>

      <style jsx>{`
        .init-container {
          height: 100vh;
          width: 100vw;
          display: flex;
          align-items: center;
          justify-content: center;
          background: radial-gradient(circle at top left, #1e3a8a, #0f172a);
          font-family: 'Inter', sans-serif;
          color: #f1f5f9;
        }
        .init-card {
          width: 440px;
          background: rgba(30, 41, 59, 0.7);
          padding: 40px;
          border-radius: 16px;
          backdrop-filter: blur(16px);
          box-shadow: 0 20px 40px rgba(0,0,0,0.3);
          border: 1px solid rgba(255,255,255,0.1);
        }
        .init-header {
          text-align: center;
          margin-bottom: 25px;
        }
        .logo-circle {
          width: 64px;
          height: 64px;
          background: linear-gradient(135deg, #3b82f6, #1d4ed8);
          color: white;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          margin: 0 auto 15px;
          box-shadow: 0 4px 15px rgba(59, 130, 246, 0.4);
        }
        .init-header h1 {
          margin: 0;
          font-size: 1.6rem;
          font-weight: 700;
        }
        .init-header p {
          color: #94a3b8;
          font-size: 0.85rem;
          margin-top: 8px;
          line-height: 1.4;
        }
        .form-group {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }
        .form-group label {
          font-size: 0.85rem;
          color: #cbd5e1;
          display: flex;
          align-items: center;
          gap: 6px;
          font-weight: 500;
        }
        .form-group input {
          padding: 12px;
          border-radius: 8px;
          border: 1px solid rgba(255,255,255,0.15);
          background: rgba(15, 23, 42, 0.6);
          color: white;
          font-size: 0.95rem;
          outline: none;
          transition: all 0.2s ease;
        }
        .form-group input:focus {
          border-color: #3b82f6;
          box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.25);
        }
        .strength-checklist {
          margin-top: 12px;
          background: rgba(15, 23, 42, 0.4);
          padding: 12px;
          border-radius: 8px;
          border: 1px solid rgba(255,255,255,0.05);
          display: flex;
          flex-direction: column;
          gap: 6px;
        }
        .checklist-item {
          font-size: 0.75rem;
          color: #94a3b8;
          display: flex;
          align-items: center;
          gap: 8px;
          transition: color 0.2s ease;
        }
        .checklist-item .dot {
          width: 6px;
          height: 6px;
          border-radius: 50%;
          background: #ef4444;
          display: inline-block;
          transition: all 0.2s ease;
        }
        .checklist-item.valid {
          color: #34d399;
        }
        .checklist-item.valid .dot {
          background: #34d399;
          box-shadow: 0 0 6px #34d399;
        }
        .match-indicator {
          font-size: 0.75rem;
          margin: 4px 0 0 0;
          font-weight: 500;
        }
        .match-indicator.valid {
          color: #34d399;
        }
        .match-indicator.invalid {
          color: #fb7185;
        }
        .init-btn {
          width: 100%;
          margin-top: 25px;
          padding: 12px;
          font-size: 0.95rem;
          font-weight: 600;
          border-radius: 8px;
          background: #3b82f6;
          border: none;
          color: white;
          cursor: pointer;
          transition: all 0.2s ease;
        }
        .init-btn:hover:not(:disabled) {
          background: #2563eb;
          transform: translateY(-1px);
        }
        .init-btn:disabled {
          background: rgba(255,255,255,0.1);
          color: #64748b;
          cursor: not-allowed;
        }
      `}</style>
    </div>
  )
}
