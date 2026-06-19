import React, { useEffect, useState } from 'react'
import {
  MdSearch, MdFingerprint, MdDelete, MdRefresh, MdClearAll,
  MdInfo, MdAccessTime, MdClose, MdToggleOn, MdToggleOff, MdSettings, MdCheck
} from 'react-icons/md'
import toast from 'react-hot-toast'
import {
  getMachines,
  addMachine,
  removeMachine,
  testConnection,
  manualPull,
  getDeviceInfo,
  clearAttendance,
  getCompanies,
  syncTime,
  toggleMachine
} from '../api/client'

const secondsToInterval = (totalSeconds) => {
  if (totalSeconds % 604800 === 0) return { value: totalSeconds / 604800, unit: 'weeks' };
  if (totalSeconds % 86400 === 0) return { value: totalSeconds / 86400, unit: 'days' };
  if (totalSeconds % 3600 === 0) return { value: totalSeconds / 3600, unit: 'hours' };
  if (totalSeconds % 60 === 0) return { value: totalSeconds / 60, unit: 'minutes' };
  return { value: totalSeconds, unit: 'seconds' };
};

const intervalToSeconds = (value, unit) => {
  const v = parseInt(value) || 20;
  if (unit === 'weeks') return v * 604800;
  if (unit === 'days') return v * 86400;
  if (unit === 'hours') return v * 3600;
  if (unit === 'minutes') return v * 60;
  return v;
};

const formatSchedule = (m) => {
  if (m.sync_type === 'cron') {
    const days = m.sync_days && m.sync_days.length > 0 
      ? m.sync_days.map(d => d.charAt(0).toUpperCase() + d.slice(1)).join(', ')
      : 'Every day';
    return `${days} @ ${m.sync_time || '00:00'}`;
  } else {
    const totalSeconds = m.sync_interval || 20;
    const sched = secondsToInterval(totalSeconds);
    const unitStr = sched.unit.charAt(0).toUpperCase() + sched.unit.slice(1);
    return `Every ${sched.value} ${unitStr}`;
  }
};

const defaultFormData = { 
  ip: '', 
  port: 4370, 
  location: '', 
  sn: '', 
  password: 0, 
  protocol: 'TCP', 
  company_names: [],
  name: '',
  enabled: true,
  driver: 'zk',
  sync_type: 'interval',
  sync_interval: 20,
  sync_days: [],
  sync_time: '00:00'
}

export default function Machines({ isLoggedIn }) {
  const [machines, setMachines] = useState([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [testing, setTesting] = useState(false)
  const [infoModal, setInfoModal] = useState(null)
  const [confirmModal, setConfirmModal] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')

  // Scheduling State
  const [isEditing, setIsEditing] = useState(false)
  const [editSn, setEditSn] = useState('')
  const [intervalValue, setIntervalValue] = useState(20)
  const [intervalUnit, setIntervalUnit] = useState('seconds')
  
  // Form State
  const [formData, setFormData] = useState(defaultFormData)
  const [companies, setCompanies] = useState([])

  const resetFocus = () => {
    if (document.activeElement && typeof document.activeElement.blur === 'function') {
      document.activeElement.blur();
    }
  };

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
      if (res.data.success) {
        setCompanies(res.data.companies.filter(c => c !== 'None'))
      }
    } catch (err) {}
  }

  const fetchMachines = async () => {
    try {
      const res = await getMachines()
      setMachines(res.data || [])
    } catch (err) {
      toast.error('Failed to load machines')
    } finally {
      setLoading(false)
    }
  }

  const handleTestConnection = async () => {
    if (!formData.ip) return toast.error('Enter IP Address')
    setTesting(true)
    try {
      const res = await testConnection({ ip: formData.ip, port: formData.port, password: formData.password })
      if (res.data.success) {
        toast.success('Connection Successful!')
        setFormData(prev => ({ ...prev, sn: res.data.serial_number, driver: res.data.driver || prev.driver }))
      } else {
        toast.error(`Connection Failed: ${res.data.error}`)
      }
    } catch (err) {
      toast.error('Connection Failed - Server unreachable')
    } finally {
      setTesting(false)
    }
  }

  const handleEdit = (m) => {
    const sched = secondsToInterval(m.sync_interval || 20);
    
    // Resolve company_names array fallback
    let comps = m.company_names || []
    if (comps.length === 0 && m.company_name && m.company_name !== 'None') {
      comps = [m.company_name]
    }

    setFormData({
      ip: m.ip || '',
      port: m.port || 4370,
      location: m.location || '',
      sn: m.sn || '',
      password: m.password || 0,
      protocol: m.protocol || 'TCP',
      company_names: comps,
      name: m.name || '',
      enabled: m.enabled !== undefined ? m.enabled : true,
      driver: m.driver || 'zk',
      sync_type: m.sync_type || 'interval',
      sync_interval: m.sync_interval || 20,
      sync_days: m.sync_days || [],
      sync_time: m.sync_time || '00:00'
    });
    setIntervalValue(sched.value);
    setIntervalUnit(sched.unit);
    setIsEditing(true);
    setEditSn(m.sn || `${m.ip}:${m.port}`);
    setShowModal(true);
  };

  const handleAddMachineClick = () => {
    setFormData(defaultFormData);
    setIntervalValue(20);
    setIntervalUnit('seconds');
    setIsEditing(false);
    setEditSn('');
    setShowModal(true);
  };

  const handleSaveMachine = async () => {
    if (formData.protocol === 'TCP' && !formData.ip) return toast.error('Enter IP Address')
    if (formData.protocol === 'HTTP' && !formData.sn) return toast.error('Enter Serial Number')

    let payload = { ...formData }

    if (payload.sync_type === 'interval') {
      const secs = intervalToSeconds(intervalValue, intervalUnit);
      if (secs < 20) {
        return toast.error('Minimum sync interval is 20 seconds');
      }
      payload.sync_interval = secs;
    } else {
      if (!payload.sync_days || payload.sync_days.length === 0) {
        return toast.error('Please select at least one day for scheduled sync');
      }
      if (!payload.sync_time) {
        return toast.error('Please specify a sync execution time');
      }
    }

    // Connect & test on addition for TCP machines
    if (formData.protocol === 'TCP' && !isEditing) {
      const t = toast.loading('Testing TCP connection to device...')
      setTesting(true)
      try {
        const res = await testConnection({ ip: formData.ip, port: formData.port, password: 0 })
        if (res.data.success) {
          toast.success('Connection Successful!', { id: t })
          payload.sn = res.data.serial_number
          payload.password = 0
          payload.sync_interval = 20 // default timer of 20s
          payload.enabled = true
          payload.company_names = []
          payload.name = ''
          if (res.data.driver) payload.driver = res.data.driver
        } else {
          toast.error(`Connection Failed: ${res.data.error}`, { id: t })
          setTesting(false)
          return
        }
      } catch (err) {
        toast.error('Connection Failed - Server unreachable', { id: t })
        setTesting(false)
        return
      }
      setTesting(false)
    }

    try {
      const res = await addMachine(payload)
      if (res.data.success) {
        toast.success(isEditing ? 'Machine Settings Updated' : 'Machine Added Successfully')
        resetFocus()
        setShowModal(false)
        fetchMachines()
      }
    } catch (err) {
      toast.error(isEditing ? 'Failed to update machine' : 'Failed to add machine')
    }
  }

  const handleDelete = (m) => {
    const identifier = m.sn || `${m.ip}:${m.port}`
    setConfirmModal({
      title: 'Delete Machine',
      message: `Are you sure you want to delete this machine (${m.name || m.location || identifier})? This action cannot be undone.`,
      isDanger: true,
      onConfirm: async () => {
        try {
          await removeMachine(identifier)
          toast.success('Machine Removed')
          fetchMachines()
        } catch (err) {
          toast.error('Failed to remove machine')
        }
      }
    })
  }

  const handlePull = async (sn) => {
    const t = toast.loading('Pulling records...')
    try {
      const res = await manualPull(sn)
      if (res.data.success) {
        toast.success(res.data.message || `Pulled ${res.data.records} records`, { id: t })
        fetchMachines()
      } else {
        toast.error(res.data.error || 'Pull failed', { id: t })
      }
    } catch (err) {
      toast.error('Server error', { id: t })
    }
  }
  
  const handleClear = (sn) => {
    setConfirmModal({
      title: 'Clear Device Logs',
      message: 'Are you sure you want to clear ALL attendance logs on this device? This action cannot be undone.',
      isDanger: true,
      onConfirm: async () => {
        const t = toast.loading('Clearing logs...')
        try {
          const res = await clearAttendance(sn)
          if (res.data.success) {
            toast.success(res.data.message || 'Logs cleared on device', { id: t })
          } else {
            toast.error(res.data.error || 'Clear failed', { id: t })
          }
        } catch (err) {
          toast.error('Server error', { id: t })
        }
      }
    })
  }

  const handleSyncTime = async (sn) => {
    const t = toast.loading('Syncing device time...')
    try {
      const res = await syncTime(sn)
      if (res.data.success) {
        toast.success(res.data.message || `Time synced successfully`, { id: t })
      } else {
        toast.error(res.data.error || 'Sync failed', { id: t })
      }
    } catch (err) {
      toast.error('Server error', { id: t })
    }
  }

  const handleDeviceInfo = async (sn) => {
    const t = toast.loading('Fetching device info...')
    try {
      const res = await getDeviceInfo(sn)
      if (!res.data.error) {
        toast.dismiss(t)
        setInfoModal(res.data)
      } else {
        toast.error(res.data.error || 'Failed to get info', { id: t })
      }
    } catch (err) {
      toast.error('Server error', { id: t })
    }
  }

  const handleToggleSync = async (sn) => {
    const t = toast.loading('Toggling sync state...')
    try {
      const res = await toggleMachine(sn)
      if (res.data.success) {
        toast.success(res.data.enabled ? 'Sync Enabled' : 'Sync Paused', { id: t })
        fetchMachines()
      } else {
        toast.error('Failed to toggle sync', { id: t })
      }
    } catch (err) {
      toast.error('Failed to toggle sync', { id: t })
    }
  }

  const filteredMachines = machines.filter(m => {
    const name = m.name || m.location || ''
    const identifier = m.sn || `${m.ip}:${m.port}`
    return (
      name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      identifier.toLowerCase().includes(searchQuery.toLowerCase()) ||
      m.ip.includes(searchQuery)
    );
  })

  return (
    <div>
      <div className="section-header-card red">
        <div>
          <h2>Total Machines</h2>
          <div className="big-num">{machines.length}</div>
        </div>
        <MdFingerprint size={64} style={{ opacity: 0.3 }} />
      </div>

      <div className="filter-bar" style={{ justifyContent: 'space-between' }}>
        <div className="search-box" style={{ background: 'var(--color-card)' }}>
          <MdSearch size={18} color="var(--color-text-muted)" />
          <input
            type="text"
            placeholder="Search machine (name, SN, IP)..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
          />
        </div>
        {isLoggedIn && (
          <div style={{ display: 'flex', gap: '10px' }}>
            <button className="btn btn-primary" onClick={handleAddMachineClick}>Add Machine</button>
          </div>
        )}
      </div>

      {loading ? (
        <div className="empty-state">
          <div className="spinner" style={{ borderColor: 'rgba(0,0,0,0.1)', borderTopColor: 'var(--color-accent)' }}></div>
          Loading machines...
        </div>
      ) : filteredMachines.length === 0 ? (
        <div className="empty-state">
          <MdFingerprint />
          <p>{searchQuery ? 'No matching machines found.' : 'No machines configured yet.'}</p>
        </div>
      ) : (
        <div className="machines-grid">
          {filteredMachines.map((m, i) => {
            const snKey = m.sn || `${m.ip}:${m.port}`
            return (
              <div key={snKey} className={`machine-card ${!m.enabled ? 'paused' : ''}`}>
                <div className="machine-card-header">
                  <span className="machine-card-title">{m.name || m.location || `Device ${m.ip}`}</span>
                  <span className={`status-badge ${m.status}`}>{m.status}</span>
                </div>
                
                {/* Enabled Toggle Row */}
                <div className="machine-info-row toggle-sync-row">
                  <span className="machine-info-label">Sync Action</span>
                  <button 
                    className={`btn btn-sm toggle-btn ${m.enabled ? 'btn-active' : 'btn-paused'}`}
                    disabled={!isLoggedIn}
                    onClick={() => handleToggleSync(snKey)}
                    title={!isLoggedIn ? "Login to toggle syncing state" : m.enabled ? "Click to Pause Syncing" : "Click to Enable Syncing"}
                  >
                    {m.enabled ? (
                      <><MdToggleOn className="toggle-icon-on" /> Active</>
                    ) : (
                      <><MdToggleOff className="toggle-icon-off" /> Paused</>
                    )}
                  </button>
                </div>

                <div className="machine-info-row">
                  <span className="machine-info-label">Protocol</span>
                  <span className="machine-info-value" style={{ color: m.protocol === 'HTTP' ? 'var(--color-accent)' : 'inherit', fontWeight: 'bold' }}>
                    {m.protocol || 'TCP'}
                  </span>
                </div>
                <div className="machine-info-row">
                  <span className="machine-info-label">Assigned Companies</span>
                  <span className="machine-info-value">
                    {m.company_names && m.company_names.length > 0 
                      ? m.company_names.join(', ') 
                      : m.company_name && m.company_name !== 'None' 
                        ? m.company_name 
                        : 'None'}
                  </span>
                </div>
                <div className="machine-info-row">
                  <span className="machine-info-label">IP Address</span>
                  <span className="machine-info-value">{m.ip || '---'}:{m.port}</span>
                </div>
                <div className="machine-info-row">
                  <span className="machine-info-label">Serial No.</span>
                  <span className="machine-info-value">{m.sn || '---'}</span>
                </div>
                <div className="machine-info-row">
                  <span className="machine-info-label">Schedule</span>
                  <span className="machine-info-value" style={{ fontWeight: '600', color: 'var(--color-accent)' }}>
                    {formatSchedule(m)}
                  </span>
                </div>
                <div className="machine-info-row" style={{ border: 'none', color: 'var(--color-text-muted)', fontSize: '11px', marginTop: '4px' }}>
                  {m.last_sync ? `Last sync: ${new Date(m.last_sync).toLocaleTimeString()}` : 'Never synced'}
                </div>

                <div className="machine-card-actions" style={{ display: 'flex', flexWrap: 'wrap', gap: '5px' }}>
                  <button className="btn btn-ghost btn-sm" style={{ flex: '1 1 30%' }} title="Manual Pull" onClick={() => handlePull(m.sn)} disabled={!m.enabled}>
                    <MdRefresh /> Pull
                  </button>
                  
                  {isLoggedIn && (
                    <>
                      <button className="btn btn-ghost btn-sm" style={{ flex: '1 1 30%' }} title="Sync Time" onClick={() => handleSyncTime(m.sn)} disabled={!m.enabled}>
                        Sync Time
                      </button>
                      <button className="btn btn-ghost btn-sm" style={{ flex: '1 1 30%' }} title="Device Info" onClick={() => handleDeviceInfo(m.sn)} disabled={!m.enabled}>
                        Info
                      </button>
                      <button className="btn btn-ghost btn-sm" style={{ flex: '1 1 30%' }} title="Edit Settings" onClick={() => handleEdit(m)}>
                        <MdSettings /> Edit
                      </button>
                      <button className="btn btn-ghost btn-sm" style={{ flex: '1 1 30%', borderColor: 'var(--card-red)', color: 'var(--card-red)' }} title="Clear Logs" onClick={() => handleClear(m.sn)} disabled={!m.enabled}>
                        <MdClearAll /> Clear
                      </button>
                      <button className="btn btn-ghost btn-sm btn-delete-company" style={{ flex: '1 1 30%' }} onClick={() => handleDelete(m)} title="Delete Machine">
                        <MdDelete /> Delete
                      </button>
                    </>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Add/Edit Machine Modal */}
      {showModal && (
        <div className="modal-overlay">
          <div className="modal" style={{ maxHeight: '90vh', overflowY: 'auto' }}>
            <h2>{isEditing ? 'Edit Machine Settings' : 'Add New Machine'}</h2>
            
            {!isEditing && (
              <div className="form-group">
                <label>Protocol</label>
                <select className="form-control" value={formData.protocol} onChange={e => setFormData({ ...formData, protocol: e.target.value })}>
                  <option value="TCP">TCP (Pull) - Auto Detect</option>
                  <option value="HTTP">HTTP (Push/ADMS) - Manual Entry</option>
                </select>
              </div>
            )}

            {/* If adding, show minimal fields. If editing, show all detailed configurations */}
            {!isEditing ? (
              <>
                {formData.protocol === 'TCP' ? (
                  <div className="form-group" style={{ display: 'flex', gap: '10px' }}>
                    <div style={{ flex: 2 }}>
                      <label>IP Address</label>
                      <input type="text" value={formData.ip} onChange={e => setFormData({ ...formData, ip: e.target.value })} placeholder="e.g. 192.168.1.100" />
                    </div>
                    <div style={{ flex: 1 }}>
                      <label>Port</label>
                      <input type="number" value={formData.port} onChange={e => setFormData({ ...formData, port: parseInt(e.target.value) || 0 })} />
                    </div>
                  </div>
                ) : (
                  <div className="form-group">
                    <label>Serial Number</label>
                    <input type="text" value={formData.sn} onChange={e => setFormData({ ...formData, sn: e.target.value })} placeholder="e.g. NYU12345" />
                  </div>
                )}
              </>
            ) : (
              // EDITING FLOW (All settings configurable)
              <>
                <div className="form-group">
                  <label>Custom Machine Name</label>
                  <input type="text" value={formData.name} onChange={e => setFormData({ ...formData, name: e.target.value })} placeholder="e.g. Main Exit Gate" />
                </div>

                <div className="form-group" style={{ display: 'flex', gap: '10px' }}>
                  <div style={{ flex: 1 }}>
                    <label>Protocol</label>
                    <select className="form-control" value={formData.protocol} onChange={e => setFormData({ ...formData, protocol: e.target.value })}>
                      <option value="TCP">TCP (Pull Mode)</option>
                      <option value="HTTP">HTTP (Push/ADMS Mode)</option>
                    </select>
                  </div>
                  <div style={{ flex: 1 }}>
                    <label>Device Driver</label>
                    <select className="form-control" value={formData.driver} onChange={e => setFormData({ ...formData, driver: e.target.value })}>
                      <option value="zk">ZKTeco Standard (ZK)</option>
                      <option value="fk">FK / AMT Series (FK)</option>
                    </select>
                  </div>
                </div>

                <div className="form-group" style={{ display: 'flex', gap: '10px' }}>
                  <div style={{ flex: 2 }}>
                    <label>IP Address / Host</label>
                    <input type="text" value={formData.ip} onChange={e => setFormData({ ...formData, ip: e.target.value })} />
                  </div>
                  <div style={{ flex: 1 }}>
                    <label>Port</label>
                    <input type="number" value={formData.port} onChange={e => setFormData({ ...formData, port: parseInt(e.target.value) || 4370 })} />
                  </div>
                </div>

                <div className="form-group">
                  <label>Serial Number</label>
                  <input type="text" disabled value={formData.sn} />
                </div>

                <div className="form-group" style={{ display: 'flex', gap: '10px' }}>
                  <div style={{ flex: 1 }}>
                    <label>Location / Branch (Optional)</label>
                    <input type="text" value={formData.location} onChange={e => setFormData({ ...formData, location: e.target.value })} placeholder="e.g. Head Office" />
                  </div>
                  <div style={{ flex: 1 }}>
                    <label>Comm Key / Password</label>
                    <input type="number" value={formData.password} onChange={e => setFormData({ ...formData, password: parseInt(e.target.value) || 0 })} />
                  </div>
                </div>

                {/* Company Multiselect checkboxes */}
                <div className="form-group">
                  <label style={{ fontWeight: '700', marginBottom: '8px', display: 'block' }}>Assigned Companies</label>
                  <div className="companies-checkbox-list">
                    {companies.map(c => {
                      const checked = formData.company_names && formData.company_names.includes(c);
                      return (
                        <label key={c} className="company-checkbox-label">
                          <input 
                            type="checkbox" 
                            checked={checked} 
                            onChange={() => {
                              const list = formData.company_names || [];
                              const updated = checked 
                                ? list.filter(item => item !== c)
                                : [...list, c];
                              setFormData({ ...formData, company_names: updated });
                            }} 
                          />
                          <span>{c}</span>
                        </label>
                      );
                    })}
                    {companies.length === 0 && (
                      <div className="no-companies-text">No companies created. Configure them in the Companies tab first.</div>
                    )}
                  </div>
                </div>

                <h3 className="section-divider">Sync Scheduling</h3>
                
                <div className="form-group">
                  <label>Sync Mode</label>
                  <select className="form-control" value={formData.sync_type} onChange={e => setFormData({ ...formData, sync_type: e.target.value })}>
                    <option value="interval">Interval-based</option>
                    <option value="cron">Specific Days & Time</option>
                  </select>
                </div>

                {formData.sync_type === 'interval' ? (
                  <div className="form-group" style={{ display: 'flex', gap: '10px' }}>
                    <div style={{ flex: 1 }}>
                      <label>Interval Value</label>
                      <input 
                        type="number" 
                        min={intervalUnit === 'seconds' ? 20 : 1}
                        value={intervalValue} 
                        onChange={e => {
                          const val = parseInt(e.target.value) || 0;
                          setIntervalValue(val);
                          setFormData(prev => ({
                            ...prev,
                            sync_interval: intervalToSeconds(val, intervalUnit)
                          }));
                        }} 
                      />
                    </div>
                    <div style={{ flex: 1 }}>
                      <label>Interval Unit</label>
                      <select 
                        className="form-control" 
                        value={intervalUnit} 
                        onChange={e => {
                          const unit = e.target.value;
                          setIntervalUnit(unit);
                          let val = intervalValue;
                          if (unit === 'seconds' && val < 20) {
                            val = 20;
                            setIntervalValue(20);
                          }
                          setFormData(prev => ({
                            ...prev,
                            sync_interval: intervalToSeconds(val, unit)
                          }));
                        }}
                      >
                        <option value="seconds">Seconds (min 20)</option>
                        <option value="minutes">Minutes</option>
                        <option value="hours">Hours</option>
                        <option value="days">Days</option>
                        <option value="weeks">Weeks</option>
                      </select>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="form-group">
                      <label>Days of the Week</label>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', padding: '6px 0' }}>
                        {['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'].map(day => {
                          const checked = formData.sync_days.includes(day);
                          return (
                            <label key={day} style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', cursor: 'pointer', textTransform: 'capitalize', fontSize: '12px', fontWeight: '500', marginRight: '8px', color: 'var(--color-text)' }}>
                              <input 
                                type="checkbox" 
                                checked={checked} 
                                style={{ width: 'auto', margin: 0 }}
                                onChange={() => {
                                  const updatedDays = checked 
                                    ? formData.sync_days.filter(d => d !== day)
                                    : [...formData.sync_days, day];
                                  setFormData({ ...formData, sync_days: updatedDays });
                                }} 
                              />
                              {day}
                            </label>
                          );
                        })}
                      </div>
                    </div>
                    <div className="form-group">
                      <label>Sync Execution Time</label>
                      <input 
                        type="time" 
                        value={formData.sync_time} 
                        onChange={e => setFormData({ ...formData, sync_time: e.target.value })} 
                      />
                    </div>
                  </>
                )}
              </>
            )}

            <div className="modal-actions">
              <button className="btn btn-ghost" onClick={() => { resetFocus(); setShowModal(false); }}>Cancel</button>
              <button className="btn btn-primary" onClick={handleSaveMachine}>
                {isEditing ? 'Save Settings' : 'Add Machine'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Info Modal */}
      {infoModal && (
        <div className="modal-overlay">
          <div className="modal" style={{ maxWidth: '450px' }}>
            <h2>Device Information</h2>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px', margin: '20px 0' }}>
              <div><strong>Serial No:</strong> {infoModal.serial_number}</div>
              <div><strong>Device Time:</strong> {infoModal.device_time}</div>
              <div><strong>IP Address:</strong> {infoModal.ip}</div>
              <div><strong>Firmware:</strong> {infoModal.firmware}</div>
              <div><strong>Platform:</strong> {infoModal.platform}</div>
              <div><strong>MAC Address:</strong> {infoModal.mac}</div>
              <div><strong>Total Logs:</strong> {infoModal.records}</div>
              <div><strong>Total Users:</strong> {infoModal.users}</div>
              <div><strong>Total Fingers:</strong> {infoModal.fingers}</div>
            </div>
            <div className="modal-actions">
              <button className="btn btn-primary" onClick={() => { resetFocus(); setInfoModal(null); }}>Close</button>
            </div>
          </div>
        </div>
      )}

      {/* Confirm Dialog Modal */}
      {confirmModal && (
        <div className="modal-overlay">
          <div className="modal" style={{ maxWidth: '400px' }}>
            <h2>{confirmModal.title || 'Confirm Action'}</h2>
            <p style={{ margin: '15px 0', color: 'var(--color-text-muted)', fontSize: '14px', lineHeight: '1.5' }}>{confirmModal.message}</p>
            <div className="modal-actions">
              <button className="btn btn-ghost" onClick={() => { resetFocus(); setConfirmModal(null); }}>Cancel</button>
              <button className={confirmModal.isDanger ? "btn btn-danger" : "btn btn-primary"} onClick={() => {
                resetFocus();
                confirmModal.onConfirm();
                setConfirmModal(null);
              }}>Confirm</button>
            </div>
          </div>
        </div>
      )}

      <style>{`
        .paused {
          opacity: 0.75;
          border-color: #cbd5e1 !important;
          background: #f8fafc !important;
        }
        .toggle-sync-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 8px 0;
          border-bottom: 1px solid var(--color-border);
        }
        .toggle-btn {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          font-size: 0.8rem;
          padding: 3px 8px;
          border-radius: 99px;
          font-weight: 700;
          cursor: pointer;
        }
        .btn-active {
          background: #dcfce7;
          color: #166534;
        }
        .btn-active:hover {
          background: #bbf7d0;
        }
        .btn-paused {
          background: #fee2e2;
          color: #991b1b;
        }
        .btn-paused:hover {
          background: #fecaca;
        }
        .toggle-icon-on {
          font-size: 1.25rem;
          color: #16a34a;
        }
        .toggle-icon-off {
          font-size: 1.25rem;
          color: #dc2626;
        }
        .companies-checkbox-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
          max-height: 150px;
          overflow-y: auto;
          border: 1px solid var(--color-border);
          border-radius: var(--radius-sm);
          padding: 10px;
          background: var(--color-bg);
        }
        .company-checkbox-label {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 0.85rem;
          font-weight: 500;
          color: var(--color-text);
          cursor: pointer;
        }
        .company-checkbox-label input[type="checkbox"] {
          width: 16px;
          height: 16px;
          accent-color: var(--color-accent);
          cursor: pointer;
        }
        .no-companies-text {
          font-size: 0.8rem;
          color: var(--color-text-muted);
          font-style: italic;
        }
        .section-divider {
          font-size: 0.78rem;
          font-weight: 800;
          color: var(--color-text-muted);
          text-transform: uppercase;
          letter-spacing: 0.5px;
          margin-top: 20px;
          margin-bottom: 10px;
          border-bottom: 1px solid var(--color-border);
          padding-bottom: 4px;
        }
      `}</style>
    </div>
  )
}
