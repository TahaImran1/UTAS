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

  const navItems = [
    { path: '/',         icon: <MdDashboard />,    label: 'Dashboard', isProtected: false },
    { path: '/machines', icon: <MdFingerprint />,  label: 'Machines', isProtected: false },
    { path: '/server',   icon: <MdSettingsInputComponent />, label: 'Server Engine', isProtected: true },
    { path: '/companies',icon: <MdBusiness />,     label: 'Companies', isProtected: true },
    { path: '/employees',icon: <MdPeople />,       label: 'Employees', isProtected: true },
    { path: '/logs',     icon: <MdBarChart />,     label: 'Attendance Logs', isProtected: true },
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
              marginTop: 'auto',
              padding: '8px 4px',
            }}
          >
            <MdLogout />
            <span style={{ fontSize: '9px' }}>Logout</span>
          </button>
        )}
      </div>
    </div>
  )
}

