import React from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { MdDashboard, MdFingerprint, MdBusiness, MdPeople, MdBarChart, MdSettingsInputComponent, MdLogout } from 'react-icons/md'

export default function Sidebar({ onLogout }) {
  const location = useLocation()
  const navigate = useNavigate()

  const navItems = [
    { path: '/',         icon: <MdDashboard />,    label: 'Dashboard' },
    { path: '/machines', icon: <MdFingerprint />,  label: 'Machines' },
    { path: '/server',   icon: <MdSettingsInputComponent />, label: 'Server Engine' },
    { path: '/companies',icon: <MdBusiness />,     label: 'Companies' },
    { path: '/employees',icon: <MdPeople />,       label: 'Employees' },
    { path: '/logs',     icon: <MdBarChart />,     label: 'Attendance Logs' },
  ]

  const handleLogout = () => {
    localStorage.removeItem('utas_token')
    if (onLogout) {
      onLogout()
    } else {
      navigate('/login')
    }
  }

  return (
    <div className="sidebar">
      <div className="sidebar-logo">
        <MdFingerprint />
      </div>
      
      <div className="nav-list" style={{flex: 1}}>
        {navItems.map(item => (
            <Link 
            key={item.path} 
            to={item.path}
            className={`nav-item ${location.pathname === item.path ? 'active' : ''}`}
            >
            {item.icon}
            <span>{item.label}</span>
            </Link>
        ))}
      </div>

      <button className="nav-item logout-btn" onClick={handleLogout} style={{background: 'none', border: 'none', cursor: 'pointer', width: '100%', color: 'inherit'}}>
        <MdLogout />
        <span>Logout</span>
      </button>
    </div>
  )
}
