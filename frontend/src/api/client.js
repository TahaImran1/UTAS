import axios from 'axios'

const BASE_URL = 'http://localhost:4370'

const client = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
})

// ── Machines ──────────────────────────────────────────────────────────────────
export const getMachines       = ()              => client.get('/pull/machines')
export const addMachine        = (data)          => client.post('/pull/machines', data)
export const removeMachine     = (sn)            => client.delete(`/pull/machines/${sn}`)
export const testConnection    = (data)          => client.post('/pull/machines/test-connection', data)
export const reloadMachines    = ()              => client.post('/pull/machines/reload')

// ── Pull operations ───────────────────────────────────────────────────────────
export const manualPull        = (sn)            => client.post(`/pull/attendance/${sn}`)
export const getDeviceInfo     = (sn)            => client.get(`/pull/device-info/${sn}`)
export const clearAttendance   = (sn)            => client.post(`/pull/clear-attendance/${sn}`)
export const syncTime          = (sn)            => client.post(`/pull/sync-time/${sn}`)

// ── Attendance logs ───────────────────────────────────────────────────────────
export const getAttendanceLogs = (params)        => client.get('/pull/attendance/logs', { params })

// ── Dashboard stats ───────────────────────────────────────────────────────────
export const getDashboardStats = ()              => client.get('/pull/stats')

export default client
