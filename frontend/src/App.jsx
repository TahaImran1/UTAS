import React from 'react'
import { HashRouter, Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import TopBar from './components/TopBar'

// Pages
import Dashboard from './pages/Dashboard'
import Machines from './pages/Machines'
import Companies from './pages/Companies'
import Employees from './pages/Employees'
import AttendanceLogs from './pages/AttendanceLogs'

export default function App() {
  return (
    <HashRouter>
      <div className="app-layout">
        <Sidebar />
        <div className="main-area">
          <TopBar />
          <div className="page-content">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/machines" element={<Machines />} />
              <Route path="/companies" element={<Companies />} />
              <Route path="/employees" element={<Employees />} />
              <Route path="/logs" element={<AttendanceLogs />} />
            </Routes>
          </div>
        </div>
      </div>
    </HashRouter>
  )
}
