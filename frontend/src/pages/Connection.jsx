import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Wifi, WifiOff, LogOut, Smartphone, User, Globe,
  LayoutDashboard, RefreshCw, Loader2, Zap, Building2, Mail,
} from 'lucide-react'
import toast from 'react-hot-toast'
import { getWaStatus, disconnectWa } from '../api/wa.js'
import useWaStore from '../store/useWaStore.js'
import useAuthStore from '../store/useAuthStore.js'
import useVendorStore from '../store/useVendorStore.js'

export default function Connection() {
  const [loading, setLoading] = useState(true)
  const [confirmDisconnect, setConfirmDisconnect] = useState(false)
  // 'idle' | 'disconnecting' | 'restarting'
  const [disconnectPhase, setDisconnectPhase] = useState('idle')
  const redirectTimer = useRef(null)
  // true solo cuando el usuario escaneó el QR en esta sesión (false → true)
  const justLinked = useRef(false)
  // Guarda el estado anterior de connected para detectar el cambio
  const prevConnected = useRef(null)

  const { connected, info, qrDataUrl, setStatus } = useWaStore()
  const logout = useAuthStore((s) => s.logout)
  const { vendor, clearVendor } = useVendorStore()
  const navigate = useNavigate()

  const fetchStatus = useCallback(async () => {
    try {
      const res = await getWaStatus()
      const wasConnected = prevConnected.current
      const nowConnected = res.data.connected

      // Detectar transición desconectado → conectado (usuario escaneó QR)
      if (wasConnected === false && nowConnected === true) {
        justLinked.current = true
      }
      prevConnected.current = nowConnected

      setStatus(res.data)
      if (res.data.connected || res.data.qrDataUrl) {
        setDisconnectPhase('idle')
        clearTimeout(restartTimeout.current)
      }
    } catch {
      // El proceso WA puede estar reiniciando — no interrumpir la UI
    } finally {
      setLoading(false)
    }
  }, [setStatus])

  // Polling cada 2s para reaccionar rápido a cambios
  useEffect(() => {
    fetchStatus()
    const iv = setInterval(fetchStatus, 2000)
    return () => clearInterval(iv)
  }, [fetchStatus])

  // Auto-redirect SOLO si el usuario acaba de escanear el QR en esta sesión
  useEffect(() => {
    if (connected === true && justLinked.current && disconnectPhase === 'idle') {
      clearTimeout(redirectTimer.current)
      redirectTimer.current = setTimeout(() => navigate('/dashboard'), 1500)
    }
    return () => clearTimeout(redirectTimer.current)
  }, [connected, disconnectPhase, navigate])

  const restartTimeout = useRef(null)

  const handleDisconnect = async () => {
    if (!confirmDisconnect) {
      setConfirmDisconnect(true)
      return
    }
    setConfirmDisconnect(false)
    setDisconnectPhase('disconnecting')
    // Limpiar estado local optimistamente — el proceso WA se reiniciará
    setStatus({ connected: false, info: null, qrDataUrl: null })
    try {
      await disconnectWa()
    } catch {
      // Esperado: el proceso WA puede morir antes de responder
    }
    // Dar tiempo al proceso WA para reiniciarse y generar QR
    setDisconnectPhase('restarting')
    toast('Reiniciando cliente WhatsApp...', { icon: '🔄' })
    // Seguro de fallo: tras 50s forzar 'idle' para que el usuario
    // al menos vea el spinner de "Generando QR" en vez de quedar bloqueado
    clearTimeout(restartTimeout.current)
    restartTimeout.current = setTimeout(() => setDisconnectPhase('idle'), 50000)
  }

  const handleRefreshQr = async () => {
    setDisconnectPhase('restarting')
    setStatus({ connected: false, info: null, qrDataUrl: null })
    try {
      await disconnectWa()
    } catch {
      // esperado: el proceso WA puede morir antes de responder
    }
    toast('Generando nuevo QR...', { icon: '🔄' })
    clearTimeout(restartTimeout.current)
    restartTimeout.current = setTimeout(() => setDisconnectPhase('idle'), 50000)
  }

  const handleLogout = () => {
    logout()
    clearVendor()
    navigate('/login')
  }

  const isDisconnecting = disconnectPhase !== 'idle'

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-indigo-50 flex flex-col items-center justify-center p-4">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -16 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center gap-3 mb-8"
      >
        <div className="w-12 h-12 rounded-2xl bg-indigo-600 flex items-center justify-center shadow-lg">
          <Zap size={24} className="text-white" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-indigo-600">InstantVende</h1>
          <p className="text-xs text-slate-500">Panel de administración</p>
        </div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="w-full max-w-md"
      >
        {/* Vendor profile card */}
        {vendor && (
          <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-4 mb-4 flex items-center gap-4">
            <div className="w-10 h-10 rounded-full bg-indigo-600 flex items-center justify-center text-white font-bold text-sm shrink-0">
              {vendor.name?.[0]?.toUpperCase() || 'V'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-slate-800 truncate">{vendor.name}</p>
              {vendor.business_name && (
                <p className="text-xs text-indigo-600 truncate flex items-center gap-1"><Building2 size={10} />{vendor.business_name}</p>
              )}
              <p className="text-xs text-slate-400 truncate flex items-center gap-1"><Mail size={10} />{vendor.email}</p>
            </div>
          </div>
        )}

        <div className="bg-white shadow-xl border border-slate-200 rounded-2xl overflow-hidden">
          {/* Status banner */}
          <div
            className={`px-6 py-4 flex items-center gap-3 ${
              connected
                ? 'bg-emerald-50 border-b border-emerald-100'
                : isDisconnecting
                ? 'bg-slate-50 border-b border-slate-100'
                : 'bg-amber-50 border-b border-amber-100'
            }`}
          >
            {loading ? (
              <Loader2 size={20} className="animate-spin text-slate-400" />
            ) : connected ? (
              <Wifi size={20} className="text-emerald-600" />
            ) : isDisconnecting ? (
              <Loader2 size={20} className="animate-spin text-slate-400" />
            ) : (
              <WifiOff size={20} className="text-amber-600" />
            )}
            <div>
              <p className={`text-sm font-semibold ${connected ? 'text-emerald-700' : isDisconnecting ? 'text-slate-600' : 'text-amber-700'}`}>
                {loading
                  ? 'Verificando conexión...'
                  : connected
                  ? 'WhatsApp vinculado'
                  : disconnectPhase === 'disconnecting'
                  ? 'Desconectando...'
                  : disconnectPhase === 'restarting'
                  ? 'Reiniciando cliente WhatsApp...'
                  : 'WhatsApp desvinculado'}
              </p>
              <p className="text-xs text-slate-500">
                {connected
                  ? justLinked.current
                    ? 'Entrando al panel en unos segundos...'
                    : 'Tu número está activo y recibiendo mensajes'
                  : disconnectPhase === 'restarting'
                  ? 'El QR aparecerá en 20-30 segundos'
                  : 'Escanea el QR para vincular tu número'}
              </p>
            </div>
          </div>

          <div className="p-6 flex flex-col gap-6">
            <AnimatePresence mode="wait">
              {/* ---- CONNECTED ---- */}
              {connected && (
                <motion.div
                  key="connected"
                  initial={{ opacity: 0, scale: 0.96 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.96 }}
                  className="flex flex-col gap-4"
                >
                  {/* Seller card */}
                  {info && (
                    <div className="rounded-xl border border-slate-100 bg-slate-50 p-4 flex flex-col gap-3">
                      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Cuenta vinculada</p>
                      <InfoRow icon={<User size={15} />} label="Nombre" value={info.pushname || '—'} />
                      <InfoRow icon={<Smartphone size={15} />} label="Número" value={`+${info.phone}`} />
                      <InfoRow icon={<Globe size={15} />} label="Plataforma" value={info.platform || '—'} />
                    </div>
                  )}

                  {/* Auto-redirect notice — solo si acaba de escanear QR */}
                  {justLinked.current && (
                    <div className="flex items-center justify-center gap-2 text-emerald-600">
                      <Loader2 size={16} className="animate-spin" />
                      <p className="text-sm font-medium">Entrando al panel...</p>
                    </div>
                  )}

                  {/* Manual entry button */}
                  <button
                    onClick={() => navigate('/dashboard')}
                    className="w-full flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-3 rounded-xl transition-colors shadow-sm"
                  >
                    <LayoutDashboard size={18} />
                    Entrar al panel
                  </button>

                  {/* Disconnect section */}
                  {confirmDisconnect ? (
                    <div className="flex flex-col gap-2 rounded-xl border border-red-200 bg-red-50 p-4">
                      <p className="text-sm font-medium text-red-700 text-center">
                        ¿Confirmas desconectar el WhatsApp?
                      </p>
                      <p className="text-xs text-red-500 text-center mb-1">
                        El bot dejará de funcionar hasta que lo vuelvas a vincular.
                      </p>
                      <div className="flex gap-2">
                        <button
                          onClick={() => setConfirmDisconnect(false)}
                          className="flex-1 py-2 rounded-lg border border-slate-200 text-slate-600 text-sm font-medium hover:bg-slate-50 transition-colors"
                        >
                          Cancelar
                        </button>
                        <button
                          onClick={handleDisconnect}
                          className="flex-1 py-2 rounded-lg bg-red-600 hover:bg-red-700 text-white text-sm font-semibold transition-colors flex items-center justify-center gap-1"
                        >
                          <LogOut size={14} />
                          Desconectar
                        </button>
                      </div>
                    </div>
                  ) : (
                    <button
                      onClick={handleDisconnect}
                      className="w-full flex items-center justify-center gap-2 border border-red-200 text-red-600 hover:bg-red-50 font-medium py-2.5 rounded-xl transition-colors text-sm"
                    >
                      <LogOut size={16} />
                      Desconectar WhatsApp
                    </button>
                  )}
                </motion.div>
              )}

              {/* ---- DISCONNECTED: QR o spinner de espera ---- */}
              {!connected && !loading && (
                <motion.div
                  key="disconnected"
                  initial={{ opacity: 0, scale: 0.96 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.96 }}
                  className="flex flex-col items-center gap-5"
                >
                  {!isDisconnecting && (
                    <div className="text-center">
                      <p className="text-sm font-semibold text-slate-700 mb-1">Vincula tu WhatsApp</p>
                      <p className="text-xs text-slate-500 leading-relaxed">
                        Abre WhatsApp → Configuración → Dispositivos vinculados → Vincular un dispositivo
                      </p>
                    </div>
                  )}

                  {/* QR o spinner */}
                  <div className="rounded-2xl border-2 border-dashed border-slate-200 p-4 flex items-center justify-center bg-slate-50 min-h-[280px]">
                    {qrDataUrl ? (
                      <img
                        src={qrDataUrl}
                        alt="Código QR de WhatsApp"
                        className="rounded-xl"
                        style={{ width: 260, height: 260 }}
                      />
                    ) : (
                      <div className="flex flex-col items-center gap-3 text-slate-400">
                        <Loader2 size={32} className="animate-spin" />
                        <p className="text-sm">
                          {isDisconnecting ? 'Reiniciando cliente...' : 'Generando código QR...'}
                        </p>
                        <p className="text-xs text-slate-400">Esto puede tomar hasta 30 segundos</p>
                      </div>
                    )}
                  </div>

                  <button
                    onClick={handleRefreshQr}
                    disabled={isDisconnecting}
                    className="flex items-center gap-2 text-xs text-slate-500 hover:text-indigo-600 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    <RefreshCw size={13} className={isDisconnecting ? 'animate-spin' : ''} />
                    {isDisconnecting ? 'Generando nuevo QR...' : 'Actualizar QR'}
                  </button>
                </motion.div>
              )}

              {/* ---- LOADING inicial ---- */}
              {loading && (
                <motion.div
                  key="loading"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex flex-col items-center gap-3 py-8 text-slate-400"
                >
                  <Loader2 size={28} className="animate-spin" />
                  <p className="text-sm">Consultando estado...</p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* Logout from platform */}
        <button
          onClick={handleLogout}
          className="mt-4 w-full text-xs text-slate-400 hover:text-slate-600 transition-colors flex items-center justify-center gap-1.5 py-2"
        >
          <LogOut size={12} />
          Cerrar sesión del panel
        </button>
      </motion.div>
    </div>
  )
}

function InfoRow({ icon, label, value }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-slate-400">{icon}</span>
      <span className="text-xs text-slate-500 w-20 shrink-0">{label}</span>
      <span className="text-sm font-medium text-slate-800 truncate">{value}</span>
    </div>
  )
}
