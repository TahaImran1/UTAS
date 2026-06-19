import React, { useState, useEffect } from 'react'
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import TopBar from './components/TopBar'
import { getAuthStatus } from './api/client'

// Pages
import Dashboard from './pages/Dashboard'
import Machines from './pages/Machines'
import Companies from './pages/Companies'
import Employees from './pages/Employees'
import AttendanceLogs from './pages/AttendanceLogs'
import ServerStatus from './pages/ServerStatus'
import HealthDashboard from './pages/HealthDashboard'
import DatabaseSettings from './pages/DatabaseSettings'
import Login from './pages/Login'
import InitializeAuth from './pages/InitializeAuth'
import MasterSettings from './pages/MasterSettings'

export default function App() {
  const [initialized, setInitialized] = useState(null)
  const [lockout, setLockout] = useState(false)
  const [isLoggedIn, setIsLoggedIn] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    checkAuth()
  }, [])

  const checkAuth = async () => {
    try {
      const res = await getAuthStatus()
      setInitialized(res.data.initialized)
      setLockout(res.data.lockout || false)
      setIsLoggedIn(res.data.logged_in)
    } catch (err) {
      console.error('Auth check failed:', err)
      // Default fallback
      setInitialized(true)
      setLockout(false)
      setIsLoggedIn(false)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div style={{ height: '100vh', width: '100vw', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', background: '#0f172a', color: '#f1f5f9', fontFamily: 'sans-serif' }}>
        <div style={{ width: '40px', height: '40px', border: '3px solid rgba(255,255,255,0.1)', borderTopColor: '#3b82f6', borderRadius: '50%', animation: 'spin 1s linear infinite', marginBottom: '15px' }}></div>
        <span>Verifying Security Status...</span>
        <style>{`@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }`}</style>
      </div>
    )
  }

  if (lockout) {
    return (
      <div style={{
        height: '100vh',
        width: '100vw',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#0f172a',
        color: '#f8fafc',
        fontFamily: "'Outfit', 'Inter', sans-serif",
        padding: '20px',
        boxSizing: 'border-box'
      }}>
        <div style={{
          maxWidth: '500px',
          width: '100%',
          background: 'rgba(30, 41, 59, 0.7)',
          backdropFilter: 'blur(10px)',
          border: '1px solid rgba(239, 68, 68, 0.2)',
          borderRadius: '16px',
          padding: '40px',
          textAlign: 'center',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)'
        }}>
          <div style={{
            width: '64px',
            height: '64px',
            background: 'rgba(239, 68, 68, 0.1)',
            borderRadius: '50%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 24px',
            border: '1px solid rgba(239, 68, 68, 0.3)'
          }}>
            <svg style={{ width: '32px', height: '32px', color: '#ef4444' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
          <h2 style={{ fontSize: '24px', fontWeight: '700', marginBottom: '12px', color: '#f8fafc', letterSpacing: '-0.025em' }}>Security Lockout</h2>
          <p style={{ color: '#94a3b8', fontSize: '14px', lineHeight: '1.6', marginBottom: '24px' }}>
            The master security configuration for this installation has been corrupted or tampered with.
          </p>
          <div style={{
            background: 'rgba(15, 23, 42, 0.5)',
            border: '1px solid rgba(255, 255, 255, 0.05)',
            borderRadius: '12px',
            padding: '16px',
            textAlign: 'left',
            marginBottom: '24px',
            fontSize: '13px',
            lineHeight: '1.5',
            color: '#cbd5e1'
          }}>
            <strong style={{ color: '#ef4444', display: 'block', marginBottom: '6px' }}>Access Locked</strong>
            To protect your configured machines, database connections, and company profiles, administration access has been locked.
          </div>
          <p style={{ color: '#64748b', fontSize: '12px', lineHeight: '1.5' }}>
            Please contact your system administrator or support to restore your security configuration.
          </p>
        </div>
      </div>
    )
  }

  if (!initialized) {
    return (
      <InitializeAuth onInitialized={() => { setInitialized(true); setIsLoggedIn(true); }} />
    )
  }

  return (
    <HashRouter>
      <div className="app-layout">
        <Sidebar isLoggedIn={isLoggedIn} onLogout={() => setIsLoggedIn(false)} />
        <div className="main-area">
          <TopBar isLoggedIn={isLoggedIn} onLogout={() => setIsLoggedIn(false)} />
          <div className="page-content">
            <Routes>
              <Route path="/" element={<Dashboard isLoggedIn={isLoggedIn} />} />
              <Route path="/machines" element={<Machines isLoggedIn={isLoggedIn} />} />
              <Route path="/server" element={isLoggedIn ? <ServerStatus /> : <Navigate to="/login" replace />} />
              <Route path="/companies" element={isLoggedIn ? <Companies /> : <Navigate to="/login" replace />} />
              <Route path="/employees" element={isLoggedIn ? <Employees /> : <Navigate to="/login" replace />} />
              <Route path="/logs" element={isLoggedIn ? <AttendanceLogs /> : <Navigate to="/login" replace />} />
              <Route path="/health" element={isLoggedIn ? <HealthDashboard /> : <Navigate to="/login" replace />} />
              <Route path="/database" element={isLoggedIn ? <DatabaseSettings /> : <Navigate to="/login" replace />} />
              <Route path="/master-settings" element={isLoggedIn ? <MasterSettings /> : <Navigate to="/login" replace />} />
              <Route path="/login" element={<Login onLogin={() => setIsLoggedIn(true)} />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </div>
        </div>
      </div>
    </HashRouter>
  )
}

