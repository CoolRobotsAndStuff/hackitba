const { app, BrowserWindow, Tray, Menu, globalShortcut, screen, ipcMain, nativeImage } = require('electron')
const Store = require('electron-store')
const path = require('path')
const fs = require('fs')

const store = new Store()

let tray = null
let overlayWindow = null
let isOverlayVisible = false

// Icon path — works in both dev (npm start) and packaged (AppImage)
function getIconPath() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'icon.png')
  }
  return path.join(__dirname, 'assets', 'icon.png')
}

// On Linux (Wayland), the dock icon ONLY works via .desktop file.
// This auto-installs one with the correct icon + StartupWMClass.
function installDesktopFile() {
  if (process.platform !== 'linux') return

  const iconSrc = getIconPath()
  const homeDir = require('os').homedir()

  // Copy icon to a stable location GNOME can always find
  const iconDir = path.join(homeDir, '.local', 'share', 'icons')
  const iconDst = path.join(iconDir, 'haleph.png')
  try {
    fs.mkdirSync(iconDir, { recursive: true })
    fs.copyFileSync(iconSrc, iconDst)
  } catch (e) {
    console.warn('[ICON] Could not copy icon:', e.message)
  }

  // Determine Exec line
  let execLine
  if (app.isPackaged) {
    execLine = process.env.APPIMAGE || process.execPath
  } else {
    execLine = `bash -c "cd ${path.dirname(__dirname)} && npm start"`
  }

  const desktopContent = `[Desktop Entry]
Name=HALeph
Comment=AI Project Orchestrator
Exec=${execLine}
Icon=${iconDst}
Type=Application
Categories=Utility;
StartupWMClass=haleph-overlay
Terminal=false
`

  const desktopDir = path.join(homeDir, '.local', 'share', 'applications')
  const desktopFile = path.join(desktopDir, 'haleph-overlay.desktop')
  try {
    fs.mkdirSync(desktopDir, { recursive: true })
    fs.writeFileSync(desktopFile, desktopContent)
    console.log('[ICON] Desktop file installed:', desktopFile)
  } catch (e) {
    console.warn('[ICON] Could not write .desktop file:', e.message)
  }
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

  // Install .desktop file so Linux dock shows the icon
  installDesktopFile()

  const iconPath = getIconPath()
  const iconImage = nativeImage.createFromPath(iconPath)

  if (iconImage.isEmpty()) {
    console.warn('[WARN] Icon not found at:', iconPath)
  } else {
    console.log('[INFO] Icon loaded:', iconPath, iconImage.getSize())
  }

  const trayIcon = iconImage.isEmpty() ? nativeImage.createEmpty() : iconImage.resize({ width: 22, height: 22 })
  tray = new Tray(trayIcon)

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