import React from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { 
  MdDashboard, MdFingerprint, MdBusiness, MdPeople, MdBarChart, 
  MdSettingsInputComponent, MdAnalytics, MdStorage, MdLock, MdSettings, MdLogout 
} from 'react-icons/md'
import { logout as apiLogout } from '../api/client'
import toast from 'react-hot-toast'

export default function Sidebar({ isLoggedIn, onLogout }) {
  const location = useLocation()
  const navigate = useNavigate()
  const [version, setVersion] = React.useState('')

  React.useEffect(() => {
    if (window.electronAPI?.getAppVersion) {
      window.electronAPI.getAppVersion().then(v => setVersion(v))
    }
  }, [])

  const navItems = [
    { path: '/',         icon: <MdDashboard />,    label: 'Dashboard', isProtected: false },
    { path: '/machines', icon: <MdFingerprint />,  label: 'Machines', isProtected: false },
    { path: '/server',   icon: <MdSettingsInputComponent />, label: 'Server Engine', isProtected: true },
    { path: '/companies',icon: <MdBusiness />,     label: 'Companies', isProtected: true },
    { path: '/employees',icon: <MdPeople />,       label: 'Employees', isProtected: true },
    { path: '/logs',     icon: <MdBarChart />,     label: 'Logs Tracker', isProtected: true },
    { path: '/health',   icon: <MdAnalytics />,    label: 'Health Monitor', isProtected: true },
    { path: '/database', icon: <MdStorage />,      label: 'Database Config', isProtected: true },
  ]

  if (isLoggedIn) {
    navItems.push({ path: '/master-settings', icon: <MdSettings />, label: 'Master Settings', isProtected: false })
  }

  const handleLogout = async () => {
    try {
      await apiLogout()
    } catch (err) {}
    localStorage.removeItem('utas_token')
    onLogout()
    toast.success('Logged Out')
    navigate('/')
  }

  return (
    <div className="sidebar">
      <div className="sidebar-logo">
        <MdFingerprint />
        {version && (
          <span className="version-badge" style={{ 
            fontSize: '11px', 
            fontWeight: 600, 
            background: 'rgba(0, 0, 0, 0.05)', 
            padding: '2px 8px', 
            borderRadius: '12px',
            color: 'var(--color-text-muted)',
            border: '1px solid var(--color-border)',
            opacity: 0.8,
            marginTop: '6px'
          }}>
            v{version}
          </span>
        )}
      </div>
      
      <div className="nav-list" style={{flex: 1, display: 'flex', flexDirection: 'column'}}>
        <div style={{ flex: 1 }}>
          {navItems.map(item => {
            const isLocked = item.isProtected && !isLoggedIn
            const targetPath = isLocked ? '/login' : item.path
            return (
              <Link 
                key={item.path} 
                to={targetPath}
                className={`nav-item ${location.pathname === item.path ? 'active' : ''}`}
                style={{ position: 'relative', display: 'flex', flexDirection: 'column', alignItems: 'center' }}
              >
                {item.icon}
                <span style={{ fontSize: '9px', textAlign: 'center', wordBreak: 'break-word', lineHeight: '1.2' }}>{item.label}</span>
                {isLocked && (
                  <div style={{ 
                    position: 'absolute', 
                    top: '2px', 
                    right: '2px', 
                    background: 'rgba(239, 68, 68, 0.1)', 
                    borderRadius: '50%', 
                    padding: '2px', 
                    display: 'flex',
                    border: '1px solid rgba(239, 68, 68, 0.2)'
                  }}>
                    <MdLock size={10} style={{ color: '#ef4444' }} />
                  </div>
                )}
              </Link>
            )
          })}
        </div>
 
        <div style={{ marginTop: 'auto', display: 'flex', flexDirection: 'column', alignItems: 'center', width: '100%', paddingBottom: '10px' }}>
          {isLoggedIn && (
            <button 
              onClick={handleLogout}
              className="nav-item logout-btn"
              style={{ 
                display: 'flex', 
                flexDirection: 'column',
                alignItems: 'center', 
                gap: '3px', 
                background: 'none', 
                border: 'none', 
                color: '#ef4444', 
                cursor: 'pointer', 
                width: '60px',
                marginBottom: '10px',
                padding: '8px 4px',
              }}
            >
              <MdLogout />
              <span style={{ fontSize: '9px' }}>Logout</span>
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

