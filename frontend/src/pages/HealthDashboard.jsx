import React, { useEffect, useState } from 'react'
import { 
  MdDns, MdStorage, MdCloudQueue, MdSpeed, 
  MdMemory, MdDeveloperBoard, MdTimer, MdAnalytics,
  MdTrendingUp, MdErrorOutline, MdCheckCircle
} from 'react-icons/md'
import { getHealthStatus } from '../api/client'
import toast from 'react-hot-toast'

export default function HealthDashboard() {
  const [health, setHealth] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const res = await getHealthStatus()
        setHealth(res.data)
        setLoading(false)
      } catch (err) {
        console.error("Health check failed", err)
      }
    }

    fetchHealth()
    const interval = setInterval(fetchHealth, 2000)
    return () => clearInterval(interval)
  }, [])

  if (loading || !health) return (
    <div className="loading-container">
      <div className="spinner"></div>
      <p>Collecting Real-time Metrics...</p>
    </div>
  )

  const formatUptime = (seconds) => {
    const h = Math.floor(seconds / 3600)
    const m = Math.floor((seconds % 3600) / 60)
    const s = seconds % 60
    return `${h}h ${m}m ${s}s`
  }

  const getStatusColor = (status) => {
    if (status === 'online' || status === 'healthy') return '#10b981'
    if (status.includes('error') || status === 'offline') return '#ef4444'
    return '#f59e0b'
  }

  return (
    <div className="health-container">
      <div className="health-header">
        <h1><MdAnalytics /> System Health Monitoring</h1>
        <div className="pulse-container">
            <span className="pulse-dot"></span>
            LIVE UPDATES
        </div>
      </div>

      <div className="metrics-grid">
        {/* API STATUS CARD */}
        <div className="health-card glass">
          <div className="card-top">
            <MdCloudQueue size={32} color="#3b82f6" />
            <span className="status-badge" style={{background: getStatusColor(health.api.status)}}>
              {health.api.status.toUpperCase()}
            </span>
          </div>
          <h3>API Services</h3>
          <div className="stat-line">
            <MdSpeed /> <span>Avg Latency:</span> <strong>{health.api.metrics.avg_latency_ms}ms</strong>
          </div>
          <div className="stat-line">
            <MdTimer /> <span>Total Threads:</span> <strong>{health.api.metrics.active_threads}</strong>
          </div>
          <div className="stat-line">
            <MdTimer /> <span>Uptime:</span> <strong>{formatUptime(health.uptime_seconds)}</strong>
          </div>
        </div>

        {/* DATABASE STATUS CARD */}
        <div className="health-card glass">
          <div className="card-top">
            <MdStorage size={32} color="#8b5cf6" />
            <span className="status-badge" style={{background: getStatusColor(health.database.status)}}>
              {health.database.status.toUpperCase()}
            </span>
          </div>
          <h3>{health.database.type} Database</h3>
          <div className="stat-line">
            <MdSpeed /> <span>Connection Latency:</span> <strong>{health.database.latency_ms}ms</strong>
          </div>
          <div className="stat-line">
            <MdCheckCircle /> <span>Health:</span> <strong>{health.database.status === 'online' ? 'Optimal' : 'Degraded'}</strong>
          </div>
          <div className="stat-line">
             <span>Type:</span> <strong>{health.database.type}</strong>
          </div>
        </div>

        {/* PUSH ENGINE CARD */}
        <div className="health-card glass">
          <div className="card-top">
            <MdTrendingUp size={32} color="#10b981" />
            <span className="status-badge" style={{background: getStatusColor(health.push_engine?.status || 'offline')}}>
              {(health.push_engine?.status || 'OFFLINE').toUpperCase()}
            </span>
          </div>
          <h3>Push Engine (ADMS)</h3>
          <div className="stat-line">
            <MdAnalytics /> <span>Online Devices:</span> <strong>{health.push_engine?.online_devices || 0} / {health.push_engine?.total_devices || 0}</strong>
          </div>
          <div className="stat-line">
            <MdDns /> <span>Command Queue:</span> <strong>{health.push_engine?.queue_size || 0} commands</strong>
          </div>
          <div className="stat-line">
             <span>Protocol:</span> <strong>HTTP / Push</strong>
          </div>
        </div>

        {/* PULL ENGINE CARD */}
        <div className="health-card glass">
          <div className="card-top">
            <MdDns size={32} color="#ec4899" />
            <span className="status-badge" style={{background: getStatusColor(health.engine?.status === 'online' ? 'online' : 'offline')}}>
              {(health.engine?.status || 'OFFLINE').toUpperCase()}
            </span>
          </div>
          <h3>Pull Engine (TCP)</h3>
          <div className="stat-line">
            <MdAnalytics /> <span>Active Threads:</span> <strong>{health.engine?.sync_threads || 0} Workers</strong>
          </div>
          <div className="stat-line">
            <MdTimer /> <span>Scheduler:</span> <strong>{health.engine?.scheduler || 'stopped'}</strong>
          </div>
          <div className="stat-line">
             <span>Configured:</span> <strong>{health.engine?.active_machines || 0} Machines</strong>
          </div>
        </div>
      </div>

      <div className="resource-section">
        <h2><MdDeveloperBoard /> Resource Utilization</h2>
        <div className="resource-grid">
          <div className="resource-card glass">
            <div className="resource-info">
              <span className="res-label">CPU Usage</span>
              <span className="res-value">{health.system.cpu_percent}%</span>
            </div>
            <div className="progress-bg">
              <div className="progress-fill cpu" style={{width: `${health.system.cpu_percent}%`}}></div>
            </div>
          </div>

          <div className="resource-card glass">
            <div className="resource-info">
              <span className="res-label">Memory Usage</span>
              <span className="res-value">{health.system.memory_percent}%</span>
            </div>
            <div className="progress-bg">
              <div className="progress-fill mem" style={{width: `${health.system.memory_percent}%`}}></div>
            </div>
          </div>

          <div className="resource-card glass">
            <div className="resource-info">
              <span className="res-label">Process Memory</span>
              <span className="res-value">{health.system.process_memory_mb} MB</span>
            </div>
            <div className="stat-desc">Backend process footprint</div>
          </div>
        </div>
      </div>

      <div className="api-stats-section glass">
        <h2><MdTrendingUp /> API Traffic Snapshot</h2>
        <div className="traffic-badges">
          {Object.entries(health.api.metrics.status_codes).map(([code, count]) => (
            <div key={code} className={`traffic-badge ${code.startsWith('2') ? 'success' : 'error'}`}>
               <span className="code">{code}</span>
               <span className="count">{count} reqs</span>
            </div>
          ))}
          {Object.keys(health.api.metrics.status_codes).length === 0 && (
            <p style={{color: '#888'}}>No traffic recorded yet.</p>
          )}
        </div>
      </div>

      <style jsx>{`
        .health-container {
          padding: 30px;
          color: #e2e8f0;
          background: #0f172a;
          min-height: 100vh;
          animation: fadeIn 0.5s ease;
        }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

        .health-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 40px;
        }
        .health-header h1 {
          font-size: 1.8rem;
          font-weight: 700;
          display: flex;
          align-items: center;
          gap: 12px;
          margin: 0;
          color: #f8fafc;
        }

        .pulse-container {
          background: rgba(255,255,255,0.05);
          padding: 8px 16px;
          border-radius: 20px;
          display: flex;
          align-items: center;
          gap: 10px;
          font-size: 0.75rem;
          font-weight: 600;
          color: #94a3b8;
          border: 1px solid rgba(255,255,255,0.1);
        }
        .pulse-dot {
          width: 8px;
          height: 8px;
          background: #10b981;
          border-radius: 50%;
          animation: pulse 2s infinite;
        }
        @keyframes pulse {
          0% { box-shadow: 0 0 0 0 rgba(16,185,129, 0.7); }
          70% { box-shadow: 0 0 0 8px rgba(16,185,129, 0); }
          100% { box-shadow: 0 0 0 0 rgba(16,185,129, 0); }
        }

        .metrics-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
          gap: 25px;
          margin-bottom: 40px;
        }

        .glass {
          background: #1e293b;
          border: 1px solid #334155;
          border-radius: 16px;
          padding: 24px;
          transition: all 0.3s ease;
          box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        }
        .glass:hover {
          border-color: #475569;
          transform: translateY(-2px);
          box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        }

        .card-top {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 20px;
        }
        .status-badge {
          padding: 4px 10px;
          border-radius: 6px;
          font-size: 0.7rem;
          font-weight: 800;
          color: white;
        }

        h3 { margin: 0 0 20px 0; font-size: 1.1rem; color: #f1f5f9; }
        h2 { margin: 0 0 25px 0; font-size: 1.3rem; color: #f8fafc; display: flex; align-items: center; gap: 10px; }

        .stat-line {
          display: flex;
          align-items: center;
          gap: 10px;
          margin-bottom: 12px;
          color: #94a3b8;
          font-size: 0.9rem;
        }
        .stat-line strong { color: #f1f5f9; }

        .resource-section { margin-bottom: 40px; }
        .resource-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
          gap: 20px;
        }

        .resource-card {
           padding: 20px;
        }

        .resource-info {
          display: flex;
          justify-content: space-between;
          margin-bottom: 12px;
        }
        .res-label { color: #94a3b8; font-weight: 500; }
        .res-value { color: #f1f5f9; font-weight: 700; font-size: 1.1rem; }

        .progress-bg {
          height: 10px;
          background: #334155;
          border-radius: 5px;
          overflow: hidden;
        }
        .progress-fill {
          height: 100%;
          border-radius: 5px;
          transition: width 0.5s ease;
        }
        .progress-fill.cpu { background: #3b82f6; }
        .progress-fill.mem { background: #8b5cf6; }

        .stat-desc { color: #64748b; font-size: 0.8rem; margin-top: 8px; }

        .api-stats-section {
          background: #1e293b;
        }
        .traffic-badges {
          display: flex;
          flex-wrap: wrap;
          gap: 12px;
          margin-top: 20px;
        }
        .traffic-badge {
          padding: 8px 16px;
          border-radius: 10px;
          display: flex;
          align-items: center;
          gap: 10px;
          background: #0f172a;
          border: 1px solid #334155;
        }
        .traffic-badge.success { border-color: #059669; }
        .traffic-badge.error { border-color: #dc2626; }
        .traffic-badge .code { font-weight: 800; font-family: monospace; }
        .traffic-badge.success .code { color: #10b981; }
        .traffic-badge.error .code { color: #ef4444; }
        .traffic-badge .count { color: #94a3b8; font-size: 0.85rem; }

        .loading-container {
          height: 100vh;
          display: flex;
          flex-direction: column;
          justify-content: center;
          align-items: center;
          background: #0f172a;
          color: #94a3b8;
        }
        .spinner {
          width: 32px;
          height: 32px;
          border: 3px solid rgba(255,255,255,0.05);
          border-top: 3px solid #3b82f6;
          border-radius: 50%;
          animation: spin 1s linear infinite;
          margin-bottom: 20px;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
      `}</style>
    </div>
  )
}
