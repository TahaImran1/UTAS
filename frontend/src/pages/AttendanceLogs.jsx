import React, { useEffect, useState } from 'react'
import { MdBarChart, MdSearch, MdFilterList, MdFileDownload, MdCloudQueue } from 'react-icons/md'
import client, { getAttendanceLogs, getOfflineLogsStatus, syncOfflineLogs } from '../api/client'
import toast from 'react-hot-toast'
import { format } from 'date-fns'

export default function AttendanceLogs() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [dateFilter, setDateFilter] = useState(format(new Date(), 'yyyy-MM-dd'))
  const [snFilter, setSnFilter] = useState('')
  const [offlineCount, setOfflineCount] = useState(0)
  const [syncingOffline, setSyncingOffline] = useState(false)

  useEffect(() => {
    fetchLogs()
  }, [dateFilter, snFilter])

  const fetchLogs = async () => {
    setLoading(true)
    try {
      const res = await getAttendanceLogs({ date: dateFilter, sn: snFilter })
      setLogs(res.data)
      await checkOfflineLogsStatus()
    } catch (err) {
      toast.error('Failed to load logs')
      setLogs([]) 
    } finally {
      setLoading(false)
    }
  }

  const checkOfflineLogsStatus = async () => {
    try {
      const res = await getOfflineLogsStatus()
      setOfflineCount(res.data.count || 0)
    } catch (err) {
      console.error('Failed to check offline logs status:', err)
    }
  }

  const handleSyncOffline = async () => {
    setSyncingOffline(true)
    const t = toast.loading('Syncing offline logs to database...')
    try {
      const res = await syncOfflineLogs()
      if (res.data.success) {
        toast.success(res.data.message || `Successfully synced ${res.data.synced} logs.`, { id: t })
        await fetchLogs()
      } else {
        const errMsg = res.data.errors ? res.data.errors.join('; ') : 'Sync failed'
        toast.error(`Sync completed with errors: ${errMsg}`, { id: t, duration: 5000 })
        await fetchLogs()
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Sync request failed', { id: t })
    } finally {
      setSyncingOffline(false)
      checkOfflineLogsStatus()
    }
  }

  const handleDownloadOffline = async (formatType) => {
    const t = toast.loading(`Downloading offline logs as ${formatType.toUpperCase()}...`)
    try {
      const response = await client.get(`/api/admin/offline-logs/download?format=${formatType}`, {
        responseType: 'blob'
      })
      const blob = new Blob([response.data], { type: response.headers['content-type'] })
      const link = document.createElement('a')
      link.href = window.URL.createObjectURL(blob)
      link.download = `offline_logs_${new Date().toISOString().slice(0, 10)}.${formatType === 'txt' ? 'txt' : 'csv'}`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(link.href)
      toast.success('Download complete!', { id: t })
    } catch (err) {
      toast.error('Download failed', { id: t })
    }
  }

  // Calculate total logs pulled in current list
  const totalPulled = logs.reduce((sum, item) => sum + (item.count || 0), 0)

  return (
    <div>
      {offlineCount > 0 && (
        <div style={{
          background: 'linear-gradient(135deg, #EF4444 0%, #B91C1C 100%)',
          color: 'white',
          padding: '15px 20px',
          borderRadius: '8px',
          marginBottom: '20px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          boxShadow: '0 4px 12px rgba(239, 68, 68, 0.25)'
        }}>
          <div>
            <h4 style={{ margin: 0, fontWeight: 700, fontSize: '15px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <MdCloudQueue size={20} /> Unsynced Offline Logs ({offlineCount})
            </h4>
            <p style={{ margin: '4px 0 0 0', opacity: 0.9, fontSize: '12px' }}>
              There are {offlineCount} attendance records saved locally that could not be pushed to the database due to internet loss.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button className="btn btn-secondary" onClick={() => handleDownloadOffline('csv')} style={{ background: 'rgba(255, 255, 255, 0.2)', border: 'none', color: 'white', padding: '6px 12px', fontSize: '12px', cursor: 'pointer' }}>
              <MdFileDownload /> Download CSV
            </button>
            <button className="btn btn-secondary" onClick={() => handleDownloadOffline('txt')} style={{ background: 'rgba(255, 255, 255, 0.15)', border: 'none', color: 'white', padding: '6px 12px', fontSize: '12px', cursor: 'pointer' }}>
              <MdFileDownload /> Download TXT
            </button>
            <button className="btn btn-primary" onClick={handleSyncOffline} style={{ background: 'white', color: '#B91C1C', border: 'none', padding: '6px 16px', fontSize: '12px', fontWeight: 'bold', cursor: 'pointer' }}>
              Sync to Database
            </button>
          </div>
        </div>
      )}
      <div className="section-header-card" style={{background: 'var(--card-green)'}}>
        <div>
          <h2>Total Logs Pulled</h2>
          <div className="big-num">{totalPulled}</div>
        </div>
        <MdBarChart size={64} style={{opacity: 0.3}} />
      </div>

      <div className="filter-bar" style={{justifyContent: 'space-between'}}>
        <div style={{display: 'flex', gap: '10px'}}>
           <div className="search-box" style={{background: 'var(--color-card)'}}>
            <MdSearch size={18} color="var(--color-text-muted)" />
            <input type="text" placeholder="Search by SN/IP..." value={snFilter} onChange={e => setSnFilter(e.target.value)} />
          </div>
          <input type="date" value={dateFilter} onChange={e => setDateFilter(e.target.value)} />
        </div>
        
        <div style={{display: 'flex', gap: '10px'}}>
          <button className="btn btn-ghost" onClick={fetchLogs}><MdFilterList /> Filter</button>
          <button className="btn btn-primary"><MdFileDownload /> Export</button>
        </div>
      </div>

      <div className="data-table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>When (Date)</th>
              <th>Which (Device)</th>
              <th>Company</th>
              <th>DB Profile</th>
              <th>No. of Logs Pulled</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan="6" style={{textAlign: 'center', padding: '30px'}}>Loading...</td></tr>
            ) : logs.length === 0 ? (
              <tr><td colSpan="6" style={{textAlign: 'center', padding: '30px', color: 'var(--color-text-muted)'}}>No attendance records found for this date.</td></tr>
            ) : (
               logs.map((log, i) => (
                <tr key={i} className="present">
                  <td style={{fontWeight: 600}}>{log.date}</td>
                  <td style={{color: 'var(--color-text)'}}>{log.machine}</td>
                  <td style={{color: 'var(--color-text-muted)'}}>{log.company}</td>
                  <td style={{color: 'var(--color-text-muted)', fontFamily: 'monospace'}}>{log.profile}</td>
                  <td style={{fontWeight: 700, color: 'var(--color-accent)'}}>{log.count} logs</td>
                  <td>
                     <div style={{
                       display: 'inline-flex', 
                       alignItems: 'center', 
                       justifyContent: 'center', 
                       background: log.status === 'Success' ? '#22C55E' : '#EF4444', 
                       color: 'white', 
                       borderRadius: '4px', 
                       padding: '2px 8px', 
                       fontSize: '11px', 
                       fontWeight: 'bold'
                     }}>
                        {log.status}
                     </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
