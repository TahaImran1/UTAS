import React, { useEffect, useState } from 'react'
import { MdBusiness, MdFingerprint, MdSearch, MdAdd, MdCheck, MdClose, MdLinkOff } from 'react-icons/md'
import { getCompanies, getMachines, mapDevicesToCompany } from '../api/client'
import toast from 'react-hot-toast'

export default function Companies() {
  const [allMachines, setAllMachines] = useState([])
  const [companyStats, setCompanyStats] = useState([])
  const [unassignedMachines, setUnassignedMachines] = useState([])
  const [loading, setLoading] = useState(true)
  
  // Modals
  const [showAddModal, setShowAddModal] = useState(false)
  const [manageCompany, setManageCompany] = useState(null) // { name, machines: [] }
  
  // Form State
  const [newCompanyName, setNewCompanyName] = useState('')
  const [selectedSNS, setSelectedSNS] = useState([])
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 10000)
    return () => clearInterval(interval)
  }, [])

  const fetchData = async () => {
    try {
      const [compRes, machRes] = await Promise.all([getCompanies(), getMachines()])
      
      const machineList = machRes.data || []
      const companyList = compRes.data.companies || ['None']

      setAllMachines(machineList)

      // Calculate stats
      const stats = companyList.filter(n => n !== 'None').map(name => {
        const matchingMachines = machineList.filter(m => m.company_name === name)
        return {
          name,
          machineCount: matchingMachines.length,
          onlineCount: matchingMachines.filter(m => m.status === 'online').length,
          machines: matchingMachines
        }
      })

      setCompanyStats(stats)
      setUnassignedMachines(machineList.filter(m => m.company_name === 'None' || !m.company_name))
      
      // Update manage modal if open
      if(manageCompany) {
          const updated = stats.find(s => s.name === manageCompany.name)
          if(updated) setManageCompany(updated)
      }
    } catch (err) {
      toast.error('Failed to load company data')
    } finally {
      setLoading(false)
    }
  }

  const handleToggleSelect = (sn) => {
    setSelectedSNS(prev => 
      prev.includes(sn) ? prev.filter(s => s !== sn) : [...prev, sn]
    )
  }

  const handleMapAction = async (companyName, sns) => {
    setSaving(true)
    try {
      const res = await mapDevicesToCompany({ company_name: companyName, sns: sns })
      if(res.data.success) {
        toast.success(res.data.message)
        setSelectedSNS([])
        fetchData()
        return true
      } else {
        toast.error(res.data.error)
      }
    } catch (err) {
      toast.error('Mapping failed')
    } finally {
      setSaving(false)
    }
    return false
  }

  const handleRegisterCompany = async () => {
    if(!newCompanyName.trim()) return toast.error('Enter company name')
    if(selectedSNS.length === 0) return toast.error('Select at least one device to link')
    
    const ok = await handleMapAction(newCompanyName, selectedSNS)
    if(ok) {
        setShowAddModal(false)
        setNewCompanyName('')
    }
  }

  const handleUnlink = async (sn) => {
      await handleMapAction('None', [sn])
  }

  return (
    <div>
      <div className="section-header-card blue">
        <div>
          <h2>Total Companies</h2>
          <div className="big-num">{companyStats.length}</div>
        </div>
        <MdBusiness size={64} style={{opacity: 0.3}} />
      </div>

      <div className="filter-bar" style={{justifyContent: 'space-between'}}>
        <div className="search-box" style={{background: 'var(--color-card)'}}>
          <MdSearch size={18} color="var(--color-text-muted)" />
          <input type="text" placeholder="Search company..." />
        </div>
        <button className="btn btn-primary" onClick={() => setShowAddModal(true)}>
          <MdAdd /> Add Company
        </button>
      </div>

      {loading && companyStats.length === 0 ? (
        <div className="empty-state">Loading...</div>
      ) : companyStats.length === 0 ? (
        <div className="empty-state">
           <MdBusiness />
           <p>No companies registered yet.</p>
           <button className="btn btn-ghost" onClick={() => setShowAddModal(true)}>Register your first company</button>
        </div>
      ) : (
        <div className="machines-grid">
          {companyStats.map(c => (
            <div key={c.name} className="machine-card">
              <div className="machine-card-header">
                <span className="machine-card-title">{c.name}</span>
                <span className="status-badge" style={{background: 'var(--color-accent-soft)', color: 'var(--color-accent)'}}>
                    {c.machineCount} Device(s)
                </span>
              </div>
              
              <div className="machine-info-row" style={{border: 'none'}}>
                <span className="machine-info-label">Active Machines</span>
                <span className="machine-info-value" style={{color: 'var(--color-success)'}}>
                    {c.onlineCount} Online
                </span>
              </div>

              <div className="machine-card-actions">
                <button className="btn btn-ghost btn-sm" style={{flex: 1}} onClick={() => setManageCompany(c)}>
                  <MdBusiness /> Manage Company
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add Company Modal */}
      {showAddModal && (
        <div className="modal-overlay">
          <div className="modal" style={{maxWidth: '500px'}}>
            <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px'}}>
                <h2>Register New Company</h2>
                <MdClose style={{cursor: 'pointer'}} onClick={() => setShowAddModal(false)} />
            </div>
            
            <div className="form-group">
              <label>Company Name</label>
              <input 
                type="text" 
                value={newCompanyName} 
                onChange={e => setNewCompanyName(e.target.value)} 
                placeholder="e.g. Techno Group HQ" 
              />
            </div>

            <div className="form-group">
              <label>Link Available Devices ({unassignedMachines.length})</label>
              <div className="unassigned-list" style={{maxHeight: '200px', overflowY: 'auto', border: '1px solid var(--color-border)', borderRadius: '8px', marginTop: '8px'}}>
                {unassignedMachines.length === 0 ? (
                  <div style={{padding: '20px', textAlign: 'center', fontSize: '13px', color: 'var(--color-text-muted)'}}>
                    No unassigned devices found. Add a machine first!
                  </div>
                ) : (
                  unassignedMachines.map(m => (
                    <div 
                      key={m.sn} 
                      onClick={() => handleToggleSelect(m.sn)}
                      style={{
                        padding: '10px 15px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        cursor: 'pointer',
                        borderBottom: '1px solid var(--color-border)',
                        background: selectedSNS.includes(m.sn) ? 'var(--color-accent-soft)' : 'transparent'
                      }}
                    >
                      <div>
                        <div style={{fontWeight: 'bold', fontSize: '14px'}}>{m.location || 'New Device'}</div>
                        <div style={{fontSize: '12px', color: 'var(--color-text-muted)'}}>{m.protocol} | SN: {m.sn}</div>
                      </div>
                      {selectedSNS.includes(m.sn) && <MdCheck color="var(--color-accent)" size={20} />}
                    </div>
                  ))
                )}
              </div>
            </div>

            <div className="modal-actions">
              <button className="btn btn-ghost" onClick={() => setShowAddModal(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={handleRegisterCompany} disabled={saving || !newCompanyName}>
                {saving ? 'Registering...' : 'Register & Link Devices'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Manage Company Modal */}
      {manageCompany && (
        <div className="modal-overlay">
            <div className="modal" style={{maxWidth: '600px', width: '90%'}}>
               <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px'}}>
                    <div>
                        <h2 style={{margin: 0}}>Manage: {manageCompany.name}</h2>
                        <span style={{fontSize: '12px', color: 'var(--color-text-muted)'}}>{manageCompany.machineCount} Linked Devices</span>
                    </div>
                    <MdClose style={{cursor: 'pointer'}} size={24} onClick={() => setManageCompany(null)} />
                </div>

                <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px'}}>
                    {/* Column 1: Currently Linked */}
                    <div>
                        <label style={{fontWeight: 'bold', display: 'block', marginBottom: '10px'}}>Linked Devices</label>
                        <div style={{border: '1px solid var(--color-border)', borderRadius: '8px', maxHeight: '300px', overflowY: 'auto'}}>
                            {manageCompany.machines.map(m => (
                                <div key={m.sn} style={{padding: '10px', borderBottom: '1px solid var(--color-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
                                    <div style={{fontSize: '13px'}}>
                                        <div style={{fontWeight: '600'}}>{m.location}</div>
                                        <div style={{fontSize: '11px', color: 'var(--color-text-muted)'}}>{m.sn}</div>
                                    </div>
                                    <button className="btn btn-ghost btn-sm" title="Unlink" onClick={() => handleUnlink(m.sn)} style={{color: 'var(--card-red)', borderColor: 'var(--card-red)'}}>
                                        <MdLinkOff />
                                    </button>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Column 2: Unassigned */}
                    <div>
                        <label style={{fontWeight: 'bold', display: 'block', marginBottom: '10px'}}>Add Unassigned Machines</label>
                        <div style={{border: '1px solid var(--color-border)', borderRadius: '8px', maxHeight: '300px', overflowY: 'auto'}}>
                            {unassignedMachines.length === 0 ? (
                                <div style={{padding: '20px', textAlign: 'center', fontSize: '12px', color: 'var(--color-text-muted)'}}>No more unassigned devices.</div>
                            ) : (
                                unassignedMachines.map(m => (
                                    <div 
                                        key={m.sn} 
                                        onClick={() => handleToggleSelect(m.sn)}
                                        style={{
                                            padding: '10px', 
                                            borderBottom: '1px solid var(--color-border)', 
                                            display: 'flex', 
                                            justifyContent: 'space-between', 
                                            alignItems: 'center', 
                                            cursor: 'pointer',
                                            background: selectedSNS.includes(m.sn) ? 'var(--color-accent-soft)' : 'transparent'
                                        }}
                                    >
                                        <div style={{fontSize: '13px'}}>
                                            <div style={{fontWeight: '600'}}>{m.location}</div>
                                            <div style={{fontSize: '11px', color: 'var(--color-text-muted)'}}>{m.sn}</div>
                                        </div>
                                        {selectedSNS.includes(m.sn) && <MdCheck color="var(--color-accent)" size={18} />}
                                    </div>
                                ))
                            )}
                        </div>
                        {selectedSNS.length > 0 && (
                            <button className="btn btn-primary" style={{width: '100%', marginTop: '10px'}} onClick={() => handleMapAction(manageCompany.name, selectedSNS)}>
                                Link {selectedSNS.length} Device(s)
                            </button>
                        ) }
                    </div>
                </div>

                <div className="modal-actions" style={{marginTop: '30px'}}>
                    <button className="btn btn-ghost" onClick={() => setManageCompany(null)}>Done</button>
                </div>
            </div>
        </div>
      )}
    </div>
  )
}
