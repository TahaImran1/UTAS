import React, { useState, useEffect } from 'react'
import { MdLock, MdCheck, MdSecurity, MdSystemUpdateAlt, MdRefresh } from 'react-icons/md'
import { changePassword } from '../api/client'
import toast from 'react-hot-toast'

export default function MasterSettings() {
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)

  // Update State
  const [updateStatus, setUpdateStatus] = useState('idle') // idle, checking, available, not-available, downloading, downloaded, error
  const [updateVersion, setUpdateVersion] = useState('')
  const [downloadPercent, setDownloadPercent] = useState(0)
  const [errorMsg, setErrorMsg] = useState('')

  const isElectron = !!window.electronAPI
  const [currentVersion, setCurrentVersion] = useState('')

  useEffect(() => {
    if (isElectron && window.electronAPI?.getAppVersion) {
      window.electronAPI.getAppVersion().then(v => setCurrentVersion(v))
    }
  }, [isElectron])

  useEffect(() => {
    if (!isElectron) return

    const unsubscribeStatus = window.electronAPI.onUpdaterStatus((status, detail) => {
      setUpdateStatus(status)
      if (status === 'available') {
        setUpdateVersion(detail || '')
      } else if (status === 'downloaded') {
        setUpdateVersion(detail || '')
      } else if (status === 'error') {
        setErrorMsg(detail || 'An unknown error occurred during update.')
      }
    })

    const unsubscribeProgress = window.electronAPI.onUpdaterDownloadProgress((percent) => {
      setUpdateStatus('downloading')
      setDownloadPercent(Math.round(percent))
    })

    return () => {
      unsubscribeStatus()
      unsubscribeProgress()
    }
  }, [isElectron])

  const handleCheckUpdates = () => {
    if (isElectron) {
      setUpdateStatus('checking')
      window.electronAPI.checkForUpdates()
    }
  }

  const handleRestartInstall = () => {
    if (isElectron) {
      window.electronAPI.restartAndInstall()
    }
  }

  // Complexity states
  const hasMinLength = newPassword.length >= 8
  const hasUpper = /[A-Z]/.test(newPassword)
  const hasLower = /[a-z]/.test(newPassword)
  const hasNumber = /\d/.test(newPassword)
  const hasSpecial = /[!@#$%^&*(),.?":{}|<>]/.test(newPassword)
  const passwordsMatch = newPassword && newPassword === confirmPassword
  const isStrong = hasMinLength && hasUpper && hasLower && hasNumber && hasSpecial

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!isStrong) {
      toast.error('New password does not meet all security requirements.')
      return
    }
    if (!passwordsMatch) {
      toast.error('Passwords do not match.')
      return
    }

    setLoading(true)
    try {
      const res = await changePassword(oldPassword, newPassword)
      if (res.data.status === 'success') {
        toast.success('Master password changed successfully!')
        setOldPassword('')
        setNewPassword('')
        setConfirmPassword('')
      } else {
        toast.error('Failed to change password.')
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to change password.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="settings-page">
      <div className="page-header" style={{ marginBottom: '25px' }}>
        <h1 style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <MdSecurity /> Master User Settings
        </h1>
        <p className="subtitle" style={{ color: 'var(--color-text-muted)', fontSize: '0.9rem', marginTop: '4px' }}>
          Configure security settings and change your master password.
        </p>
      </div>

      <div className="card" style={{ maxWidth: '600px', padding: '30px' }}>
        <h3 style={{ marginBottom: '20px', fontSize: '1.2rem', fontWeight: 600 }}>Change Master Password</h3>
        
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div className="form-group">
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', fontWeight: 500, marginBottom: '6px' }}>
              <MdLock /> Current Password
            </label>
            <input 
              type="password" 
              placeholder="Enter current password" 
              value={oldPassword} 
              onChange={e => setOldPassword(e.target.value)}
              required
              style={{
                padding: '10px 12px',
                borderRadius: '6px',
                border: '1px solid var(--color-border)',
                background: 'var(--color-input-bg, rgba(0,0,0,0.02))',
                color: 'var(--color-text)',
                outline: 'none'
              }}
            />
          </div>

          <div className="form-group">
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', fontWeight: 500, marginBottom: '6px' }}>
              <MdLock /> New Password
            </label>
            <input 
              type="password" 
              placeholder="Create a highly secure password" 
              value={newPassword} 
              onChange={e => setNewPassword(e.target.value)}
              required
              style={{
                padding: '10px 12px',
                borderRadius: '6px',
                border: '1px solid var(--color-border)',
                background: 'var(--color-input-bg, rgba(0,0,0,0.02))',
                color: 'var(--color-text)',
                outline: 'none'
              }}
            />
          </div>

          {newPassword && (
            <div className="strength-checklist" style={{
              background: 'var(--color-bg-hover, rgba(0,0,0,0.01))',
              padding: '15px',
              borderRadius: '8px',
              border: '1px solid var(--color-border)',
              display: 'flex',
              flexDirection: 'column',
              gap: '8px'
            }}>
              <p style={{ margin: '0 0 6px 0', fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>Password Requirements:</p>
              <div className={`checklist-item ${hasMinLength ? 'valid' : ''}`} style={{ fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '6px', color: hasMinLength ? 'var(--color-success, #10b981)' : 'var(--color-text-muted)' }}>
                <span className="dot" style={{ width: '6px', height: '6px', borderRadius: '50%', background: hasMinLength ? 'var(--color-success, #10b981)' : '#ef4444' }}></span> At least 8 characters
              </div>
              <div className={`checklist-item ${hasUpper ? 'valid' : ''}`} style={{ fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '6px', color: hasUpper ? 'var(--color-success, #10b981)' : 'var(--color-text-muted)' }}>
                <span className="dot" style={{ width: '6px', height: '6px', borderRadius: '50%', background: hasUpper ? 'var(--color-success, #10b981)' : '#ef4444' }}></span> At least 1 uppercase letter (A-Z)
              </div>
              <div className={`checklist-item ${hasLower ? 'valid' : ''}`} style={{ fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '6px', color: hasLower ? 'var(--color-success, #10b981)' : 'var(--color-text-muted)' }}>
                <span className="dot" style={{ width: '6px', height: '6px', borderRadius: '50%', background: hasLower ? 'var(--color-success, #10b981)' : '#ef4444' }}></span> At least 1 lowercase letter (a-z)
              </div>
              <div className={`checklist-item ${hasNumber ? 'valid' : ''}`} style={{ fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '6px', color: hasNumber ? 'var(--color-success, #10b981)' : 'var(--color-text-muted)' }}>
                <span className="dot" style={{ width: '6px', height: '6px', borderRadius: '50%', background: hasNumber ? 'var(--color-success, #10b981)' : '#ef4444' }}></span> At least 1 number (0-9)
              </div>
              <div className={`checklist-item ${hasSpecial ? 'valid' : ''}`} style={{ fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '6px', color: hasSpecial ? 'var(--color-success, #10b981)' : 'var(--color-text-muted)' }}>
                <span className="dot" style={{ width: '6px', height: '6px', borderRadius: '50%', background: hasSpecial ? 'var(--color-success, #10b981)' : '#ef4444' }}></span> At least 1 special character (!@#$...)
              </div>
            </div>
          )}

          <div className="form-group">
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', fontWeight: 500, marginBottom: '6px' }}>
              <MdLock /> Confirm New Password
            </label>
            <input 
              type="password" 
              placeholder="Confirm new password" 
              value={confirmPassword} 
              disabled={!isStrong}
              onChange={e => setConfirmPassword(e.target.value)}
              required
              style={{
                padding: '10px 12px',
                borderRadius: '6px',
                border: '1px solid var(--color-border)',
                background: 'var(--color-input-bg, rgba(0,0,0,0.02))',
                color: 'var(--color-text)',
                outline: 'none'
              }}
            />
            {confirmPassword && (
              <p style={{ fontSize: '0.75rem', margin: '4px 0 0 0', fontWeight: 500, color: passwordsMatch ? 'var(--color-success, #10b981)' : '#ef4444' }}>
                {passwordsMatch ? '✓ Passwords match' : '✗ Passwords do not match'}
              </p>
            )}
          </div>

          <button 
            type="submit" 
            className="btn btn-primary" 
            disabled={loading || !isStrong || !passwordsMatch}
            style={{ padding: '12px', fontWeight: 600, fontSize: '0.9rem', marginTop: '10px' }}
          >
            {loading ? 'Changing Password...' : 'Update Password'}
          </button>
        </form>
      </div>

      {/* Auto Updates Card */}
      {isElectron && (
        <div className="card" style={{ maxWidth: '600px', padding: '30px', marginTop: '30px' }}>
          <h3 style={{ marginBottom: '10px', fontSize: '1.2rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <MdSystemUpdateAlt /> Application Updates
          </h3>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem', marginBottom: '20px' }}>
            Check for new versions and install updates directly from the update server.{currentVersion && <span> Current Version: <strong>v{currentVersion}</strong></span>}
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
            <div style={{
              background: 'var(--color-bg-hover, rgba(0,0,0,0.01))',
              padding: '15px',
              borderRadius: '8px',
              border: '1px solid var(--color-border)',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <span style={{ fontSize: '0.9rem', fontWeight: 500 }}>Status: </span>
                  <span style={{ 
                    fontSize: '0.9rem', 
                    fontWeight: 600,
                    color: updateStatus === 'error' ? '#ef4444' : 
                           updateStatus === 'downloaded' ? 'var(--color-success, #10b981)' :
                           updateStatus === 'available' || updateStatus === 'downloading' ? '#3b82f6' : 'var(--color-text-muted)'
                  }}>
                    {updateStatus === 'idle' && 'Up to date'}
                    {updateStatus === 'checking' && 'Checking for updates...'}
                    {updateStatus === 'available' && `Update available (v${updateVersion})`}
                    {updateStatus === 'not-available' && 'You are running the latest version'}
                    {updateStatus === 'downloading' && `Downloading update (${downloadPercent}%)`}
                    {updateStatus === 'downloaded' && `Ready to install (v${updateVersion})`}
                    {updateStatus === 'error' && 'Failed to fetch updates'}
                  </span>
                </div>
                
                {(updateStatus === 'idle' || updateStatus === 'not-available' || updateStatus === 'error') && (
                  <button 
                    onClick={handleCheckUpdates}
                    className="btn btn-secondary"
                    style={{ padding: '6px 12px', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '4px' }}
                  >
                    <MdRefresh /> Check Now
                  </button>
                )}
              </div>

              {updateStatus === 'downloading' && (
                <div style={{ width: '100%', background: 'var(--color-border)', height: '6px', borderRadius: '3px', marginTop: '10px', overflow: 'hidden' }}>
                  <div style={{ width: `${downloadPercent}%`, background: '#3b82f6', height: '100%', transition: 'width 0.2s ease' }} />
                </div>
              )}

              {updateStatus === 'error' && (
                <p style={{ color: '#ef4444', fontSize: '0.75rem', margin: '8px 0 0 0' }}>
                  {errorMsg}
                </p>
              )}
            </div>

            {updateStatus === 'downloaded' && (
              <button 
                onClick={handleRestartInstall}
                className="btn btn-success"
                style={{ padding: '10px', fontWeight: 600, fontSize: '0.85rem', width: '100%', background: 'var(--color-success, #10b981)', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }}
              >
                Restart & Apply Update
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
