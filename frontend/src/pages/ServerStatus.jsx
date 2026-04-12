import React, { useEffect, useState, useRef } from 'react'
import { MdSettingsInputComponent, MdPlayArrow, MdStop, MdTerminal, MdRefresh } from 'react-icons/md'
import { getServerStatus, getServerLogs, controlServer } from '../api/client'
import toast from 'react-hot-toast'

export default function ServerStatus() {
  const [status, setStatus] = useState({ enabled: true, scheduler_running: true })
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const logEndRef = useRef(null)

  useEffect(() => {
    fetchStatus()
    fetchLogs()
    const interval = setInterval(() => {
        fetchStatus()
        fetchLogs()
    }, 3000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  const fetchStatus = async () => {
    try {
      const res = await getServerStatus()
      setStatus(res.data)
    } catch (err) {} 
  }

  const fetchLogs = async () => {
    try {
      const res = await getServerLogs()
      setLogs(res.data)
      setLoading(false)
    } catch (err) {}
  }

  const handleToggle = async (action) => {
    const t = toast.loading(`${action === 'start' ? 'Starting' : 'Stopping'} engine...`)
    try {
      await controlServer(action)
      toast.success(`Engine ${action === 'start' ? 'Started' : 'Stopped'}`, { id: t })
      fetchStatus()
    } catch (err) {
      toast.error('Failed to change engine status', { id: t })
    }
  }

  return (
    <div>
      <div className="section-header-card blue">
        <div>
          <h2>Server Engine Status</h2>
          <div className="status-indicator">
            <span className={`status-dot ${status.enabled ? 'online' : 'offline'}`}></span>
            {status.enabled ? 'Engine Active & Polling' : 'Engine Paused (Maintenance Mode)'}
          </div>
        </div>
        <MdSettingsInputComponent size={64} style={{opacity: 0.3}} />
      </div>

      <div className="admin-controls" style={{marginTop: '20px', display: 'flex', gap: '15px'}}>
        <button 
            className={`btn ${status.enabled ? 'btn-ghost' : 'btn-primary'}`} 
            onClick={() => handleToggle('start')}
            disabled={status.enabled}
        >
            <MdPlayArrow /> Resume Polling
        </button>
        <button 
            className={`btn ${status.enabled ? 'btn-red' : 'btn-ghost'}`} 
            onClick={() => handleToggle('stop')}
            disabled={!status.enabled}
        >
            <MdStop /> Pause Polling
        </button>
        <button className="btn btn-ghost" onClick={fetchLogs}><MdRefresh /> Refresh Logs</button>
      </div>

      <div className="log-viewer-container" style={{marginTop: '30px'}}>
        <div className="log-header">
            <MdTerminal /> System Runtime Logs
        </div>
        <div className="log-body">
            {loading ? (
                <div style={{padding: '20px', color: '#999'}}>Loading logs...</div>
            ) : logs.length === 0 ? (
                <div style={{padding: '20px', color: '#999'}}>No recent logs.</div>
            ) : (
                logs.map((log, i) => (
                    <div key={i} className={`log-line ${log.level.toLowerCase()}`}>
                        <span className="log-time">[{log.time}]</span>
                        <span className="log-level">{log.level}</span>
                        <span className="log-msg">{log.msg}</span>
                    </div>
                ))
            )}
            <div ref={logEndRef} />
        </div>
      </div>

      <style jsx>{`
        .status-indicator {
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 1.1rem;
            margin-top: 5px;
        }
        .status-dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
        }
        .status-dot.online { background: #10b981; box-shadow: 0 0 10px rgba(16,185,129,0.5); }
        .status-dot.offline { background: #ef4444; }

        .log-viewer-container {
            background: #1e1e1e;
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid #333;
        }
        .log-header {
            background: #252526;
            color: #ccc;
            padding: 10px 15px;
            font-size: 0.85rem;
            display: flex;
            align-items: center;
            gap: 10px;
            border-bottom: 1px solid #333;
        }
        .log-body {
            height: 400px;
            overflow-y: auto;
            padding: 15px;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 0.85rem;
        }
        .log-line {
            margin-bottom: 4px;
            line-height: 1.4;
        }
        .log-line.info { color: #d4d4d4; }
        .log-line.warning { color: #cca700; }
        .log-line.error { color: #f48771; }
        
        .log-time { color: #888; margin-right: 10px; }
        .log-level { margin-right: 10px; font-weight: bold; width: 60px; display: inline-block; }
        
        .btn-red {
            border: 1px solid #ef4444;
            color: #ef4444;
        }
        .btn-red:hover {
            background: #ef4444;
            color: white;
        }
      `}</style>
    </div>
  )
}
