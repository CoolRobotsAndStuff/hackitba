const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electron', {
  hideOverlay: () => ipcRenderer.send('hide-overlay'),
  getSettings: () => ipcRenderer.invoke('get-settings'),
  saveSettings: (s) => ipcRenderer.invoke('save-settings', s),
  getHistory: () => ipcRenderer.invoke('get-history'),
  addHistoryEntry: (entry) => ipcRenderer.invoke('add-history-entry', entry),
  clearHistory: () => ipcRenderer.invoke('clear-history'),
  onOverlayOpened: (cb) => ipcRenderer.on('overlay-opened', cb)
})