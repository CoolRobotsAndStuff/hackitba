const { app, BrowserWindow, Tray, Menu, globalShortcut, screen, ipcMain, nativeImage } = require('electron')
const Store = require('electron-store')
const path = require('path')

const store = new Store()

let tray = null
let overlayWindow = null
let isOverlayVisible = false

// Icon path — works in both dev (npm start) and packaged (AppImage)
function getIconPath() {
  if (app.isPackaged) {
    // In AppImage, extraResources lands in process.resourcesPath
    return path.join(process.resourcesPath, 'icon.png')
  }
  return path.join(__dirname, 'assets', 'icon.png')
}

function createOverlay() {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize
  const overlayHeight = Math.round(height * 0.55)
  const overlayY = height - overlayHeight

  overlayWindow = new BrowserWindow({
    width: 400,
    height: overlayHeight,
    x: width - 400,
    y: overlayY,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: false,
    resizable: false,
    focusable: true,
    icon: getIconPath(),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      webSecurity: false
    }
  })

  overlayWindow.loadFile(path.join(__dirname, 'overlay.html'))
  overlayWindow.hide()
}

function showOverlay() {
  overlayWindow.show()
  overlayWindow.focus()
  overlayWindow.webContents.send('overlay-opened')
  isOverlayVisible = true
}

function hideOverlay() {
  overlayWindow.hide()
  isOverlayVisible = false
}

function toggleOverlay() {
  isOverlayVisible ? hideOverlay() : showOverlay()
}

app.whenReady().then(() => {
  app.setAppUserModelId("ar.haleph.overlay")

  const iconPath = getIconPath()
  const trayIcon = nativeImage.createFromPath(iconPath)
  // Tray icons should be small — resize if needed
  tray = new Tray(trayIcon.isEmpty() ? nativeImage.createEmpty() : trayIcon.resize({ width: 22, height: 22 }))

  const contextMenu = Menu.buildFromTemplate([
    { label: 'Abrir overlay (Ctrl+Alt+Space)', click: toggleOverlay },
    { type: 'separator' },
    { label: 'Salir', click: () => app.quit() }
  ])

  tray.setToolTip('HALeph — AI Orchestrator')
  tray.setContextMenu(contextMenu)
  tray.on('click', toggleOverlay)
  tray.on('double-click', toggleOverlay)

  createOverlay()
  setTimeout(() => showOverlay(), 1000)

  globalShortcut.register('CommandOrControl+Alt+Space', toggleOverlay)

  ipcMain.on('hide-overlay', hideOverlay)

  // ── Settings ──
  ipcMain.handle('get-settings', () => ({
    backendUrl: store.get('backendUrl', ''),
    jiraDomain: store.get('jiraDomain', ''),
    teamMembers: store.get('teamMembers', [])
  }))

  ipcMain.handle('save-settings', (_, s) => {
    store.set('backendUrl', s.backendUrl)
    store.set('jiraDomain', s.jiraDomain)
    store.set('teamMembers', s.teamMembers)
    return true
  })

  // ── Action History (persistent) ──
  ipcMain.handle('get-history', () => store.get('actionHistory', []))

  ipcMain.handle('add-history-entry', (_, entry) => {
    const h = store.get('actionHistory', [])
    h.unshift({ ...entry, timestamp: Date.now() })
    if (h.length > 200) h.length = 200
    store.set('actionHistory', h)
    return true
  })

  ipcMain.handle('clear-history', () => {
    store.set('actionHistory', [])
    return true
  })
})

app.on('will-quit', () => globalShortcut.unregisterAll())
app.on('window-all-closed', (e) => e.preventDefault())