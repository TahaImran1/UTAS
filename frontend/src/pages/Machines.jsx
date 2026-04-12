import React, { useEffect, useState } from 'react'
import { MdSearch, MdFingerprint, MdDelete, MdRefresh, MdClearAll, MdInfo } from 'react-icons/md'
import toast from 'react-hot-toast'
import { getMachines, addMachine, removeMachine, testConnection, manualPull, getDeviceInfo, clearAttendance } from '../api/client'

export default function Machines() {
  const [machines, setMachines] = useState([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [testing, setTesting] = useState(false)
  
  // Form State
  const [formData, setFormData] = useState({ ip: '', port: 4370, location: '', sn: '', password: 0, protocol: 'TCP', company_name: 'None' })
  const [companies, setCompanies] = useState(['None'])

  useEffect(() => {
    fetchMachines()
    fetchCompanies()
    const interval = setInterval(() => {
        fetchMachines();
        fetchCompanies();
    }, 10000)
    return () => clearInterval(interval)
  }, [])

  const fetchCompanies = async () => {
    try {
      const res = await getCompanies()
      if(res.data.success) setCompanies(res.data.companies)
    } catch (err) {}
  }

  const fetchMachines = async () => {
    try {
      const res = await getMachines()
      setMachines(res.data)
    } catch (err) {
      toast.error('Failed to load machines')
    } finally {
      setLoading(false)
    }
  }

  const handleTestConnection = async () => {
    if(!formData.ip) return toast.error('Enter IP Address')
    setTesting(true)
    try {
      const res = await testConnection({ ip: formData.ip, port: formData.port, password: formData.password })
      if(res.data.success) {
        toast.success('Connection Successful!')
        setFormData(prev => ({ ...prev, sn: res.data.serial_number }))
      } else {
        toast.error(`Connection Failed: ${res.data.error}`)
      }
    } catch (err) {
      toast.error('Connection Failed - Server unreachable')
    } finally {
      setTesting(false)
    }
  }

  const handleSaveMachine = async () => {
    if(!formData.ip) return toast.error('Enter IP Address')
    try {
      const res = await addMachine(formData)
      if(res.data.success) {
        toast.success('Machine Added')
        setShowModal(false)
        setFormData({ ip: '', port: 4370, location: '', sn: '', password: 0, protocol: 'TCP', company_name: 'None' })
        fetchMachines()
      }
    } catch (err) {
      toast.error('Failed to add machine')
    }
  }

  const handleDelete = async (sn) => {
    if(!window.confirm('Delete this machine?')) return
    try {
      await removeMachine(sn)
      toast.success('Machine Removed')
      fetchMachines()
    } catch (err) {
      toast.error('Failed to remove machine')
    }
  }

  const handlePull = async (sn) => {
    const t = toast.loading('Pulling records...')
    try {
      const res = await manualPull(sn)
      if(res.data.success) {
        toast.success(`Pulled ${res.data.records} records`, { id: t })
        fetchMachines()
      } else {
        toast.error(res.data.error || 'Pull failed', { id: t })
      }
    } catch (err) {
      toast.error('Server error', { id: t })
    }
  }
  
  const handleClear = async (sn) => {
    if(!window.confirm("Are you sure you want to clear ALL logs on this device?")) {
      return
    }
    const t = toast.loading('Clearing logs...')
    try {
      const res = await clearAttendance(sn)
      if(res.data.success) {
        toast.success('Logs cleared on device', { id: t })
      } else {
        toast.error(res.data.error || 'Clear failed', { id: t })
      }
    } catch (err) {
      toast.error('Server error', { id: t })
    }
  }

  return (
    <div>
      <div className="section-header-card red">
        <div>
          <h2>Total Machines</h2>
          <div className="big-num">{machines.length}</div>
        </div>
        <MdFingerprint size={64} style={{opacity: 0.3}} />
      </div>

      <div className="filter-bar" style={{justifyContent: 'space-between'}}>
        <div className="search-box" style={{background: 'var(--color-card)'}}>
          <MdSearch size={18} color="var(--color-text-muted)" />
          <input type="text" placeholder="Search machine..." />
        </div>
        <div style={{display: 'flex', gap: '10px'}}>
          <button className="btn btn-ghost"><MdRefresh /> Filter</button>
          <button className="btn btn-primary" onClick={() => setShowModal(true)}>Add Machine</button>
        </div>
      </div>

      {loading ? (
        <div className="empty-state"><div className="spinner" style={{borderColor: 'rgba(0,0,0,0.1)', borderTopColor: 'var(--color-accent)'}}></div> Loading...</div>
      ) : machines.length === 0 ? (
        <div className="empty-state">
          <MdFingerprint />
          <p>No machines configured yet.</p>
        </div>
      ) : (
        <div className="machines-grid">
          {machines.map((m, i) => (
             <div key={m.sn || i} className="machine-card">
              <div className="machine-card-header">
                <span className="machine-card-title">{m.location || 'Unknown '}</span>
                <span className={`status-badge ${m.status}`}>{m.status}</span>
              </div>
              
               <div className="machine-info-row">
                <span className="machine-info-label">Protocol</span>
                <span className="machine-info-value" style={{color: m.protocol === 'HTTP' ? 'var(--color-accent)' : 'inherit', fontWeight: 'bold'}}>
                    {m.protocol || 'TCP'}
                </span>
              </div>
              <div className="machine-info-row">
                <span className="machine-info-label">Company</span>
                <span className="machine-info-value">{m.company_name || 'None'}</span>
              </div>
              <div className="machine-info-row">
                <span className="machine-info-label">IP Address</span>
                <span className="machine-info-value">{m.ip}:{m.port}</span>
              </div>
              <div className="machine-info-row">
                <span className="machine-info-label">Serial No.</span>
                <span className="machine-info-value">{m.sn || '---'}</span>
              </div>
               <div className="machine-info-row" style={{border: 'none', color: 'var(--color-text-muted)', fontSize: '11px', marginTop: '4px'}}>
                {m.last_sync ? `Last sync: ${new Date(m.last_sync).toLocaleTimeString()}` : 'Never synced'}
              </div>

              <div className="machine-card-actions">
                <button className="btn btn-ghost btn-sm" style={{flex: 1}} title="Manual Pull" onClick={() => handlePull(m.sn)}>
                  <MdRefresh /> Pull
                </button>
                <button className="btn btn-ghost btn-sm" style={{flex: 1, borderColor: 'var(--card-red)', color: 'var(--card-red)'}} title="Clear Logs" onClick={() => handleClear(m.sn)}>
                  <MdClearAll /> Clear
                </button>
                <button className="btn btn-ghost btn-sm" onClick={() => handleDelete(m.sn)} title="Delete Machine">
                  <MdDelete />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add Machine Modal */}
      {showModal && (
        <div className="modal-overlay">
          <div className="modal">
            <h2>Add New Machine</h2>
            
            <div className="form-group">
              <label>IP Address</label>
              <input type="text" value={formData.ip} onChange={e => setFormData({...formData, ip: e.target.value})} placeholder="e.g. 192.168.1.100" />
            </div>
            
             <div className="form-group" style={{display: 'flex', gap: '10px'}}>
               <div style={{flex: 1}}>
                  <label>Port</label>
                  <input type="number" value={formData.port} onChange={e => setFormData({...formData, port: e.target.value})} />
               </div>
               <div style={{flex: 1}}>
                  <label>Password</label>
                  <input type="password" value={formData.password} onChange={e => setFormData({...formData, password: e.target.value})} placeholder="0 if none" />
               </div>
            </div>

            <div className="form-group" style={{display: 'flex', gap: '10px'}}>
               <div style={{flex: 1}}>
                  <label>Protocol</label>
                  <select className="form-control" value={formData.protocol} onChange={e => setFormData({...formData, protocol: e.target.value})}>
                      <option value="TCP">TCP (Pull)</option>
                      <option value="HTTP">HTTP (Push/ADMS)</option>
                  </select>
               </div>
               <div style={{flex: 1}}>
                  <label>Company Mapping</label>
                  <input type="text" list="company-list" value={formData.company_name} onChange={e => setFormData({...formData, company_name: e.target.value})} placeholder="e.g. Techno Group" />
                  <datalist id="company-list">
                      {companies.map(c => <option key={c} value={c} />)}
                  </datalist>
               </div>
            </div>

            <div className="form-group">
              <label>Location / Branch</label>
              <input type="text" value={formData.location} onChange={e => setFormData({...formData, location: e.target.value})} placeholder="e.g. Head Office" />
            </div>
            
            <div className="form-group">
              <label>Serial Number</label>
              <div style={{display: 'flex', gap: '10px'}}>
                <input type="text" value={formData.sn} onChange={e => setFormData({...formData, sn: e.target.value})} placeholder="Auto-filled on test" disabled={testing} />
                <button type="button" className="btn btn-ghost" onClick={handleTestConnection} disabled={testing || !formData.ip}>
                  {testing ? 'Testing...' : 'Test'}
                </button>
              </div>
            </div>

            <div className="modal-actions">
              <button className="btn btn-ghost" onClick={() => setShowModal(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={handleSaveMachine}>Save Machine</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
