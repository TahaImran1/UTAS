import React, { useEffect, useState } from 'react'
import { MdBarChart, MdSearch, MdFilterList, MdFileDownload } from 'react-icons/md'
import { getAttendanceLogs } from '../api/client'
import toast from 'react-hot-toast'
import { format } from 'date-fns'

export default function AttendanceLogs() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [dateFilter, setDateFilter] = useState(format(new Date(), 'yyyy-MM-dd'))
  const [snFilter, setSnFilter] = useState('')

  useEffect(() => {
    fetchLogs()
  }, [dateFilter, snFilter])

  const fetchLogs = async () => {
    setLoading(true)
    try {
      const res = await getAttendanceLogs({ date: dateFilter, sn: snFilter })
      setLogs(res.data)
    } catch (err) {
      toast.error('Failed to load logs')
      setLogs([]) 
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="section-header-card" style={{background: 'var(--card-green)'}}>
        <div>
          <h2>Total Logs</h2>
          <div className="big-num">{logs.length}</div>
        </div>
        <MdBarChart size={64} style={{opacity: 0.3}} />
      </div>

      <div className="filter-bar" style={{justifyContent: 'space-between'}}>
        <div style={{display: 'flex', gap: '10px'}}>
           <div className="search-box" style={{background: 'var(--color-card)'}}>
            <MdSearch size={18} color="var(--color-text-muted)" />
            <input type="text" placeholder="Search by SN..." value={snFilter} onChange={e => setSnFilter(e.target.value)} />
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
              <th>User ID</th>
              <th>Time</th>
              <th>Machine</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan="4" style={{textAlign: 'center', padding: '30px'}}>Loading...</td></tr>
            ) : logs.length === 0 ? (
              <tr><td colSpan="4" style={{textAlign: 'center', padding: '30px', color: 'var(--color-text-muted)'}}>No attendance records found for this date.</td></tr>
            ) : (
               logs.map((log, i) => (
                <tr key={i} className="present">
                  <td style={{fontWeight: 600}}>{log.user_id}</td>
                  <td>{log.timestamp}</td>
                  <td style={{color: 'var(--color-text-muted)'}}>{log.machine}</td>
                  <td>
                     <div style={{display: 'inline-flex', alignItems: 'center', justifyContent: 'center', background: '#22C55E', color: 'white', borderRadius: '4px', padding: '2px 8px', fontSize: '11px', fontWeight: 'bold'}}>
                        Present
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
