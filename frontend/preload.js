const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  openExternal: (url) => ipcRenderer.send('open-external', url),
  platform: process.platform,
  getLocalIp: () => ipcRenderer.invoke('get-local-ip'),
  getAppVersion: () => ipcRenderer.invoke('get-app-version'),
  
  // Auto-updater functions
  checkForUpdates: () => ipcRenderer.send('check-for-updates'),
  restartAndInstall: () => ipcRenderer.send('restart-and-install'),
  onUpdaterStatus: (callback) => {
    const subscription = (event, status, detail) => callback(status, detail)
    ipcRenderer.on('updater-status', subscription)
    return () => ipcRenderer.removeListener('updater-status', subscription)
  },
  onUpdaterDownloadProgress: (callback) => {
    const subscription = (event, percent) => callback(percent)
    ipcRenderer.on('updater-download-progress', subscription)
    return () => ipcRenderer.removeListener('updater-download-progress', subscription)
  }
})

