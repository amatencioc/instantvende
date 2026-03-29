import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Eye, EyeOff, Zap } from 'lucide-react'
import toast from 'react-hot-toast'
import useAuthStore from '../store/useAuthStore.js'
import client from '../api/client.js'

export default function Login() {
  const [apiKey, setApiKey] = useState('')
  const [showKey, setShowKey] = useState(false)
  const [loading, setLoading] = useState(false)
  const setApiKeyStore = useAuthStore((s) => s.setApiKey)
  const navigate = useNavigate()

  const handleConnect = async (e) => {
    e.preventDefault()
    if (!apiKey.trim()) return
    setLoading(true)
    try {
      useAuthStore.setState({ apiKey: apiKey.trim() })
      await client.get('/api/products', {
        headers: { 'X-API-Key': apiKey.trim() },
      })
      setApiKeyStore(apiKey.trim())
      toast.success('Conectado exitosamente')
      navigate('/dashboard')
    } catch (err) {
      useAuthStore.setState({ apiKey: '' })
      toast.error('API Key inválida. Verifica e intenta de nuevo.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-indigo-50 flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-md"
      >
        <div className="bg-white shadow-xl border border-slate-200 rounded-2xl p-8 flex flex-col gap-6">
          {/* Logo */}
          <div className="flex flex-col items-center gap-3">
            <div className="w-16 h-16 rounded-2xl bg-indigo-600 flex items-center justify-center shadow-lg">
              <Zap size={32} className="text-white" />
            </div>
            <div className="text-center">
              <h1 className="text-2xl font-bold text-indigo-600">InstantVende Admin</h1>
              <p className="text-slate-500 text-sm mt-1">
                Panel de administración web
              </p>
            </div>
          </div>

          {/* Form */}
          <form onSubmit={handleConnect} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-slate-700">
                API Secret Key
              </label>
              <div className="relative">
                <input
                  type={showKey ? 'text' : 'password'}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="sk-..."
                  className="w-full bg-white border border-slate-300 rounded-xl px-4 py-3 pr-12 text-slate-800 placeholder-slate-400 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 transition-all duration-200"
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowKey(!showKey)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
                >
                  {showKey ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              <p className="text-xs text-slate-400">
                Usa la clave configurada en tu archivo{' '}
                <code className="text-indigo-600">.env</code> del backend
              </p>
            </div>

            <motion.button
              type="submit"
              disabled={loading || !apiKey.trim()}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className="w-full py-3 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  Conectando...
                </>
              ) : (
                'Conectar'
              )}
            </motion.button>
          </form>
        </div>
      </motion.div>
    </div>
  )
}
