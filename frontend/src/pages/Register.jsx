import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Zap, Loader2, User, Mail, Lock, Building2, Eye, EyeOff } from 'lucide-react'
import toast from 'react-hot-toast'
import { registerVendor } from '../api/vendors.js'
import useVendorStore from '../store/useVendorStore.js'
import useAuthStore from '../store/useAuthStore.js'

export default function Register() {
  const [form, setForm] = useState({ name: '', email: '', business_name: '', password: '', confirm: '' })
  const [showPw, setShowPw] = useState(false)
  const [loading, setLoading] = useState(false)
  const setVendor = useVendorStore((s) => s.setVendor)
  const setApiKey = useAuthStore((s) => s.setApiKey)
  const navigate = useNavigate()

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.name.trim() || !form.email.trim() || !form.password) return
    if (form.password !== form.confirm) {
      toast.error('Las contraseñas no coinciden')
      return
    }
    setLoading(true)
    try {
      const res = await registerVendor({
        name: form.name.trim(),
        email: form.email.trim(),
        business_name: form.business_name.trim() || undefined,
        password: form.password,
      })
      setVendor(res.data.vendor)
      setApiKey(res.data.api_key)
      toast.success('¡Cuenta creada! Ahora vincula tu WhatsApp.')
      navigate('/connection')
    } catch (err) {
      const detail = err?.response?.data?.detail
      toast.error(detail || 'Error al registrar. Intenta de nuevo.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-indigo-50 flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="w-full max-w-md"
      >
        <div className="bg-white shadow-xl border border-slate-200 rounded-2xl p-8 flex flex-col gap-6">
          {/* Logo */}
          <div className="flex flex-col items-center gap-3">
            <div className="w-14 h-14 rounded-2xl bg-indigo-600 flex items-center justify-center shadow-lg">
              <Zap size={28} className="text-white" />
            </div>
            <div className="text-center">
              <h1 className="text-2xl font-bold text-indigo-600">Crear cuenta</h1>
              <p className="text-slate-500 text-sm mt-1">Únete a InstantVende como vendedor</p>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <Field label="Nombre completo" icon={<User size={15} />} required>
              <input
                type="text"
                value={form.name}
                onChange={set('name')}
                placeholder="Juan Pérez"
                required
                className={inputCls}
              />
            </Field>

            <Field label="Email" icon={<Mail size={15} />} required>
              <input
                type="email"
                value={form.email}
                onChange={set('email')}
                placeholder="tu@email.com"
                required
                className={inputCls}
              />
            </Field>

            <Field label="Nombre del negocio" icon={<Building2 size={15} />}>
              <input
                type="text"
                value={form.business_name}
                onChange={set('business_name')}
                placeholder="Opcional — ej: Fresh Boy Store"
                className={inputCls}
              />
            </Field>

            <Field label="Contraseña" icon={<Lock size={15} />} required>
              <div className="relative">
                <input
                  type={showPw ? 'text' : 'password'}
                  value={form.password}
                  onChange={set('password')}
                  placeholder="Mínimo 6 caracteres"
                  required
                  className={inputCls + ' pr-10'}
                />
                <button
                  type="button"
                  onClick={() => setShowPw((s) => !s)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                >
                  {showPw ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </Field>

            <Field label="Confirmar contraseña" icon={<Lock size={15} />} required>
              <input
                type={showPw ? 'text' : 'password'}
                value={form.confirm}
                onChange={set('confirm')}
                placeholder="Repite tu contraseña"
                required
                className={inputCls}
              />
            </Field>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white font-semibold py-3 rounded-xl transition-colors flex items-center justify-center gap-2 shadow-sm mt-1"
            >
              {loading ? <Loader2 size={18} className="animate-spin" /> : <Zap size={18} />}
              {loading ? 'Creando cuenta...' : 'Crear cuenta'}
            </button>
          </form>

          <p className="text-center text-sm text-slate-500">
            ¿Ya tienes cuenta?{' '}
            <Link to="/login" className="text-indigo-600 font-medium hover:underline">
              Inicia sesión
            </Link>
          </p>
        </div>
      </motion.div>
    </div>
  )
}

const inputCls =
  'w-full bg-white border border-slate-300 rounded-xl px-4 py-2.5 text-slate-800 placeholder-slate-400 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 transition-all duration-200 text-sm'

function Field({ label, icon, required, children }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs font-medium text-slate-600 flex items-center gap-1.5">
        <span className="text-slate-400">{icon}</span>
        {label}
        {required && <span className="text-red-400">*</span>}
      </label>
      {children}
    </div>
  )
}
