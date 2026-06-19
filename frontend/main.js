const { app, BrowserWindow, ipcMain, shell } = require('electron')
const { autoUpdater } = require('electron-updater')
const path = require('path')
const fs = require('fs')
const Store = require('electron-store')
const { spawn, execFile } = require('child_process')
const os = require('os')

const store = new Store()
const isDev = !app.isPackaged

let mainWindow
let backendProcess = null
let fkBridgeProcess = null

// ── Paths ────────────────────────────────────────────────────────────────────
function getResourcePath(...parts) {
  return isDev
    ? path.join(__dirname, '..', ...parts)
    : path.join(process.resourcesPath, ...parts)
}

// App data dir — same as backend: %APPDATA%\UTAS
function getAppDataDir() {
  const base = process.env.APPDATA || os.homedir()
  const dir = path.join(base, 'UTAS')
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
  return dir
}

// ── First-run: copy default .env if none exists ──────────────────────────────
function ensureEnv() {
  const appDataDir = getAppDataDir()
  const envDest = path.join(appDataDir, '.env')
  if (!fs.existsSync(envDest)) {
    const envSrc = getResourcePath('.env.default')
    if (fs.existsSync(envSrc)) {
      fs.copyFileSync(envSrc, envDest)
      console.log(`[UTAS] Created default .env at ${envDest}`)
    } else {
      console.warn('[UTAS] No .env.default found — server will use built-in defaults')
    }
  }
  return appDataDir
}

// ── Firewall port helper ──────────────────────────────────────────────────────
const REQUIRED_PORTS = [
  { port: 4370, proto: 'TCP', name: 'UTAS-4370-TCP' },
  { port: 4370, proto: 'UDP', name: 'UTAS-4370-UDP' },
  { port: 5001, proto: 'TCP', name: 'UTAS-5001-TCP' },
]

function openFirewallPorts() {
  if (process.platform !== 'win32') return
  REQUIRED_PORTS.forEach(({ port, proto, name }) => {
    const addArgs = [
      'advfirewall', 'firewall', 'add', 'rule',
      `name=${name}`, 'dir=in', 'action=allow',
      `protocol=${proto}`, `localport=${port}`,
      'profile=any', 'enable=yes',
    ]
    try {
      const proc = execFile('netsh', addArgs, { windowsHide: true })
      proc.on('close', (code) => {
        console.log(`[Firewall] Rule ${name}: ${code === 0 ? 'OK' : `exit ${code}`}`)
      })
    } catch (e) {
      console.warn(`[Firewall] netsh error: ${e.message}`)
    }
  })
}

// ── FK Bridge launcher ────────────────────────────────────────────────────────
function startFkBridge() {
  if (isDev) return // In dev mode the user runs FkBridge manually
  const fkExe = getResourcePath('fk-bridge', 'FkBridge.exe')
  const fkDir = path.dirname(fkExe)
  if (!fs.existsSync(fkExe)) {
    console.warn(`[FkBridge] Not found at ${fkExe} — FK device pull will be unavailable`)
    return
  }
  console.log(`[FkBridge] Starting from ${fkExe}`)
  fkBridgeProcess = spawn(fkExe, [], {
    cwd: fkDir,         // must run from its own dir (DLLs are relative)
    detached: false,
    windowsHide: true,
  })
  fkBridgeProcess.stdout?.on('data', (d) => console.log(`[FkBridge] ${d}`))
  fkBridgeProcess.stderr?.on('data', (d) => console.error(`[FkBridge ERR] ${d}`))
  fkBridgeProcess.on('exit', (code) => {
    console.log(`[FkBridge] Exited with code ${code}`)
    fkBridgeProcess = null
  })
}

// ── Backend launcher ──────────────────────────────────────────────────────────
function startBackend(appDataDir) {
  if (isDev) return
  const backendPath = getResourcePath('UTAS.exe')
  if (!fs.existsSync(backendPath)) {
    console.error(`[Backend] UTAS.exe not found at ${backendPath}`)
    return
  }

  // Pass DOTENV_PATH so server.exe loads .env from APPDATA\UTAS\.env
  const envVars = Object.assign({}, process.env, {
    DOTENV_PATH: path.join(appDataDir, '.env'),
    FK_BRIDGE_URL: 'http://127.0.0.1:5001',
  })

  console.log(`[Backend] Starting from ${backendPath}`)
  backendProcess = spawn(backendPath, [], {
    cwd: appDataDir,    // working dir = %APPDATA%\UTAS so .env is found
    detached: false,
    windowsHide: true,
    env: envVars,
  })
  backendProcess.stdout?.on('data', (d) => console.log(`[Backend] ${d}`))
  backendProcess.stderr?.on('data', (d) => console.error(`[Backend ERR] ${d}`))
  backendProcess.on('exit', (code) => {
    console.log(`[Backend] Exited with code ${code}`)
    backendProcess = null
  })
}

// ── Window creation ───────────────────────────────────────────────────────────
function createWindow() {
  const { width, height, x, y } = store.get('windowBounds', {
    width: 1280, height: 800, x: undefined, y: undefined
  })

  mainWindow = new BrowserWindow({
    width, height, x, y,
    minWidth: 960,
    minHeight: 620,
    title: 'UTAS — Time Attendance System',
    icon: path.join(__dirname, 'src', 'assets', 'icon.png'),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    },
    titleBarStyle: 'default',
    show: false,
  })

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173')
    mainWindow.webContents.openDevTools({ mode: 'detach' })
  } else {
    mainWindow.loadFile(path.join(__dirname, 'dist', 'index.html'))
  }

  mainWindow.once('ready-to-show', () => mainWindow.show())
  mainWindow.on('close', () => {
    const b = mainWindow.getBounds()
    store.set('windowBounds', b)
  })
  mainWindow.on('closed', () => { mainWindow = null })
}

// ── App lifecycle ─────────────────────────────────────────────────────────────
app.whenReady().then(() => {
  const appDataDir = ensureEnv()
  openFirewallPorts()
  startFkBridge()
  // Give FK Bridge a moment to bind its port before backend tries to probe it
  setTimeout(() => startBackend(appDataDir), 1500)
  createWindow()
  initAutoUpdater()
})

app.on('window-all-closed', () => {
  if (fkBridgeProcess) {
    fkBridgeProcess.kill()
    fkBridgeProcess = null
  }
  if (backendProcess) {
    backendProcess.kill()
    backendProcess = null
  }
  if (process.platform !== 'darwin') app.quit()
})

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow()
})

// ── IPC ───────────────────────────────────────────────────────────────────────
ipcMain.on('open-external', (_, url) => shell.openExternal(url))

ipcMain.handle('get-local-ip', () => {
  const nets = os.networkInterfaces()
  for (const name of Object.keys(nets)) {
    for (const net of nets[name]) {
      if (net.family === 'IPv4' && !net.internal) return net.address
    }
  }
  return '127.0.0.1'
})

// ── Auto-Updater Logic ────────────────────────────────────────────────────────
function initAutoUpdater() {
  if (isDev) {
    console.log('[Updater] Development mode: Auto-updater is disabled.')
    return
  }

  autoUpdater.logger = console
  autoUpdater.autoDownload = true
  autoUpdater.autoInstallOnAppQuit = true

  console.log('[Updater] Initializing auto-updater...')

  autoUpdater.on('checking-for-update', () => {
    console.log('[Updater] Checking for update...')
    mainWindow?.webContents.send('updater-status', 'checking')
  })

  autoUpdater.on('update-available', (info) => {
    console.log(`[Updater] Update available: version ${info.version}`)
    mainWindow?.webContents.send('updater-status', 'available', info.version)
  })

  autoUpdater.on('update-not-available', () => {
    console.log('[Updater] Update not available.')
    mainWindow?.webContents.send('updater-status', 'not-available')
  })

  autoUpdater.on('error', (err) => {
    console.error(`[Updater] Error: ${err.message}`)
    mainWindow?.webContents.send('updater-status', 'error', err.message)
  })

  autoUpdater.on('download-progress', (progressObj) => {
    console.log(`[Updater] Downloaded ${Math.round(progressObj.percent)}%`)
    mainWindow?.webContents.send('updater-download-progress', progressObj.percent)
  })

  autoUpdater.on('update-downloaded', (info) => {
    console.log('[Updater] Update downloaded; ready to install.')
    mainWindow?.webContents.send('updater-status', 'downloaded', info.version)
  })

  // IPC listeners from frontend
  ipcMain.on('check-for-updates', () => {
    console.log('[Updater] Manual check triggered via frontend.')
    autoUpdater.checkForUpdatesAndNotify()
  })

  ipcMain.on('restart-and-install', () => {
    console.log('[Updater] Manual restart and install triggered.')
    autoUpdater.quitAndInstall()
  })

  // Auto check on start
  autoUpdater.checkForUpdatesAndNotify()

  // Poll for updates every 6 hours
  setInterval(() => {
    autoUpdater.checkForUpdatesAndNotify()
  }, 6 * 60 * 60 * 1000)
}

