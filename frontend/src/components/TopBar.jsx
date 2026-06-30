import React from 'react'
import { MdSearch, MdClose } from 'react-icons/md'
import { useLocation, Link } from 'react-router-dom'

export default function TopBar({ isLoggedIn }) {
  const location = useLocation()
  
  // Map route to title
  const getTitle = () => {
    switch(location.pathname) {
      case '/': return 'DashBoard'
      case '/machines': return 'Machines'
      case '/companies': return 'Companies'
      case '/employees': return 'Employees'
      case '/logs': return 'Logs Tracker'
      case '/master-settings': return 'Master Settings'
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

      {isLoggedIn ? (
        <div className="user-badge">
          <div className="user-avatar" style={{ background: '#3b82f6', color: 'white' }}>M</div>
          <span className="user-name">Master User</span>
        </div>
      ) : (
        <Link 
          to="/login" 
          className="btn btn-primary" 
          style={{ textDecoration: 'none', padding: '8px 16px', fontSize: '0.85rem', fontWeight: 600 }}
        >
          Sign In
        </Link>
      )}
    </div>
  )
}

