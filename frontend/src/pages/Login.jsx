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
      // Temporarily set key to test it
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
    <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center p-4 relative overflow-hidden">
      {/* Animated background orbs */}
      <motion.div
        animate={{ scale: [1, 1.2, 1], rotate: [0, 90, 0] }}
        transition={{ duration: 15, repeat: Infinity, ease: 'linear' }}
        className="bg-orb w-[600px] h-[600px] -top-48 -left-48"
        style={{ background: 'radial-gradient(circle, #7c3aed, transparent)' }}
      />
      <motion.div
        animate={{ scale: [1.2, 1, 1.2], rotate: [0, -90, 0] }}
        transition={{ duration: 20, repeat: Infinity, ease: 'linear' }}
        className="bg-orb w-[500px] h-[500px] -bottom-32 -right-32"
        style={{ background: 'radial-gradient(circle, #06b6d4, transparent)' }}
      />

      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="relative z-10 w-full max-w-md"
      >
        <div className="glass p-8 flex flex-col gap-6">
          {/* Logo */}
          <div className="flex flex-col items-center gap-3">
            <motion.div
              animate={{ y: [0, -8, 0] }}
              transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
              className="w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-600 to-cyan-500 flex items-center justify-center glow-violet"
            >
              <Zap size={32} className="text-white" />
            </motion.div>
            <div className="text-center">
              <h1 className="text-2xl font-bold gradient-text">InstantVende Admin</h1>
              <p className="text-white/50 text-sm mt-1">
                Panel de administración web
              </p>
            </div>
          </div>

          {/* Form */}
          <form onSubmit={handleConnect} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-white/70">
                API Secret Key
              </label>
              <div className="relative">
                <input
                  type={showKey ? 'text' : 'password'}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="sk-..."
                  className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 pr-12 text-white placeholder-white/20 outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500/30 transition-all duration-200"
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowKey(!showKey)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-white/40 hover:text-white/70 transition-colors"
                >
                  {showKey ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              <p className="text-xs text-white/30">
                Usa la clave configurada en tu archivo{' '}
                <code className="text-violet-400">.env</code> del backend
              </p>
            </div>

            <motion.button
              type="submit"
              disabled={loading || !apiKey.trim()}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className="w-full py-3 rounded-xl bg-gradient-to-r from-violet-600 to-cyan-500 text-white font-semibold text-sm transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 glow-violet"
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
