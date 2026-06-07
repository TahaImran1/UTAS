import React, { useState, useEffect } from 'react'
import {
  MdStorage, MdLink, MdCheckCircle, MdError, MdWarning,
  MdAdd, MdSettings, MdLock, MdTableChart, MdDevices
} from 'react-icons/md'
import { connectAndCheck, createAttendanceTable, createMachineTable, getDbConfig } from '../api/client'
import toast from 'react-hot-toast'

/* ─── small helpers ─────────────────────────────────────── */
const Field = ({ label, name, value, onChange, placeholder = '', type = 'text' }) => (
  <div className="dw-field">
    <label>{label}</label>
    <input type={type} name={name} value={value} onChange={onChange} placeholder={placeholder} />
  </div>
)

const StatusPill = ({ ok, label }) => (
  <span className={`dw-pill ${ok ? 'dw-pill-ok' : 'dw-pill-miss'}`}>
    {ok ? <MdCheckCircle /> : <MdWarning />} {label}
  </span>
)

const SectionCard = ({ num, title, icon, locked, children }) => (
  <div className={`dw-section ${locked ? 'dw-locked' : ''}`}>
    <div className="dw-section-head">
      <span className="dw-num">{num}</span>
      {icon}
      <h2>{title}</h2>
      {locked && <span className="dw-lock-badge"><MdLock /> Locked</span>}
    </div>
    {!locked && <div className="dw-section-body">{children}</div>}
  </div>
)

/* ─── defaults ──────────────────────────────────────────── */
const defaultCreds = {
  database: 'Oracle', host: '', port: '1521',
  username: '', password: '', dbname: ''
}
const defaultAttCols = {
  table: 'HR_EMP_INOUT_DETAIL', col_pk: 'HR_ATT_LOG_ID',
  seq_pk: 'HR_EMP_INOUT_ID_S', column1: 'EMPLOYEE_NO',
  column2: 'SWAP_TIME', column3: 'MACHINE_REF', column4: ''
}
const defaultMachCols = {
  machine_table: 'COMP_MACHINE', col_sn: 'SN',
  col_ip: 'IP', col_proto: 'PROTOCOL', col_company: 'COMPANY_NAME'
}

export default function DatabaseSettings() {
  const [creds, setCreds]       = useState(defaultCreds)
  const [attCols, setAttCols]   = useState(defaultAttCols)
  const [machCols, setMachCols] = useState(defaultMachCols)

  /* wizard state */
  const [connStatus, setConnStatus] = useState(null)   // null | 'ok' | 'error'
  const [connMsg, setConnMsg]       = useState('')
  const [attExists, setAttExists]   = useState(false)
  const [machExists, setMachExists] = useState(false)
  const [bothExist, setBothExist]   = useState(false)

  const [wantCreateAtt,  setWantCreateAtt]  = useState(false)
  const [wantCreateMach, setWantCreateMach] = useState(false)

  const [busy, setBusy] = useState(false)
  const [attCreated,  setAttCreated]  = useState(false)
  const [machCreated, setMachCreated] = useState(false)

  /* load saved config on mount */
  useEffect(() => {
    getDbConfig().then(r => {
      const d = r.data
      if (d) {
        setCreds(prev => ({ ...prev, ...d }))
        if (d.table)          setAttCols(prev  => ({ ...prev,  table:         d.table,
          col_pk: d.col_pk||prev.col_pk, seq_pk: d.seq_pk||prev.seq_pk,
          column1: d.column1||prev.column1, column2: d.column2||prev.column2,
          column3: d.column3||prev.column3, column4: d.column4||'' }))
        if (d.machine_table)  setMachCols(prev => ({ ...prev, machine_table: d.machine_table }))
      }
    }).catch(() => {})
  }, [])

  const loadConfigForType = (dbType) => {
    getDbConfig(dbType).then(r => {
      const d = r.data
      if (d) {
        setCreds(prev => ({ ...prev, ...d }))
        if (d.table) {
          setAttCols(prev => ({
            ...prev,
            table: d.table,
            col_pk: d.col_pk || prev.col_pk,
            seq_pk: d.seq_pk || prev.seq_pk,
            column1: d.column1 || prev.column1,
            column2: d.column2 || prev.column2,
            column3: d.column3 || prev.column3,
            column4: d.column4 || ''
          }))
        }
        if (d.machine_table) {
          setMachCols(prev => ({ ...prev, machine_table: d.machine_table }))
        }
      } else {
        setCreds({
          database: dbType,
          host: '',
          port: dbType === 'Oracle' ? '1521' : '5432',
          username: '',
          password: '',
          dbname: ''
        })
      }
    }).catch(() => {
      setCreds({
        database: dbType,
        host: '',
        port: dbType === 'Oracle' ? '1521' : '5432',
        username: '',
        password: '',
        dbname: ''
      })
    })
  }

  const handleCreds = e => {
    const { name, value } = e.target
    setCreds(p => ({ ...p, [name]: value }))
    if (name === 'database') {
      loadConfigForType(value)
    }
  }
  const handleAtt    = e => setAttCols(p => ({ ...p, [e.target.name]: e.target.value }))
  const handleMach   = e => setMachCols(p => ({ ...p, [e.target.name]: e.target.value }))

  /* ── Step 1: Connect & check ── */
  const handleConnect = async () => {
    if (!creds.host || !creds.username || !creds.password || !creds.dbname) {
      toast.error('Fill all credential fields first.'); return
    }
    setBusy(true)
    try {
      const payload = {
        config: { ...creds, ...attCols, machine_table: machCols.machine_table },
        att_table:     attCols.table,
        machine_table: machCols.machine_table
      }
      const res = await connectAndCheck(payload)
      const d   = res.data
      if (d.status === 'error') {
        setConnStatus('error'); setConnMsg(d.message)
        toast.error('Connection failed')
      } else {
        // Apply auto-mapped config from backend
        if (d.detected_config) {
          const cfg = d.detected_config
          setCreds(prev => ({ ...prev, host: cfg.host, port: cfg.port, username: cfg.username, password: cfg.password, dbname: cfg.dbname }))
          setAttCols(prev => ({
            ...prev,
            table:   cfg.table   || prev.table,
            column1: cfg.column1 || prev.column1,
            column2: cfg.column2 || prev.column2,
            column3: cfg.column3 || prev.column3,
            column_pk: cfg.column_pk || prev.column_pk,
            sequence:  cfg.sequence  || prev.sequence,
          }))
          setMachCols(prev => ({
            ...prev,
            machine_table: cfg.machine_table || prev.machine_table,
            col_sn:        cfg.col_sn        || prev.col_sn,
            col_ip:        cfg.col_ip        || prev.col_ip,
            col_proto:     cfg.col_proto     || prev.col_proto,
            col_company:   cfg.col_company   || prev.col_company,
          }))
        }
        setConnStatus('ok'); setConnMsg(d.message)
        setAttExists(d.att_table_exists)
        setMachExists(d.machine_table_exists)
        setBothExist(d.both_exist)
        if (d.both_exist) toast.success('Both tables found — config saved!')
        else toast.success('Connected! Configure missing tables below.')
      }
    } catch (e) {
      setConnStatus('error'); setConnMsg(String(e))
      toast.error('Connection error')
    } finally { setBusy(false) }
  }

  /* ── Step 3: Create attendance table ── */
  const handleCreateAtt = async () => {
    setBusy(true)
    try {
      const payload = { config: { ...creds, ...attCols } }
      const res = await createAttendanceTable(payload)
      const d   = res.data
      if (d.status === 'success') { setAttCreated(true); toast.success(d.message) }
      else toast.error(d.message)
    } catch (e) { toast.error(String(e)) }
    finally { setBusy(false) }
  }

  /* ── Step 5: Create machine table ── */
  const handleCreateMach = async () => {
    setBusy(true)
    try {
      const payload = { config: { ...creds }, ...machCols }
      const res = await createMachineTable(payload)
      const d   = res.data
      if (d.status === 'success') { setMachCreated(true); toast.success(d.message) }
      else toast.error(d.message)
    } catch (e) { toast.error(String(e)) }
    finally { setBusy(false) }
  }

  const attUnlocked  = connStatus === 'ok' && !attExists  && !bothExist
  const machUnlocked = connStatus === 'ok' && !machExists && !bothExist

  return (
    <div className="dw-wrap">
      <div className="dw-header">
        <MdStorage className="dw-header-icon" />
        <div>
          <h1>Database Management</h1>
          <p>Configure your external attendance database step by step</p>
        </div>
      </div>

      {bothExist && (
        <div className="dw-banner dw-banner-ok">
          <MdCheckCircle /> Both tables are present — configuration saved. Nothing else to do!
        </div>
      )}

      {/* ══════════════ SECTION 1 ══════════════ */}
      <SectionCard num="1" title="Database Credentials" icon={<MdLink />} locked={false}>
        <p className="dw-hint">Enter connection details and click <strong>Connect & Check Tables</strong>.</p>

        <div className="dw-grid-2">
          <div className="dw-field">
            <label>Database Type</label>
            <select name="database" value={creds.database} onChange={handleCreds}>
              <option value="Oracle">Oracle</option>
              <option value="PostgreSQL">PostgreSQL</option>
            </select>
          </div>
          <Field label="Host / IP" name="host" value={creds.host} onChange={handleCreds} placeholder="192.168.1.100" />
          <Field label="Port" name="port" value={creds.port} onChange={handleCreds} placeholder="1521" />
          <Field label="Username" name="username" value={creds.username} onChange={handleCreds} />
          <Field label="Password" name="password" value={creds.password} onChange={handleCreds} type="password" />
          <Field label="DB / Service Name" name="dbname" value={creds.dbname} onChange={handleCreds} placeholder="orcl" />
        </div>

        <div className="dw-action-row">
          <button className="dw-btn dw-btn-primary" onClick={handleConnect} disabled={busy}>
            {busy ? <><span className="spinner" /> Connecting…</> : <><MdLink /> Connect &amp; Check Tables</>}
          </button>

          {connStatus === 'ok' && (
            <div className="dw-check-results">
              <StatusPill ok={attExists}  label={`Attendance table: ${attCols.table}`} />
              <StatusPill ok={machExists} label={`Machine table: ${machCols.machine_table}`} />
            </div>
          )}
          {connStatus === 'error' && (
            <div className="dw-err-msg"><MdError /> {connMsg}</div>
          )}
        </div>
      </SectionCard>

      {/* ══════════════ SECTION 2 ══════════════ */}
      <SectionCard num="2" title="Attendance Log Table — Name & Columns" icon={<MdTableChart />} locked={!attUnlocked && !attExists}>
        <p className="dw-hint">Specify the exact table and column names used in your database.</p>
        <div className="dw-grid-2">
          <Field label="Table Name" name="table" value={attCols.table} onChange={handleAtt} placeholder="HR_EMP_INOUT_DETAIL" />
          <Field label="User / Employee Column" name="column1" value={attCols.column1} onChange={handleAtt} placeholder="EMPLOYEE_NO" />
          <Field label="Timestamp Column" name="column2" value={attCols.column2} onChange={handleAtt} placeholder="SWAP_TIME" />
          <Field label="Machine Ref Column" name="column3" value={attCols.column3} onChange={handleAtt} placeholder="MACHINE_REF" />
          <Field label="Client ID Column (optional)" name="column4" value={attCols.column4} onChange={handleAtt} placeholder="CLIENT_ID" />
          {creds.database === 'Oracle' && <>
            <Field label="Primary Key Column" name="col_pk" value={attCols.col_pk} onChange={handleAtt} placeholder="HR_ATT_LOG_ID" />
            <Field label="Sequence Name" name="seq_pk" value={attCols.seq_pk} onChange={handleAtt} placeholder="HR_EMP_INOUT_ID_S" />
          </>}
        </div>

        {/* Schema preview */}
        <div className="dw-schema">
          <span className="dw-schema-title">Schema preview</span>
          <div className="dw-schema-rows">
            {creds.database === 'Oracle' && <div className="dw-schema-row"><span className="dw-col-name">{attCols.col_pk||'PK'}</span><span className="dw-col-type">NUMBER — Primary Key</span></div>}
            {creds.database === 'PostgreSQL' && <div className="dw-schema-row"><span className="dw-col-name">id</span><span className="dw-col-type">SERIAL — Primary Key</span></div>}
            <div className="dw-schema-row"><span className="dw-col-name">{attCols.column1||'col1'}</span><span className="dw-col-type">VARCHAR(50)</span></div>
            <div className="dw-schema-row"><span className="dw-col-name">{attCols.column2||'col2'}</span><span className="dw-col-type">TIMESTAMP</span></div>
            <div className="dw-schema-row"><span className="dw-col-name">{attCols.column3||'col3'}</span><span className="dw-col-type">VARCHAR(200)</span></div>
            {attCols.column4 && <div className="dw-schema-row"><span className="dw-col-name">{attCols.column4}</span><span className="dw-col-type">VARCHAR(100)</span></div>}
          </div>
        </div>

        {attExists && (
          <div className="dw-action-row" style={{ marginTop: '1rem', justifyContent: 'flex-end' }}>
            <button className="dw-btn dw-btn-ghost" onClick={handleConnect} disabled={busy}>
              <MdSettings /> Save Updated Mapping
            </button>
          </div>
        )}
      </SectionCard>

      {/* ══════════════ SECTION 3 ══════════════ */}
      <SectionCard num="3" title="Create Attendance Log Table" icon={<MdAdd />} locked={!attUnlocked}>
        {attCreated
          ? <div className="dw-banner dw-banner-ok"><MdCheckCircle /> Table <strong>{attCols.table}</strong> created successfully!</div>
          : <>
              <label className="dw-checkbox-row">
                <input type="checkbox" checked={wantCreateAtt} onChange={e => setWantCreateAtt(e.target.checked)} />
                <span>I don't have a log table — create it for me with the columns above</span>
              </label>
              {wantCreateAtt && (
                <div className="dw-action-row" style={{ marginTop: '1rem' }}>
                  <button className="dw-btn dw-btn-success" onClick={handleCreateAtt} disabled={busy}>
                    {busy ? <><span className="spinner" /> Creating…</> : <><MdAdd /> Create Attendance Table</>}
                  </button>
                </div>
              )}
            </>}
      </SectionCard>

      {/* ══════════════ SECTION 4 ══════════════ */}
      <SectionCard num="4" title="Machine Link Table — Name & Columns" icon={<MdDevices />} locked={!machUnlocked && !machExists}>
        <p className="dw-hint">This table links each device serial number to a company. Specify names used in your database.</p>
        <div className="dw-grid-2">
          <Field label="Table Name" name="machine_table" value={machCols.machine_table} onChange={handleMach} placeholder="COMP_MACHINE" />
          <Field label="Serial Number Column" name="col_sn" value={machCols.col_sn} onChange={handleMach} placeholder="SN" />
          <Field label="IP Address Column" name="col_ip" value={machCols.col_ip} onChange={handleMach} placeholder="IP" />
          <Field label="Protocol Column" name="col_proto" value={machCols.col_proto} onChange={handleMach} placeholder="PROTOCOL" />
          <Field label="Company Name Column" name="col_company" value={machCols.col_company} onChange={handleMach} placeholder="COMPANY_NAME" />
        </div>

        <div className="dw-schema">
          <span className="dw-schema-title">Schema preview</span>
          <div className="dw-schema-rows">
            <div className="dw-schema-row"><span className="dw-col-name">{machCols.col_sn||'SN'}</span><span className="dw-col-type">VARCHAR(100) — Primary Key</span></div>
            <div className="dw-schema-row"><span className="dw-col-name">{machCols.col_ip||'IP'}</span><span className="dw-col-type">VARCHAR(50)</span></div>
            <div className="dw-schema-row"><span className="dw-col-name">{machCols.col_proto||'PROTOCOL'}</span><span className="dw-col-type">VARCHAR(20)</span></div>
            <div className="dw-schema-row"><span className="dw-col-name">{machCols.col_company||'COMPANY_NAME'}</span><span className="dw-col-type">VARCHAR(200)</span></div>
          </div>
        </div>
      </SectionCard>

      {/* ══════════════ SECTION 5 ══════════════ */}
      <SectionCard num="5" title="Create Machine Link Table" icon={<MdAdd />} locked={!machUnlocked}>
        {machCreated
          ? <div className="dw-banner dw-banner-ok"><MdCheckCircle /> Table <strong>{machCols.machine_table}</strong> created successfully!</div>
          : <>
              <label className="dw-checkbox-row">
                <input type="checkbox" checked={wantCreateMach} onChange={e => setWantCreateMach(e.target.checked)} />
                <span>I don't have a machine link table — create it for me with the columns above</span>
              </label>
              {wantCreateMach && (
                <div className="dw-action-row" style={{ marginTop: '1rem' }}>
                  <button className="dw-btn dw-btn-success" onClick={handleCreateMach} disabled={busy}>
                    {busy ? <><span className="spinner" /> Creating…</> : <><MdAdd /> Create Machine Link Table</>}
                  </button>
                </div>
              )}
            </>}
      </SectionCard>

      <style>{`
        .dw-wrap { padding: 1.5rem 2rem; max-width: 860px; margin: 0 auto; }

        .dw-header { display:flex; align-items:center; gap:1rem; margin-bottom:1.75rem; }
        .dw-header-icon { font-size:2.4rem; color:var(--color-accent); }
        .dw-header h1 { font-size:1.5rem; font-weight:800; color:var(--color-text); }
        .dw-header p  { color:var(--color-text-muted); font-size:.875rem; margin-top:2px; }

        .dw-banner { display:flex; align-items:center; gap:.5rem; padding:.85rem 1.2rem;
          border-radius:var(--radius-md); font-weight:600; font-size:.875rem; margin-bottom:1.25rem; }
        .dw-banner svg { font-size:1.25rem; }
        .dw-banner-ok { background:#DCFCE7; color:#15803D; border:1px solid #86EFAC; }

        /* Section card */
        .dw-section { background:#fff; border:1px solid var(--color-border);
          border-radius:var(--radius-lg); margin-bottom:1rem;
          box-shadow:var(--shadow-sm); overflow:hidden; transition:var(--transition); }
        .dw-section:hover { box-shadow:var(--shadow-md); }
        .dw-locked { opacity:.45; pointer-events:none; }

        .dw-section-head { display:flex; align-items:center; gap:.65rem;
          padding:.95rem 1.4rem; background:#F8FAFC;
          border-bottom:1px solid var(--color-border); }
        .dw-section-head svg { font-size:1.2rem; color:var(--color-accent); }
        .dw-section-head h2 { font-size:1rem; font-weight:700; flex:1; color:var(--color-text); }

        .dw-num { width:26px; height:26px; border-radius:50%; background:var(--color-accent);
          color:#fff; font-size:.75rem; font-weight:800;
          display:flex; align-items:center; justify-content:center; flex-shrink:0; }

        .dw-lock-badge { display:flex; align-items:center; gap:4px; font-size:.72rem;
          font-weight:600; color:#94A3B8; background:#F1F5F9;
          padding:3px 10px; border-radius:99px; }

        .dw-section-body { padding:1.4rem; }
        .dw-hint { font-size:.82rem; color:var(--color-text-muted); margin-bottom:1.1rem; }

        /* Grid */
        .dw-grid-2 { display:grid; grid-template-columns:1fr 1fr; gap:.9rem; margin-bottom:1.2rem; }

        /* Field */
        .dw-field label { display:block; font-size:.72rem; font-weight:700;
          color:var(--color-text-muted); text-transform:uppercase; letter-spacing:.4px; margin-bottom:4px; }
        .dw-field input, .dw-field select {
          width:100%; padding:9px 12px; border:1px solid var(--color-border);
          border-radius:var(--radius-sm); font-size:.875rem; outline:none;
          background:var(--color-bg); transition:var(--transition); color:var(--color-text); }
        .dw-field input:focus, .dw-field select:focus {
          border-color:var(--color-accent); background:#fff;
          box-shadow:0 0 0 3px rgba(67,97,238,.12); }

        /* Action row */
        .dw-action-row { display:flex; align-items:center; gap:1rem; flex-wrap:wrap; }

        /* Buttons */
        .dw-btn { display:inline-flex; align-items:center; gap:6px;
          padding:.6rem 1.2rem; border-radius:var(--radius-sm); font-size:.875rem;
          font-weight:600; cursor:pointer; border:none; transition:var(--transition); }
        .dw-btn:disabled { opacity:.5; cursor:not-allowed; }
        .dw-btn-primary { background:var(--color-accent); color:#fff; }
        .dw-btn-primary:hover:not(:disabled) { background:#3451d1; }
        .dw-btn-success { background:#16A34A; color:#fff; }
        .dw-btn-success:hover:not(:disabled) { background:#15803D; }

        /* Status pills */
        .dw-check-results { display:flex; gap:.6rem; flex-wrap:wrap; }
        .dw-pill { display:inline-flex; align-items:center; gap:4px;
          padding:4px 12px; border-radius:99px; font-size:.78rem; font-weight:600; }
        .dw-pill svg { font-size:.9rem; }
        .dw-pill-ok   { background:#DCFCE7; color:#15803D; }
        .dw-pill-miss { background:#FEF9C3; color:#92400E; }

        .dw-err-msg { display:flex; align-items:center; gap:6px; color:#DC2626;
          font-size:.82rem; font-weight:600; }
        .dw-err-msg svg { font-size:1.1rem; }

        /* Schema preview */
        .dw-schema { margin-top:1rem; border:1px solid var(--color-border);
          border-radius:var(--radius-md); overflow:hidden; }
        .dw-schema-title { display:block; padding:.4rem .9rem; background:#F1F5F9;
          font-size:.7rem; font-weight:700; text-transform:uppercase;
          letter-spacing:.5px; color:var(--color-text-muted);
          border-bottom:1px solid var(--color-border); }
        .dw-schema-rows { display:grid; }
        .dw-schema-row { display:flex; justify-content:space-between; align-items:center;
          padding:.45rem .9rem; border-bottom:1px solid var(--color-border); font-size:.8rem; }
        .dw-schema-row:last-child { border-bottom:none; }
        .dw-col-name { font-weight:700; color:var(--color-text); font-family:monospace; }
        .dw-col-type { color:var(--color-text-muted); }

        /* Checkbox row */
        .dw-checkbox-row { display:flex; align-items:center; gap:.6rem;
          cursor:pointer; font-size:.875rem; font-weight:500; color:var(--color-text); }
        .dw-checkbox-row input[type=checkbox] { width:17px; height:17px; accent-color:var(--color-accent); cursor:pointer; }

        /* Spinner reuse */
        .spinner { width:14px; height:14px; border:2px solid rgba(255,255,255,.3);
          border-top-color:#fff; border-radius:50%;
          animation:spin .6s linear infinite; display:inline-block; }
        @keyframes spin { to { transform:rotate(360deg); } }

        @media(max-width:580px){ .dw-grid-2{ grid-template-columns:1fr; } }
      `}</style>
    </div>
  )
}
