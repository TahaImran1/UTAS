import React from 'react'
import { Link, useLocation } from 'react-router-dom'
import { MdDashboard, MdFingerprint, MdBusiness, MdPeople, MdBarChart } from 'react-icons/md'

export default function Sidebar() {
  const location = useLocation()

  const navItems = [
    { path: '/',         icon: <MdDashboard />,    label: 'Dashboard' },
    { path: '/machines', icon: <MdFingerprint />,  label: 'Machines' },
    { path: '/companies',icon: <MdBusiness />,     label: 'Companies' },
    { path: '/employees',icon: <MdPeople />,       label: 'Employees' },
    { path: '/logs',     icon: <MdBarChart />,     label: 'Attendance Logs' },
  ]

  return (
    <div className="sidebar">
      <div className="sidebar-logo">
        <MdDashboard />
      </div>
      
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
  )
}
