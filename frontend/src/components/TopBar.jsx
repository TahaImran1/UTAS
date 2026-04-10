import React from 'react'
import { MdSearch, MdClose } from 'react-icons/md'
import { useLocation } from 'react-router-dom'

export default function TopBar() {
  const location = useLocation()
  
  // Map route to title
  const getTitle = () => {
    switch(location.pathname) {
      case '/': return 'DashBoard'
      case '/machines': return 'Machines'
      case '/companies': return 'Companies'
      case '/employees': return 'Employees'
      case '/logs': return 'Attendance Logs'
      default: return 'UTAS'
    }
  }

  return (
    <div className="topbar">
      <h1>{getTitle()}</h1>
      
      <div className="search-box">
        <MdSearch size={18} color="var(--color-text-muted)" />
        <input type="text" placeholder="Search" />
        <MdClose size={16} color="var(--color-text-muted)" style={{cursor: 'pointer'}} />
      </div>

      <div className="user-badge">
        <div className="user-avatar">A</div>
        <span className="user-name">Hi, Admin</span>
      </div>
    </div>
  )
}
