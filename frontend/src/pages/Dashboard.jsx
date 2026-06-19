import React, { useEffect, useState } from 'react'
import { MdPeople, MdBusiness, MdFingerprint, MdCheckCircle, MdLan, MdContentCopy, MdCheckCircleOutline } from 'react-icons/md'
import StatCard from '../components/StatCard'
import { getDashboardStats, getServerInfo } from '../api/client'

export default function Dashboard() {
  const [stats, setStats] = useState({
    total_machines: 0,
    online_machines: 0,
    records_today: 0,
    total_companies: 0,
  })

  const [serverInfo, setServerInfo] = useState({
    local_ip: '...',
    port: '...',
    server_url: '',
  })

  const [copied, setCopied] = useState(null) // 'ip' | 'port' | 'url' | null

  useEffect(() => {
    fetchStats()
    fetchServerInfo()
    const interval = setInterval(fetchStats, 30000)
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

  const fetchServerInfo = async () => {
    try {
      const res = await getServerInfo()
      setServerInfo(res.data)
    } catch (err) {
      console.error('Could not fetch server info:', err)
    }
  }

  const copyToClipboard = (text, key) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(key)
      setTimeout(() => setCopied(null), 2000)
    })
  }

  return (
    <div>
      {/* ── Server Info Banner ─────────────────────────────────────────── */}
      <div className="server-info-banner">
        <div className="server-info-icon">
          <MdLan size={22} />
        </div>
        <div className="server-info-content">
          <span className="server-info-label">Server Address</span>
          <div className="server-info-fields">
            <div className="server-info-chip">
              <span className="chip-label">IP</span>
              <span className="chip-value">{serverInfo.local_ip}</span>
              <button
                className="chip-copy"
                title="Copy IP"
                onClick={() => copyToClipboard(serverInfo.local_ip, 'ip')}
              >
                {copied === 'ip' ? <MdCheckCircleOutline size={14} /> : <MdContentCopy size={14} />}
              </button>
            </div>
            <div className="server-info-chip">
              <span className="chip-label">PORT</span>
              <span className="chip-value">{serverInfo.port}</span>
              <button
                className="chip-copy"
                title="Copy Port"
                onClick={() => copyToClipboard(String(serverInfo.port), 'port')}
              >
                {copied === 'port' ? <MdCheckCircleOutline size={14} /> : <MdContentCopy size={14} />}
              </button>
            </div>
            <div className="server-info-chip chip-url">
              <span className="chip-label">URL</span>
              <span className="chip-value">{serverInfo.server_url}</span>
              <button
                className="chip-copy"
                title="Copy full URL"
                onClick={() => copyToClipboard(serverInfo.server_url, 'url')}
              >
                {copied === 'url' ? <MdCheckCircleOutline size={14} /> : <MdContentCopy size={14} />}
              </button>
            </div>
          </div>
        </div>
        <div className="server-info-hint">
          Configure ZKTeco devices to push to this address
        </div>
      </div>

      {/* ── Stat Cards ─────────────────────────────────────────────────── */}
      <div className="stat-cards-row">
        <StatCard title="Total Employees" value="24" color="green" icon={MdPeople} />
        <StatCard title="Total Companies" value={stats.total_companies || 0} color="blue" icon={MdBusiness} />
        <StatCard title="Total Machines" value={stats.total_machines || 0} color="red" icon={MdFingerprint} />
        <StatCard title="Records Today" value={stats.records_today || 0} color="purple" icon={MdCheckCircle} />
      </div>

      {/* ── Placeholder Chart ──────────────────────────────────────────── */}
      <div className="chart-card" style={{ height: '360px', display: 'flex', flexDirection: 'column' }}>
        <h3>Attendance per day</h3>
        <div style={{ flex: 1, borderLeft: '2px solid #1c2b59', borderBottom: '2px solid #1c2b59', display: 'flex', alignItems: 'flex-end', padding: '10px' }}>
          <span style={{ fontStyle: 'italic', color: '#666' }}>Graph to show attendance per day</span>
        </div>
      </div>
    </div>
  )
}
