import axios from 'axios'

const BASE_URL = 'http://localhost:4370'

const client = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
})

// Add JWT token to all requests
client.interceptors.request.use((config) => {
    const token = localStorage.getItem('utas_token')
    if (token) {
        config.headers.Authorization = `Bearer ${token}`
    }
    return config
})

// ── Auth ──────────────────────────────────────────────────────────────────────
export const login = (username, password) => {
    const params = new URLSearchParams()
    params.append('username', username)
    params.append('password', password)
    return client.post('/api/auth/login', params, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    })
}

export const register = (username, password) => client.post('/api/auth/register', { username, password })

// ── Admin / Server ───────────────────────────────────────────────────────────
export const getServerStatus = ()     => client.get('/api/admin/server/status')
export const getServerLogs   = ()     => client.get('/api/admin/server/logs')
export const getHealthStatus = ()     => client.get('/api/admin/health')
export const getDbConfig = (type) => client.get(type ? `/api/admin/database/config?db_type=${type}` : '/api/admin/database/config')
export const saveDbConfig = (config) => client.post('/api/admin/database/config', config)
export const testDbConnection = (config) => client.post('/api/admin/database/test', config)
export const connectAndCheck = (payload) => client.post('/api/admin/database/connect-check', payload)
export const createAttendanceTable = (payload) => client.post('/api/admin/database/create-attendance-table', payload)
export const createMachineTable = (payload) => client.post('/api/admin/database/create-machine-table', payload)
export const controlServer       = (act)  => client.post('/api/admin/server/control', { action: act })
export const getCompanies        = ()     => client.get('/api/admin/companies')
export const mapDevicesToCompany = (data) => client.post('/api/admin/companies/map', data)

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
