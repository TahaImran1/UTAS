import React, { useState, useEffect } from 'react'
import {
  MdStorage, MdLink, MdCheckCircle, MdError, MdWarning,
  MdAdd, MdSettings, MdDelete, MdEdit, MdTableChart, MdRefresh, MdOutlineDataSaverOn
} from 'react-icons/md'
import {
  getDbProfiles,
  saveDbProfile,
  deleteDbProfile,
  testDbProfileConnection,
  createAttendanceTable
} from '../api/client'
import toast from 'react-hot-toast'

/* ─── Field component ─── */
const Field = ({ label, name, value, onChange, placeholder = '', type = 'text' }) => (
  <div className="profile-field">
    <label>{label}</label>
    <input type={type} name={name} value={value} onChange={onChange} placeholder={placeholder} />
  </div>
)

const defaultProfile = {
  database: 'Oracle',
  host: '',
  port: '1521',
  username: '',
  password: '',
  dbname: '',
  table: 'HR_EMP_INOUT_DETAIL',
  column1: 'EMPLOYEE_NO',
  column2: 'SWAP_TIME',
  column3: 'MACHINE_REF',
  col_pk: 'HR_ATT_LOG_ID',
  seq_pk: 'HR_EMP_INOUT_ID_S'
}

export default function DatabaseSettings() {
  const [profiles, setProfiles] = useState({})
  const [loading, setLoading] = useState(true)
  const [selectedProfile, setSelectedProfile] = useState(null) // profile name being edited/added
  const [form, setForm] = useState(defaultProfile)
  const [profileName, setProfileName] = useState('') // Custom key name
  const [isEditMode, setIsEditMode] = useState(false)
  const [busy, setBusy] = useState(false)
  const [testStatus, setTestStatus] = useState(null) // { success: boolean, msg: string }
  const [confirmModal, setConfirmModal] = useState(null)

  const resetFocus = () => {
    if (document.activeElement && typeof document.activeElement.blur === 'function') {
      document.activeElement.blur();
    }
  }

  useEffect(() => {
    fetchProfiles()
  }, [])

  const fetchProfiles = async () => {
    setLoading(true)
    try {
      const res = await getDbProfiles()
      setProfiles(res.data || {})
    } catch (e) {
      toast.error('Failed to load database profiles')
    } finally {
      setLoading(false)
    }
  }

  const handleSelectProfile = (name) => {
    setSelectedProfile(name)
    setProfileName(name)
    setForm({ ...defaultProfile, ...profiles[name] })
    setIsEditMode(true)
    setTestStatus(null)
  }

  const handleAddNew = () => {
    setSelectedProfile('_new')
    setProfileName('')
    setForm(defaultProfile)
    setIsEditMode(false)
    setTestStatus(null)
  }

  const handleFormChange = (e) => {
    const { name, value } = e.target
    setForm(prev => {
      const updated = { ...prev, [name]: value }
      // Auto-change port when database type switches
      if (name === 'database') {
        updated.port = value === 'Oracle' ? '1521' : '5432'
      }
      return updated
    })
  }

  const handleTestConnection = async () => {
    if (!form.host || !form.username || !form.password || !form.dbname) {
      toast.error('Please fill in the server details first')
      return
    }
    setBusy(true)
    setTestStatus(null)
    try {
      const res = await testDbProfileConnection(form)
      if (res.data.status === 'success') {
        setTestStatus({ success: true, msg: 'Connection successful!' })
        toast.success('Database connection verified!')
      } else {
        setTestStatus({ success: false, msg: res.data.message })
        toast.error('Connection failed')
      }
    } catch (e) {
      setTestStatus({ success: false, msg: String(e) })
      toast.error('Connection failed')
    } finally {
      setBusy(false)
    }
  }

  const handleCreateTable = async () => {
    setBusy(true)
    try {
      const payload = { config: form }
      const res = await createAttendanceTable(payload)
      if (res.data.status === 'success') {
        toast.success(res.data.message || 'Table created successfully!')
      } else {
        toast.error(res.data.message || 'Failed to create table')
      }
    } catch (e) {
      toast.error(String(e))
    } finally {
      setBusy(false)
    }
  }

  const handleSave = async () => {
    if (document.activeElement && typeof document.activeElement.blur === 'function') {
      document.activeElement.blur();
    }
    const nameKey = profileName.trim()
    if (!nameKey) {
      toast.error('Please enter a profile name')
      return
    }
    if (!form.host || !form.username || !form.dbname) {
      toast.error('Please fill in required database parameters')
      return
    }
    setBusy(true)
    try {
      const res = await saveDbProfile(nameKey, form)
      if (res.data.success) {
        toast.success(`Profile "${nameKey}" saved successfully!`)
        fetchProfiles()
        setSelectedProfile(null)
      } else {
        toast.error('Failed to save profile')
      }
    } catch (e) {
      toast.error(String(e))
    } finally {
      setBusy(false)
    }
  }

  const handleDelete = (name) => {
    resetFocus()
    setConfirmModal({
      title: 'Delete Database Profile',
      message: `Are you sure you want to delete profile "${name}"? This action cannot be undone.`,
      isDanger: true,
      onConfirm: async () => {
        resetFocus()
        try {
          const res = await deleteDbProfile(name)
          if (res.data.success) {
            toast.success(`Profile "${name}" deleted`)
            if (selectedProfile === name) {
              setSelectedProfile(null)
            }
            fetchProfiles()
          } else {
            toast.error('Failed to delete profile')
          }
        } catch (e) {
          toast.error(String(e))
        }
      }
    })
  }

  return (
    <div className="profile-wrap">
      <div className="profile-header">
        <MdStorage className="profile-header-icon" />
        <div>
          <h1>Database Profile Settings</h1>
          <p>Create and manage named database profiles to route attendance logs for your companies.</p>
        </div>
      </div>

      <div className="profile-container">
        {/* Left Side: Profiles List */}
        <div className="profile-sidebar">
          <div className="sidebar-header">
            <h3>Active Profiles</h3>
            <button className="btn btn-primary btn-sm" onClick={handleAddNew}>
              <MdAdd /> New Profile
            </button>
          </div>

          {loading ? (
            <div className="loading-state">
              <MdRefresh className="anim-spin" /> Loading Profiles...
            </div>
          ) : Object.keys(profiles).length === 0 ? (
            <div className="empty-state">
              <MdWarning />
              <p>No profiles configured yet. Click "New Profile" to get started.</p>
            </div>
          ) : (
            <div className="profile-list">
              {Object.keys(profiles).map(name => {
                const p = profiles[name]
                return (
                  <div
                    key={name}
                    className={`profile-item-card ${selectedProfile === name ? 'active' : ''}`}
                    onClick={() => handleSelectProfile(name)}
                  >
                    <div className="item-info">
                      <h4>{name}</h4>
                      <span>
                        {p.database} | {p.host}:{p.port}
                      </span>
                    </div>
                    <div className="item-actions">
                      <button
                        className="btn-icon btn-delete"
                        onClick={(e) => {
                          e.stopPropagation()
                          handleDelete(name)
                        }}
                      >
                        <MdDelete />
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Right Side: Add/Edit Form */}
        <div className="profile-main">
          {selectedProfile ? (
            <div className="profile-card">
              <div className="card-header">
                <h2>{isEditMode ? `Edit Profile: ${profileName}` : 'Create New DB Profile'}</h2>
              </div>

              <div className="card-body">
                {/* Profile Name input */}
                <div className="dw-grid-2">
                  <div className="profile-field full-width">
                    <label>Profile Identifier (Name)</label>
                    <input
                      type="text"
                      value={profileName}
                      onChange={(e) => setProfileName(e.target.value)}
                      placeholder="e.g. Oracle Primary, Staging Postgres"
                      disabled={isEditMode}
                    />
                  </div>
                </div>

                <h3 className="section-subtitle">1. Connection Credentials</h3>
                <div className="dw-grid-2">
                  <div className="profile-field">
                    <label>Database Type</label>
                    <select name="database" value={form.database} onChange={handleFormChange}>
                      <option value="Oracle">Oracle</option>
                      <option value="PostgreSQL">PostgreSQL</option>
                    </select>
                  </div>
                  <Field label="Host / IP" name="host" value={form.host} onChange={handleFormChange} placeholder="127.0.0.1" />
                  <Field label="Port" name="port" value={form.port} onChange={handleFormChange} placeholder="1521" />
                  <Field label="Username" name="username" value={form.username} onChange={handleFormChange} placeholder="HR" />
                  <Field label="Password" name="password" value={form.password} onChange={handleFormChange} type="password" />
                  <Field label="Service / Database Name" name="dbname" value={form.dbname} onChange={handleFormChange} placeholder="orcl" />
                </div>

                <h3 className="section-subtitle">2. Attendance Table & Schema Mapping</h3>
                <div className="dw-grid-2">
                  <Field label="Table Name" name="table" value={form.table} onChange={handleFormChange} placeholder="HR_EMP_INOUT_DETAIL" />
                  <Field label="Employee ID Column" name="column1" value={form.column1} onChange={handleFormChange} placeholder="EMPLOYEE_NO" />
                  <Field label="Timestamp Column" name="column2" value={form.column2} onChange={handleFormChange} placeholder="SWAP_TIME" />
                  <Field label="Machine Reference Column" name="column3" value={form.column3} onChange={handleFormChange} placeholder="MACHINE_REF" />
                </div>

                {form.database === 'Oracle' && (
                  <>
                    <h3 className="section-subtitle">3. Oracle Sequence Settings</h3>
                    <div className="dw-grid-2">
                      <Field label="Primary Key Column" name="col_pk" value={form.col_pk || ''} onChange={handleFormChange} placeholder="HR_ATT_LOG_ID" />
                      <Field label="Sequence Name" name="seq_pk" value={form.seq_pk || ''} onChange={handleFormChange} placeholder="HR_EMP_INOUT_ID_S" />
                    </div>
                  </>
                )}

                {/* Schema preview */}
                <div className="profile-schema">
                  <span className="schema-title">Target Schema Preview (If created by UTAS)</span>
                  <div className="schema-rows">
                    {form.database === 'Oracle' && (
                      <div className="schema-row">
                        <span className="col-name">{form.col_pk || 'id'}</span>
                        <span className="col-type">
                          {form.col_pk ? `NUMBER — Primary Key (Sequence: ${form.seq_pk || 'None'})` : 'NUMBER — Auto-generated Primary Key'}
                        </span>
                      </div>
                    )}
                    {form.database === 'PostgreSQL' && (
                      <div className="schema-row">
                        <span className="col-name">id</span>
                        <span className="col-type">SERIAL — Auto-generated Primary Key</span>
                      </div>
                    )}
                    <div className="schema-row">
                      <span className="col-name">{form.column1 || 'employee_no'}</span>
                      <span className="col-type">VARCHAR(50)</span>
                    </div>
                    <div className="schema-row">
                      <span className="col-name">{form.column2 || 'swap_time'}</span>
                      <span className="col-type">TIMESTAMP</span>
                    </div>
                    <div className="schema-row">
                      <span className="col-name">{form.column3 || 'machine_ref'}</span>
                      <span className="col-type">VARCHAR(200)</span>
                    </div>
                  </div>
                </div>

                {/* Test Connection Results */}
                {testStatus !== null && (
                  <div className={`test-status-banner ${testStatus.success ? 'success' : 'error'}`}>
                    {testStatus.success ? (
                      <>
                        <MdCheckCircle /> {testStatus.msg}
                      </>
                    ) : (
                      <>
                        <MdError /> Error: {testStatus.msg}
                      </>
                    )}
                  </div>
                )}

                <div className="form-actions">
                  <button className="btn btn-secondary" onClick={handleTestConnection} disabled={busy}>
                    <MdLink /> Test Connection
                  </button>
                  <button className="btn btn-accent" onClick={handleCreateTable} disabled={busy}>
                    <MdTableChart /> Create Table
                  </button>
                  <div className="spacer" />
                  <button className="btn btn-ghost" onClick={() => {
                    if (document.activeElement && typeof document.activeElement.blur === 'function') {
                      document.activeElement.blur();
                    }
                    setSelectedProfile(null);
                  }}>
                    Cancel
                  </button>
                  <button className="btn btn-primary" onClick={handleSave} disabled={busy}>
                    <MdOutlineDataSaverOn /> Save Profile
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="form-empty-state">
              <MdSettings />
              <h3>Select a profile or create a new one</h3>
              <p>Configure individual database destinations. Each company can be routed to a separate database profile.</p>
              <button className="btn btn-primary" onClick={handleAddNew}>
                <MdAdd /> Add Profile Now
              </button>
            </div>
          )}
        </div>
      </div>

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
        .profile-wrap { padding: 2rem; max-width: 1200px; margin: 0 auto; }
        .profile-header { display: flex; align-items: center; gap: 1rem; margin-bottom: 2rem; }
        .profile-header-icon { font-size: 2.8rem; color: var(--color-accent); }
        .profile-header h1 { font-size: 1.75rem; font-weight: 800; color: var(--color-text); }
        .profile-header p { color: var(--color-text-muted); font-size: 0.95rem; margin-top: 4px; }

        .profile-container { display: grid; grid-template-columns: 320px 1fr; gap: 2rem; }

        /* Sidebar styles */
        .profile-sidebar {
          background: #fff;
          border: 1px solid var(--color-border);
          border-radius: var(--radius-lg);
          padding: 1.25rem;
          box-shadow: var(--shadow-sm);
          height: fit-content;
        }
        .sidebar-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem; }
        .sidebar-header h3 { font-size: 0.95rem; font-weight: 700; text-transform: uppercase; color: var(--color-text-muted); }
        
        .loading-state, .empty-state {
          padding: 2rem;
          text-align: center;
          color: var(--color-text-muted);
          font-size: 0.875rem;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 0.5rem;
        }
        .empty-state svg { font-size: 1.5rem; color: #eab308; }
        .anim-spin { animation: spin 1s linear infinite; font-size: 1.5rem; }
        @keyframes spin { to { transform: rotate(360deg); } }

        .profile-list { display: flex; flex-direction: column; gap: 0.75rem; }
        .profile-item-card {
          padding: 0.85rem 1rem;
          border: 1px solid var(--color-border);
          border-radius: var(--radius-md);
          background: var(--color-bg);
          cursor: pointer;
          display: flex;
          justify-content: space-between;
          align-items: center;
          transition: var(--transition);
        }
        .profile-item-card:hover {
          border-color: var(--color-accent);
          background: #fff;
          box-shadow: var(--shadow-sm);
        }
        .profile-item-card.active {
          border-color: var(--color-accent);
          background: rgba(67, 97, 238, 0.04);
        }
        .item-info h4 { font-size: 0.95rem; font-weight: 700; color: var(--color-text); margin-bottom: 3px; }
        .item-info span { font-size: 0.75rem; color: var(--color-text-muted); font-family: monospace; }
        
        .btn-icon {
          background: transparent;
          border: none;
          cursor: pointer;
          font-size: 1.2rem;
          padding: 4px;
          border-radius: var(--radius-sm);
          display: flex;
          align-items: center;
          justify-content: center;
          color: var(--color-text-muted);
          transition: var(--transition);
        }
        .btn-icon:hover { background: #f1f5f9; }
        .btn-delete:hover { color: #dc2626; }

        /* Main profile content */
        .profile-main {}
        .form-empty-state {
          background: #fff;
          border: 1px solid var(--color-border);
          border-radius: var(--radius-lg);
          padding: 4rem 2rem;
          text-align: center;
          color: var(--color-text-muted);
          box-shadow: var(--shadow-sm);
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 0.75rem;
        }
        .form-empty-state svg { font-size: 3rem; color: var(--color-accent); opacity: 0.4; }
        .form-empty-state h3 { font-size: 1.15rem; font-weight: 700; color: var(--color-text); }
        .form-empty-state p { font-size: 0.875rem; max-width: 400px; margin-bottom: 0.5rem; }

        /* Form Card */
        .profile-card {
          background: #fff;
          border: 1px solid var(--color-border);
          border-radius: var(--radius-lg);
          box-shadow: var(--shadow-sm);
          overflow: hidden;
        }
        .card-header {
          padding: 1rem 1.5rem;
          background: #f8fafc;
          border-bottom: 1px solid var(--color-border);
        }
        .card-header h2 { font-size: 1.15rem; font-weight: 700; color: var(--color-text); }
        .card-body { padding: 1.5rem; }

        .section-subtitle {
          font-size: 0.85rem;
          font-weight: 800;
          color: var(--color-accent);
          text-transform: uppercase;
          letter-spacing: 0.5px;
          margin: 1.5rem 0 1rem 0;
          border-bottom: 1px solid var(--color-border);
          padding-bottom: 6px;
        }

        .dw-grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
        .full-width { grid-column: span 2; }

        .profile-field label {
          display: block;
          font-size: 0.72rem;
          font-weight: 700;
          color: var(--color-text-muted);
          text-transform: uppercase;
          letter-spacing: 0.4px;
          margin-bottom: 4px;
        }
        .profile-field input, .profile-field select {
          width: 100%;
          padding: 8px 12px;
          border: 1px solid var(--color-border);
          border-radius: var(--radius-sm);
          font-size: 0.875rem;
          outline: none;
          background: var(--color-bg);
          transition: var(--transition);
          color: var(--color-text);
        }
        .profile-field input:focus, .profile-field select:focus {
          border-color: var(--color-accent);
          background: #fff;
          box-shadow: 0 0 0 3px rgba(67, 97, 238, 0.12);
        }

        /* Schema Preview */
        .profile-schema {
          margin-top: 1.25rem;
          border: 1px solid var(--color-border);
          border-radius: var(--radius-md);
          overflow: hidden;
        }
        .schema-title {
          display: block;
          padding: 0.5rem 1rem;
          background: #f1f5f9;
          font-size: 0.7rem;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          color: var(--color-text-muted);
          border-bottom: 1px solid var(--color-border);
        }
        .schema-rows { display: flex; flex-direction: column; }
        .schema-row {
          display: flex;
          justify-content: space-between;
          padding: 0.5rem 1rem;
          border-bottom: 1px solid var(--color-border);
          font-size: 0.8rem;
        }
        .schema-row:last-child { border-bottom: none; }
        .col-name { font-weight: 700; color: var(--color-text); font-family: monospace; }
        .col-type { color: var(--color-text-muted); }

        /* Banner */
        .test-status-banner {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.75rem 1rem;
          border-radius: var(--radius-md);
          font-weight: 600;
          font-size: 0.85rem;
          margin-top: 1.25rem;
        }
        .test-status-banner.success { background: #dcfce7; color: #166534; border: 1px solid #bbf7d0; }
        .test-status-banner.error { background: #fee2e2; color: #991b1b; border: 1px solid #fecaca; }

        /* Form Actions */
        .form-actions { display: flex; gap: 0.75rem; margin-top: 1.5rem; align-items: center; }
        .spacer { flex: 1; }

        .btn {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 0.5rem 1.1rem;
          border-radius: var(--radius-sm);
          font-size: 0.875rem;
          font-weight: 600;
          cursor: pointer;
          border: none;
          transition: var(--transition);
        }
        .btn-sm { padding: 0.35rem 0.75rem; font-size: 0.78rem; }
        .btn-primary { background: var(--color-accent); color: #fff; }
        .btn-primary:hover { background: #3451d1; }
        .btn-secondary { background: #f1f5f9; color: var(--color-text); border: 1px solid var(--color-border); }
        .btn-secondary:hover { background: #e2e8f0; }
        .btn-accent { background: #10b981; color: #fff; }
        .btn-accent:hover { background: #059669; }
        .btn-ghost { background: transparent; color: var(--color-text-muted); }
        .btn-ghost:hover { background: #f1f5f9; color: var(--color-text); }

        @media(max-width: 900px) {
          .profile-container { grid-template-columns: 1fr; }
          .dw-grid-2 { grid-template-columns: 1fr; }
          .full-width { grid-column: span 1; }
        }
      `}</style>
    </div>
  )
}
