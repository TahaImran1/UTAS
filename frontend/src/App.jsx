import React, { useState, useEffect } from 'react'
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import TopBar from './components/TopBar'

// Pages
import Dashboard from './pages/Dashboard'
import Machines from './pages/Machines'
import Companies from './pages/Companies'
import Employees from './pages/Employees'
import AttendanceLogs from './pages/AttendanceLogs'
import Login from './pages/Login'
import ServerStatus from './pages/ServerStatus'

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(!!localStorage.getItem('utas_token'))

  const handleLoginSuccess = () => {
    setIsAuthenticated(true)
  }

  if (!isAuthenticated) {
    return (
      <HashRouter>
        <Routes>
          <Route path="/login" element={<Login onLogin={handleLoginSuccess} />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </HashRouter>
    )
  }

  return (
    <HashRouter>
      <div className="app-layout">
        <Sidebar onLogout={() => setIsAuthenticated(false)} />
        <div className="main-area">
          <TopBar />
          <div className="page-content">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/machines" element={<Machines />} />
              <Route path="/server" element={<ServerStatus />} />
              <Route path="/companies" element={<Companies />} />
              <Route path="/employees" element={<Employees />} />
              <Route path="/logs" element={<AttendanceLogs />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </div>
        </div>
      </div>
    </HashRouter>
  )
}
