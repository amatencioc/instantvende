import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import Layout from './components/layout/Layout.jsx'
import Login from './pages/Login.jsx'
import Register from './pages/Register.jsx'
import Connection from './pages/Connection.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Conversations from './pages/Conversations.jsx'
import ConversationDetail from './pages/ConversationDetail.jsx'
import Products from './pages/Products.jsx'
import Orders from './pages/Orders.jsx'
import BotProfile from './pages/BotProfile.jsx'
import useAuthStore from './store/useAuthStore.js'
import useWaStore from './store/useWaStore.js'
import useVendorStore from './store/useVendorStore.js'
import { getWaStatus } from './api/wa.js'

/** Redirige al login si el vendedor no está autenticado */
function PrivateRoute({ children }) {
  const apiKey = useAuthStore((s) => s.apiKey)
  const vendor = useVendorStore((s) => s.vendor)
  if (!apiKey || !vendor) return <Navigate to="/login" replace />
  return children
}

/**
 * Requiere login + WA conectado.
 * Si WA no está conectado redirige a /connection.
 * Consulta el estado una sola vez cuando connected === null (ej: reload de página).
 */
function ConnectedRoute({ children }) {
  const apiKey = useAuthStore((s) => s.apiKey)
  const vendor = useVendorStore((s) => s.vendor)
  const { connected, setStatus } = useWaStore()
  const [checking, setChecking] = useState(connected === null)

  useEffect(() => {
    if (apiKey && connected === null) {
      getWaStatus()
        .then((r) => setStatus(r.data))
        .catch(() => setStatus({ connected: false, info: null, qrDataUrl: null }))
        .finally(() => setChecking(false))
    } else {
      setChecking(false)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  if (!apiKey || !vendor) return <Navigate to="/login" replace />
  if (checking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <Loader2 size={28} className="animate-spin text-indigo-500" />
      </div>
    )
  }
  if (!connected) return <Navigate to="/connection" replace />
  return children
}

export default function App() {
  return (
    <BrowserRouter>
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: '#ffffff',
            color: '#0f172a',
            border: '1px solid #e2e8f0',
            boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)',
          },
        }}
      />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />

        {/* Página de conexión WA — requiere login, no requiere WA conectado */}
        <Route
          path="/connection"
          element={
            <PrivateRoute>
              <Connection />
            </PrivateRoute>
          }
        />

        {/* Panel admin — requiere login + WA conectado */}
        <Route
          path="/"
          element={
            <ConnectedRoute>
              <Layout />
            </ConnectedRoute>
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="conversations" element={<Conversations />} />
          <Route path="conversations/:id" element={<ConversationDetail />} />
          <Route path="products" element={<Products />} />
          <Route path="orders" element={<Orders />} />
          <Route path="bot-profile" element={<BotProfile />} />
        </Route>

        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

