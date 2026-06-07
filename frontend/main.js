const { app, BrowserWindow, ipcMain, shell } = require('electron')
const path = require('path')
const Store = require('electron-store')
const { spawn } = require('child_process')

const store = new Store()
const isDev = !app.isPackaged

let mainWindow
let backendProcess = null

function createWindow() {
  const { width, height, x, y } = store.get('windowBounds', {
    width: 1200, height: 750, x: undefined, y: undefined
  })

  mainWindow = new BrowserWindow({
    width,
    height,
    x,
    y,
    minWidth: 900,
    minHeight: 600,
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

  // Load Vite dev server in dev, built files in production
  if (isDev) {
    mainWindow.loadURL('http://localhost:5173')
    mainWindow.webContents.openDevTools({ mode: 'detach' })
  } else {
    mainWindow.loadFile(path.join(__dirname, 'dist', 'index.html'))
  }

  mainWindow.once('ready-to-show', () => mainWindow.show())

  // Remember window position and size
  mainWindow.on('close', () => {
    const { width, height, x, y } = mainWindow.getBounds()
    store.set('windowBounds', { width, height, x, y })
  })

  mainWindow.on('closed', () => { mainWindow = null })
}

function startBackend() {
  if (!isDev) {
    const backendPath = path.join(process.resourcesPath, 'server.exe')
    backendProcess = spawn(backendPath, [], {
      detached: false,
      windowsHide: true
    })
    backendProcess.stdout.on('data', (data) => console.log(`Backend: ${data}`))
    backendProcess.stderr.on('data', (data) => console.error(`Backend Error: ${data}`))
  }
}

app.whenReady().then(() => {
  startBackend()
  createWindow()
})

app.on('window-all-closed', () => {
  if (backendProcess) {
    backendProcess.kill()
  }
  if (process.platform !== 'darwin') app.quit()
})

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow()
})

// IPC: open external links in browser
ipcMain.on('open-external', (_, url) => shell.openExternal(url))
