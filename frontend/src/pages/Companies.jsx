import React, { useEffect, useState } from 'react'
import {
  MdBusiness, MdSearch, MdAdd, MdCheck, MdClose, MdLinkOff,
  MdStorage, MdDelete, MdInfoOutline, MdDevices
} from 'react-icons/md'
import {
  getCompanies,
  getMachines,
  addCompany,
  deleteCompany,
  mapCompanyToDb,
  getCompanyMappings,
  getDbProfiles,
  addMachine
} from '../api/client'
import toast from 'react-hot-toast'

export default function Companies() {
  const [allMachines, setAllMachines] = useState([])
  const [companyStats, setCompanyStats] = useState([])
  const [unassignedMachines, setUnassignedMachines] = useState([])
  const [dbProfiles, setDbProfiles] = useState({})
  const [companyMappings, setCompanyMappings] = useState({})
  const [loading, setLoading] = useState(true)
  
  // Modals
  const [showAddModal, setShowAddModal] = useState(false)
  const [manageCompany, setManageCompany] = useState(null) // company stats object
  const [searchQuery, setSearchQuery] = useState('')
  
  // Form State
  const [newCompanyName, setNewCompanyName] = useState('')
  const [selectedSNS, setSelectedSNS] = useState([])
  const [saving, setSaving] = useState(false)
  const [confirmModal, setConfirmModal] = useState(null)
  
  const resetFocus = () => {
    if (document.activeElement && typeof document.activeElement.blur === 'function') {
      document.activeElement.blur();
    }
  }

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 10000)
    return () => clearInterval(interval)
  }, [])

  const fetchData = async () => {
    try {
      const [compRes, machRes, mappingsRes, profilesRes] = await Promise.all([
        getCompanies(),
        getMachines(),
        getCompanyMappings(),
        getDbProfiles()
      ])
      
      const machineList = machRes.data || []
      const companyList = compRes.data.companies || []
      const mappings = mappingsRes.data || {}
      const profiles = profilesRes.data || {}

      setAllMachines(machineList)
      setCompanyMappings(mappings)
      setDbProfiles(profiles)

      // Calculate stats
      const stats = companyList.filter(n => n !== 'None').map(name => {
        const matchingMachines = machineList.filter(m => 
          (m.company_names && m.company_names.includes(name)) || m.company_name === name
        )
        return {
          name,
          dbProfile: mappings[name] || 'None',
          machineCount: matchingMachines.length,
          onlineCount: matchingMachines.filter(m => m.status === 'online').length,
          machines: matchingMachines
        }
      })

      setCompanyStats(stats)
      setUnassignedMachines(machineList.filter(m => 
        (!m.company_names || m.company_names.length === 0) && (!m.company_name || m.company_name === 'None')
      ))
      
      // Update manage modal if open
      if (manageCompany) {
        const updated = stats.find(s => s.name === manageCompany.name)
        if (updated) setManageCompany(updated)
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
      for (const sn of sns) {
        const machine = allMachines.find(m => m.sn === sn)
        if (machine) {
          const companyNames = machine.company_names || []
          if (!companyNames.includes(companyName)) {
            companyNames.push(companyName)
          }
          await addMachine({ ...machine, company_names: companyNames })
        }
      }
      toast.success(`Linked devices to ${companyName}`)
      setSelectedSNS([])
      fetchData()
      return true
    } catch (err) {
      toast.error('Mapping failed')
    } finally {
      setSaving(false)
    }
    return false
  }

  const handleRegisterCompany = async () => {
    const cleanedName = newCompanyName.trim()
    if (!cleanedName) return toast.error('Enter company name')
    
    setSaving(true)
    try {
      const res1 = await addCompany(cleanedName)
      if (!res1.data.success) {
        toast.error('Failed to register company')
        setSaving(false)
        return
      }

      if (selectedSNS.length > 0) {
        await handleMapAction(cleanedName, selectedSNS)
      } else {
        toast.success(`Company "${cleanedName}" registered successfully`)
      }

      setShowAddModal(false)
      setNewCompanyName('')
      setSelectedSNS([])
      fetchData()
    } catch (e) {
      toast.error('Failed to register company')
    } finally {
      setSaving(false)
    }
  }

  const handleUnlink = async (machine, companyName) => {
    if (document.activeElement && typeof document.activeElement.blur === 'function') {
      document.activeElement.blur();
    }
    try {
      const updatedNames = (machine.company_names || []).filter(c => c !== companyName)
      const res = await addMachine({ ...machine, company_names: updatedNames })
      if (res.data.success) {
        toast.success(`Unlinked device from ${companyName}`)
        fetchData()
      } else {
        toast.error('Failed to unlink device')
      }
    } catch (err) {
      toast.error('Failed to unlink device')
    }
  }

  const handleDeleteCompany = (name) => {
    resetFocus()
    setConfirmModal({
      title: 'Delete Company',
      message: `Are you sure you want to delete company "${name}"? Linked machines will be unmapped. This action cannot be undone.`,
      isDanger: true,
      onConfirm: async () => {
        resetFocus()
        try {
          // Unlink all machines that belong to this company
          const company = companyStats.find(s => s.name === name)
          if (company && company.machines.length > 0) {
            for (const m of company.machines) {
              const updatedNames = (m.company_names || []).filter(c => c !== name)
              await addMachine({ ...m, company_names: updatedNames })
            }
          }

          const res = await deleteCompany(name)
          if (res.data.success) {
            toast.success(`Company "${name}" deleted`)
            fetchData()
          } else {
            toast.error('Failed to delete company')
          }
        } catch (e) {
          toast.error(String(e))
        }
      }
    })
  }

  const handleBindDbProfile = async (companyName, profileName) => {
    try {
      const res = await mapCompanyToDb(companyName, profileName === 'None' ? '' : profileName)
      if (res.data.success) {
        toast.success(`Database mapped for ${companyName}`)
        fetchData()
      } else {
        toast.error('Failed to map database')
      }
    } catch (e) {
      toast.error(String(e))
    }
  }

  const filteredCompanies = companyStats.filter(c =>
    c.name.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const profileOptions = Object.keys(dbProfiles)

  return (
    <div className="companies-wrap">
      <div className="section-header-card blue">
        <div>
          <h2>Total Companies</h2>
          <div className="big-num">{companyStats.length}</div>
        </div>
        <MdBusiness size={64} style={{ opacity: 0.3 }} />
      </div>

      <div className="filter-bar" style={{ justifyContent: 'space-between' }}>
        <div className="search-box" style={{ background: 'var(--color-card)' }}>
          <MdSearch size={18} color="var(--color-text-muted)" />
          <input
            type="text"
            placeholder="Search company..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
          />
        </div>
        <button className="btn btn-primary" onClick={() => setShowAddModal(true)}>
          <MdAdd /> Add Company
        </button>
      </div>

      {loading && companyStats.length === 0 ? (
        <div className="empty-state">Loading Companies...</div>
      ) : filteredCompanies.length === 0 ? (
        <div className="empty-state">
          <MdBusiness />
          <p>{searchQuery ? 'No matching companies found.' : 'No companies registered yet.'}</p>
          <button className="btn btn-ghost" onClick={() => setShowAddModal(true)}>
            Register your first company
          </button>
        </div>
      ) : (
        <div className="machines-grid">
          {filteredCompanies.map(c => (
            <div key={c.name} className="machine-card company-card">
              <div className="machine-card-header">
                <span className="machine-card-title">{c.name}</span>
                <span className="status-badge" style={{ background: 'var(--color-accent-soft)', color: 'var(--color-accent)' }}>
                  {c.machineCount} Device(s)
                </span>
              </div>
              
              <div className="machine-info-row">
                <span className="machine-info-label">Active Machines</span>
                <span className="machine-info-value" style={{ color: 'var(--color-success)', fontWeight: 600 }}>
                  {c.onlineCount} Online
                </span>
              </div>

              {/* Database profile selector */}
              <div className="machine-info-row db-mapping-row">
                <span className="machine-info-label">
                  <MdStorage /> Database Profile
                </span>
                <select
                  value={c.dbProfile}
                  onChange={(e) => handleBindDbProfile(c.name, e.target.value)}
                  className="db-select"
                >
                  <option value="None">None (Logs ignored)</option>
                  {profileOptions.map(profileName => (
                    <option key={profileName} value={profileName}>
                      {profileName} ({dbProfiles[profileName].database})
                    </option>
                  ))}
                </select>
              </div>

              {c.dbProfile === 'None' && (
                <div className="warning-mapping-text">
                  <MdInfoOutline /> Assign a DB profile to start routing attendance logs.
                </div>
              )}

              <div className="machine-card-actions">
                <button className="btn btn-ghost btn-sm" style={{ flex: 1 }} onClick={() => setManageCompany(c)}>
                  <MdDevices /> Devices
                </button>
                <button
                  className="btn btn-ghost btn-sm btn-delete-company"
                  title="Delete Company"
                  onClick={() => handleDeleteCompany(c.name)}
                >
                  <MdDelete />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add Company Modal */}
      {showAddModal && (
        <div className="modal-overlay">
          <div className="modal" style={{ maxWidth: '500px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h2>Register New Company</h2>
              <MdClose style={{ cursor: 'pointer' }} onClick={() => {
                if (document.activeElement && typeof document.activeElement.blur === 'function') {
                  document.activeElement.blur();
                }
                setShowAddModal(false);
              }} />
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
              <label>Link Available Devices ({allMachines.length})</label>
              <div className="unassigned-list" style={{ maxHeight: '200px', overflowY: 'auto', border: '1px solid var(--color-border)', borderRadius: '8px', marginTop: '8px' }}>
                {allMachines.length === 0 ? (
                  <div style={{ padding: '20px', textAlign: 'center', fontSize: '13px', color: 'var(--color-text-muted)' }}>
                    No devices found. Add a machine first!
                  </div>
                ) : (
                  allMachines.map(m => (
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
                        <div style={{ fontWeight: 'bold', fontSize: '14px' }}>{m.name || m.location || 'New Device'}</div>
                        <div style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>
                          {m.protocol} | SN: {m.sn}
                          {m.company_names && m.company_names.length > 0 && ` (Linked: ${m.company_names.join(', ')})`}
                        </div>
                      </div>
                      {selectedSNS.includes(m.sn) && <MdCheck color="var(--color-accent)" size={20} />}
                    </div>
                  ))
                )}
              </div>
            </div>

            <div className="modal-actions">
              <button className="btn btn-ghost" onClick={() => {
                if (document.activeElement && typeof document.activeElement.blur === 'function') {
                  document.activeElement.blur();
                }
                setShowAddModal(false);
              }}>Cancel</button>
              <button className="btn btn-primary" onClick={handleRegisterCompany} disabled={saving || !newCompanyName}>
                {saving ? 'Registering...' : 'Register Company'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Manage Company Modal */}
      {manageCompany && (
        <div className="modal-overlay">
          <div className="modal" style={{ maxWidth: '600px', width: '90%' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <div>
                <h2 style={{ margin: 0 }}>Devices for {manageCompany.name}</h2>
                <span style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>{manageCompany.machineCount} Linked Devices</span>
              </div>
              <MdClose style={{ cursor: 'pointer' }} size={24} onClick={() => {
                if (document.activeElement && typeof document.activeElement.blur === 'function') {
                  document.activeElement.blur();
                }
                setManageCompany(null);
              }} />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
              {/* Column 1: Currently Linked */}
              <div>
                <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '10px' }}>Linked Devices</label>
                <div style={{ border: '1px solid var(--color-border)', borderRadius: '8px', maxHeight: '300px', overflowY: 'auto' }}>
                  {manageCompany.machines.length === 0 ? (
                    <div style={{ padding: '20px', textAlign: 'center', fontSize: '12px', color: 'var(--color-text-muted)' }}>No linked devices.</div>
                  ) : (
                    manageCompany.machines.map(m => (
                      <div key={m.sn} style={{ padding: '10px', borderBottom: '1px solid var(--color-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div style={{ fontSize: '13px' }}>
                          <div style={{ fontWeight: '600' }}>{m.name || m.location || m.ip}</div>
                          <div style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>SN: {m.sn}</div>
                        </div>
                        <button
                          className="btn btn-ghost btn-sm"
                          title="Unlink"
                          onClick={() => handleUnlink(m, manageCompany.name)}
                          style={{ color: 'var(--card-red)', borderColor: 'var(--card-red)' }}
                        >
                          <MdLinkOff />
                        </button>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Column 2: Available to Link */}
              <div>
                <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '10px' }}>Link Available Devices</label>
                <div style={{ border: '1px solid var(--color-border)', borderRadius: '8px', maxHeight: '300px', overflowY: 'auto' }}>
                  {allMachines.filter(m => !m.company_names || !m.company_names.includes(manageCompany.name)).length === 0 ? (
                    <div style={{ padding: '20px', textAlign: 'center', fontSize: '12px', color: 'var(--color-text-muted)' }}>No other devices available.</div>
                  ) : (
                    allMachines.filter(m => !m.company_names || !m.company_names.includes(manageCompany.name)).map(m => (
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
                        <div style={{ fontSize: '13px' }}>
                          <div style={{ fontWeight: '600' }}>{m.name || m.location || m.ip}</div>
                          <div style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>
                            SN: {m.sn}
                            {m.company_names && m.company_names.length > 0 && ` (Linked: ${m.company_names.join(', ')})`}
                          </div>
                        </div>
                        {selectedSNS.includes(m.sn) && <MdCheck color="var(--color-accent)" size={18} />}
                      </div>
                    ))
                  )}
                </div>
                {selectedSNS.length > 0 && (
                  <button className="btn btn-primary" style={{ width: '100%', marginTop: '10px' }} onClick={() => handleMapAction(manageCompany.name, selectedSNS)}>
                    Link {selectedSNS.length} Device(s)
                  </button>
                )}
              </div>
            </div>

            <div className="modal-actions" style={{ marginTop: '30px' }}>
              <button className="btn btn-ghost" onClick={() => {
                if (document.activeElement && typeof document.activeElement.blur === 'function') {
                  document.activeElement.blur();
                }
                setManageCompany(null);
              }}>Done</button>
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
        .companies-wrap {
          display: flex;
          flex-direction: column;
          gap: 1.5rem;
        }
        .company-card {
          position: relative;
        }
        .db-mapping-row {
          border-top: 1px solid var(--color-border);
          border-bottom: 1px solid var(--color-border);
          padding: 8px 0;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 10px;
        }
        .db-mapping-row svg {
          color: var(--color-accent);
          margin-right: 4px;
        }
        .db-select {
          padding: 4px 8px;
          border-radius: var(--radius-sm);
          border: 1px solid var(--color-border);
          background: var(--color-bg);
          color: var(--color-text);
          font-size: 0.82rem;
          outline: none;
          max-width: 180px;
        }
        .db-select:focus {
          border-color: var(--color-accent);
        }
        .warning-mapping-text {
          font-size: 0.72rem;
          color: #b45309;
          background: #fef3c7;
          padding: 6px 10px;
          border-radius: var(--radius-sm);
          display: flex;
          align-items: center;
          gap: 5px;
          font-weight: 500;
        }
        .btn-delete-company {
          color: #dc2626 !important;
        }
        .btn-delete-company:hover {
          background: #fee2e2 !important;
        }
      `}</style>
    </div>
  )
}
