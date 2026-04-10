import React, { useEffect, useState } from 'react'
import { MdPeople, MdBusiness, MdFingerprint, MdCheckCircle } from 'react-icons/md'
import StatCard from '../components/StatCard'
import { getDashboardStats } from '../api/client'

export default function Dashboard() {
  const [stats, setStats] = useState({
    total_machines: 0,
    online_machines: 0,
    records_today: 0,
  })

  useEffect(() => {
    fetchStats()
    const interval = setInterval(fetchStats, 30000) // auto-refresh every 30s
    return () => clearInterval(interval)
  }, [])

  const fetchStats = async () => {
    try {
      const res = await getDashboardStats()
      setStats(res.data)
    } catch (err) {
      console.error(err)
    }
  }

  return (
    <div>
      <div className="stat-cards-row">
        <StatCard title="Total Employees" value="24" color="green" icon={MdPeople} />
        <StatCard title="Total Companies" value="3" color="blue" icon={MdBusiness} />
        <StatCard title="Total Machines" value={stats.total_machines || 7} color="red" icon={MdFingerprint} />
        <StatCard title="Present Emps" value={stats.records_today || 18} color="purple" icon={MdCheckCircle} />
      </div>

      <div className="chart-card" style={{ height: '400px', display: 'flex', flexDirection: 'column' }}>
        <h3>Attendance per day</h3>
        <div style={{ flex: 1, borderLeft: '2px solid #1c2b59', borderBottom: '2px solid #1c2b59', display: 'flex', alignItems: 'flex-end', padding: '10px' }}>
          <span style={{ fontStyle: 'italic', color: '#666' }}>Graph to show attendance per day</span>
        </div>
      </div>
    </div>
  )
}
