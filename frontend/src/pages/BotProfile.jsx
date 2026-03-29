import { useEffect, useState } from 'react'
import { useForm, Controller } from 'react-hook-form'
import { ChevronDown, Save, RefreshCw, Download, Upload, Bot } from 'lucide-react'
import toast from 'react-hot-toast'
import { getBotProfile, updateBotProfile, resetBotProfile } from '../api/botProfile.js'
import Card from '../components/ui/Card.jsx'
import Button from '../components/ui/Button.jsx'
import Input from '../components/ui/Input.jsx'
import ConfirmDialog from '../components/shared/ConfirmDialog.jsx'
import { SkeletonCard } from '../components/ui/Skeleton.jsx'

function Section({ title, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="glass overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-5 text-left"
      >
        <span className="font-semibold text-white">{title}</span>
        <ChevronDown
          size={16}
          className={`text-white/50 transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
        />
      </button>
      {open && (
        <div className="px-5 pb-5 border-t border-white/10 pt-5 flex flex-col gap-4">
          {children}
        </div>
      )}
    </div>
  )
}

function TagsInput({ value = [], onChange, placeholder }) {
  const [input, setInput] = useState('')

  const add = () => {
    const trimmed = input.trim()
    if (trimmed && !value.includes(trimmed)) {
      onChange([...value, trimmed])
      setInput('')
    }
  }

  const remove = (tag) => onChange(value.filter((t) => t !== tag))

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-1.5">
        {value.map((tag) => (
          <span
            key={tag}
            className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs bg-violet-600/20 text-violet-400 border border-violet-500/30"
          >
            {tag}
            <button onClick={() => remove(tag)} className="hover:text-white">×</button>
          </span>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add() } }}
          placeholder={placeholder}
          className="flex-1 bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-sm text-white placeholder-white/30 outline-none focus:border-violet-500 transition-all"
        />
        <Button variant="secondary" onClick={add} type="button" className="!py-2">+</Button>
      </div>
    </div>
  )
}

function ListInput({ value = [], onChange, placeholder }) {
  const [input, setInput] = useState('')

  const add = () => {
    const trimmed = input.trim()
    if (trimmed) { onChange([...value, trimmed]); setInput('') }
  }

  const remove = (i) => onChange(value.filter((_, idx) => idx !== i))

  return (
    <div className="flex flex-col gap-2">
      {value.map((item, i) => (
        <div key={i} className="flex gap-2">
          <span className="flex-1 bg-white/5 border border-white/5 rounded-xl px-3 py-2 text-sm text-white/80 truncate">{item}</span>
          <button onClick={() => remove(i)} className="text-white/30 hover:text-red-400 px-2 transition-colors">×</button>
        </div>
      ))}
      <div className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add() } }}
          placeholder={placeholder}
          className="flex-1 bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-sm text-white placeholder-white/30 outline-none focus:border-violet-500 transition-all"
        />
        <Button variant="secondary" onClick={add} type="button" className="!py-2">+</Button>
      </div>
    </div>
  )
}

// Deep-get helper
function dget(obj, path, def = '') {
  return path.split('.').reduce((acc, k) => (acc && acc[k] !== undefined ? acc[k] : def), obj)
}

export default function BotProfile() {
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [confirmReset, setConfirmReset] = useState(false)
  const [local, setLocal] = useState({})

  useEffect(() => {
    getBotProfile()
      .then((r) => {
        setProfile(r.data)
        setLocal(r.data)
      })
      .catch(() => toast.error('Error cargando perfil del bot'))
      .finally(() => setLoading(false))
  }, [])

  const FORBIDDEN_KEYS = new Set(['__proto__', 'constructor', 'prototype'])

  const set = (path, value) => {
    setLocal((prev) => {
      const keys = path.split('.')
      if (keys.some((k) => FORBIDDEN_KEYS.has(k))) return prev
      // Deep clone via JSON to avoid mutating state
      const next = JSON.parse(JSON.stringify(prev))
      // Build nested path safely using reduce to avoid reassigning cur via prototype chain
      const parentKeys = keys.slice(0, -1)
      const lastKey = keys[keys.length - 1]
      if (FORBIDDEN_KEYS.has(lastKey)) return prev
      const parent = parentKeys.reduce((acc, k) => {
        if (!Object.prototype.hasOwnProperty.call(acc, k) || typeof acc[k] !== 'object' || acc[k] === null) {
          acc[k] = {}
        }
        return acc[k]
      }, next)
      parent[lastKey] = value
      return next
    })
  }

  const get = (path, def = '') => dget(local, path, def)

  const handleSave = async () => {
    setSaving(true)
    try {
      await updateBotProfile(local)
      setProfile(local)
      toast.success('Perfil del bot guardado')
    } catch {
      toast.error('Error guardando perfil')
    } finally {
      setSaving(false)
    }
  }

  const handleReset = async () => {
    setResetting(true)
    try {
      const r = await resetBotProfile()
      setLocal(r.data)
      setProfile(r.data)
      toast.success('Perfil restaurado por defecto')
    } catch {
      toast.error('Error restaurando perfil')
    } finally {
      setResetting(false)
      setConfirmReset(false)
    }
  }

  const handleExport = () => {
    const blob = new Blob([JSON.stringify(local, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'bot_profile.json'
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleImport = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => {
      try {
        const data = JSON.parse(ev.target.result)
        setLocal(data)
        toast.success('Perfil importado — recuerda guardar los cambios')
      } catch {
        toast.error('JSON inválido')
      }
    }
    reader.readAsText(file)
    e.target.value = ''
  }

  if (loading) {
    return (
      <div className="flex flex-col gap-4">
        {[...Array(4)].map((_, i) => <SkeletonCard key={i} />)}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4 max-w-3xl">
      {/* Action bar */}
      <Card className="flex flex-wrap gap-3 items-center justify-between">
        <div className="flex items-center gap-2">
          <Bot size={20} className="text-violet-400" />
          <span className="font-semibold text-white">Editor del Perfil del Bot</span>
        </div>
        <div className="flex gap-2 flex-wrap">
          <label className="cursor-pointer">
            <input type="file" accept=".json" onChange={handleImport} className="hidden" />
            <span className="inline-flex items-center gap-2 px-3 py-2 rounded-xl bg-white/10 text-white/80 hover:bg-white/15 border border-white/10 text-sm font-medium transition-all cursor-pointer">
              <Upload size={14} /> Importar
            </span>
          </label>
          <Button variant="secondary" onClick={handleExport}>
            <Download size={14} /> Exportar
          </Button>
          <Button variant="danger" onClick={() => setConfirmReset(true)} loading={resetting}>
            <RefreshCw size={14} /> Restaurar
          </Button>
          <Button onClick={handleSave} loading={saving}>
            <Save size={14} /> Guardar cambios
          </Button>
        </div>
      </Card>

      {/* Section 1 — Bot identity */}
      <Section title="1. Identidad del Bot" defaultOpen>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Input label="Nombre del bot" value={get('bot.name')} onChange={(e) => set('bot.name', e.target.value)} />
          <Input label="Rol" value={get('bot.role')} onChange={(e) => set('bot.role', e.target.value)} />
          <Input label="Años de experiencia" type="number" value={get('bot.experience_years')} onChange={(e) => set('bot.experience_years', parseInt(e.target.value) || 0)} />
          <Input label="Estilo de lenguaje" value={get('bot.language_style')} onChange={(e) => set('bot.language_style', e.target.value)} />
        </div>
        <div>
          <label className="text-sm font-medium text-white/70 block mb-1.5">Palabras características</label>
          <TagsInput
            value={get('bot.characteristic_words', [])}
            onChange={(v) => set('bot.characteristic_words', v)}
            placeholder="Agregar palabra y Enter..."
          />
        </div>
        <div>
          <label className="text-sm font-medium text-white/70 block mb-2">
            Máximo emojis por respuesta: <span className="text-violet-400">{get('bot.max_emojis', 3)}</span>
          </label>
          <input
            type="range"
            min={0}
            max={5}
            value={get('bot.max_emojis', 3)}
            onChange={(e) => set('bot.max_emojis', parseInt(e.target.value))}
            className="w-full accent-violet-500"
          />
        </div>
      </Section>

      {/* Section 2 — Store info */}
      <Section title="2. Información de la Tienda">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Input label="Nombre de la tienda" value={get('store.name')} onChange={(e) => set('store.name', e.target.value)} />
          <Input label="Tipo de tienda" value={get('store.type')} onChange={(e) => set('store.type', e.target.value)} />
          <Input label="Dirección" value={get('store.address')} onChange={(e) => set('store.address', e.target.value)} />
          <Input label="Teléfono" value={get('store.phone')} onChange={(e) => set('store.phone', e.target.value)} />
          <Input label="Website" value={get('store.website')} onChange={(e) => set('store.website', e.target.value)} />
          <Input label="URL del logo" value={get('store.logo_url')} onChange={(e) => set('store.logo_url', e.target.value)} />
        </div>
      </Section>

      {/* Section 3 — Schedule */}
      <Section title="3. Horarios">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Input label="Lunes a Viernes" value={get('schedule.weekday')} onChange={(e) => set('schedule.weekday', e.target.value)} />
          <Input label="Sábados" value={get('schedule.saturday')} onChange={(e) => set('schedule.saturday', e.target.value)} />
          <Input label="Domingos" value={get('schedule.sunday')} onChange={(e) => set('schedule.sunday', e.target.value)} />
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium text-white/70">Zona horaria</label>
            <select
              value={get('schedule.timezone', 'America/Lima')}
              onChange={(e) => set('schedule.timezone', e.target.value)}
              className="bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-white outline-none focus:border-violet-500 transition-all"
            >
              {['America/Lima', 'America/Bogota', 'America/Santiago', 'America/Buenos_Aires', 'America/Mexico_City', 'America/Caracas'].map((tz) => (
                <option key={tz} value={tz} style={{ background: '#0a0a0f' }}>{tz}</option>
              ))}
            </select>
          </div>
        </div>
      </Section>

      {/* Section 4 — Shipping */}
      <Section title="4. Envíos">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Input
            label="Precio Lima (S/)"
            type="number"
            step="0.01"
            value={(get('shipping.lima_cents', 0) / 100).toFixed(2)}
            onChange={(e) => set('shipping.lima_cents', Math.round(parseFloat(e.target.value) * 100))}
          />
          <Input label="ETA Lima" value={get('shipping.lima_eta')} onChange={(e) => set('shipping.lima_eta', e.target.value)} />
          <Input
            label="Precio Provincias (S/)"
            type="number"
            step="0.01"
            value={(get('shipping.provinces_cents', 0) / 100).toFixed(2)}
            onChange={(e) => set('shipping.provinces_cents', Math.round(parseFloat(e.target.value) * 100))}
          />
          <Input label="ETA Provincias" value={get('shipping.provinces_eta')} onChange={(e) => set('shipping.provinces_eta', e.target.value)} />
          <Input
            label="Umbral envío gratis (S/)"
            type="number"
            step="0.01"
            value={(get('shipping.free_threshold_cents', 0) / 100).toFixed(2)}
            onChange={(e) => set('shipping.free_threshold_cents', Math.round(parseFloat(e.target.value) * 100))}
          />
        </div>
        <div>
          <label className="text-sm font-medium text-white/70 block mb-1.5">Transportistas</label>
          <TagsInput
            value={get('shipping.carriers', [])}
            onChange={(v) => set('shipping.carriers', v)}
            placeholder="Agregar transportista..."
          />
        </div>
      </Section>

      {/* Section 5 — Discounts */}
      <Section title="5. Descuentos">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Input
            label="Descuento 2 productos (%)"
            type="number"
            min={0}
            max={100}
            value={get('discounts.two_products_pct', 0)}
            onChange={(e) => set('discounts.two_products_pct', parseFloat(e.target.value) || 0)}
          />
          <Input
            label="Descuento 3+ productos (%)"
            type="number"
            min={0}
            max={100}
            value={get('discounts.three_plus_pct', 0)}
            onChange={(e) => set('discounts.three_plus_pct', parseFloat(e.target.value) || 0)}
          />
        </div>
      </Section>

      {/* Section 6 — Messages */}
      <Section title="6. Mensajes Personalizados">
        {[
          { key: 'messages.timeout', label: 'Mensaje de timeout' },
          { key: 'messages.general_error', label: 'Mensaje de error general' },
          { key: 'messages.rate_limit', label: 'Mensaje de límite de velocidad' },
        ].map(({ key, label }) => (
          <div key={key} className="flex flex-col gap-1">
            <label className="text-sm font-medium text-white/70">{label}</label>
            <textarea
              rows={2}
              value={get(key)}
              onChange={(e) => set(key, e.target.value)}
              className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-white placeholder-white/30 outline-none focus:border-violet-500 transition-all resize-none text-sm"
            />
          </div>
        ))}
        <div>
          <label className="text-sm font-medium text-white/70 block mb-1.5">Saludos (clientes nuevos)</label>
          <ListInput
            value={get('messages.greetings_new', [])}
            onChange={(v) => set('messages.greetings_new', v)}
            placeholder="Agregar saludo..."
          />
        </div>
        <div>
          <label className="text-sm font-medium text-white/70 block mb-1.5">Saludos (clientes recurrentes)</label>
          <ListInput
            value={get('messages.greetings_returning', [])}
            onChange={(v) => set('messages.greetings_returning', v)}
            placeholder="Agregar saludo..."
          />
        </div>
        <div>
          <label className="text-sm font-medium text-white/70 block mb-1.5">Despedidas</label>
          <ListInput
            value={get('messages.farewells', [])}
            onChange={(v) => set('messages.farewells', v)}
            placeholder="Agregar despedida..."
          />
        </div>
      </Section>

      {/* Section 7 — AI params */}
      <Section title="7. Parámetros de IA">
        <div className="flex flex-col gap-1">
          <label className="text-sm font-medium text-white/70">
            Temperature: <span className="text-violet-400">{Number(get('ai.temperature', 0.7)).toFixed(1)}</span>
          </label>
          <input
            type="range"
            min={0}
            max={1}
            step={0.1}
            value={get('ai.temperature', 0.7)}
            onChange={(e) => set('ai.temperature', parseFloat(e.target.value))}
            className="w-full accent-violet-500"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-sm font-medium text-white/70">
            Max tokens: <span className="text-violet-400">{get('ai.num_predict', 120)}</span>
          </label>
          <input
            type="range"
            min={20}
            max={200}
            step={5}
            value={get('ai.num_predict', 120)}
            onChange={(e) => set('ai.num_predict', parseInt(e.target.value))}
            className="w-full accent-violet-500"
          />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Input
            label="Máx. chars en respuesta"
            type="number"
            min={100}
            value={get('ai.max_response_chars', 1000)}
            onChange={(e) => set('ai.max_response_chars', parseInt(e.target.value) || 1000)}
          />
          <Input
            label="Límite historial mensajes"
            type="number"
            min={1}
            value={get('ai.max_history_messages', 10)}
            onChange={(e) => set('ai.max_history_messages', parseInt(e.target.value) || 10)}
          />
        </div>
      </Section>

      {/* Section 8 — System prompt */}
      <Section title="8. System Prompt">
        <div className="flex flex-col gap-1">
          <label className="text-sm font-medium text-white/70">Template del system prompt</label>
          <textarea
            rows={10}
            value={get('system_prompt_template', '')}
            onChange={(e) => set('system_prompt_template', e.target.value)}
            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white/80 placeholder-white/30 outline-none focus:border-violet-500 transition-all resize-y text-xs font-mono"
            placeholder="Usa {bot_name}, {store_name}, etc. como variables de plantilla..."
          />
        </div>
      </Section>

      {/* Floating save */}
      <div className="flex justify-end gap-3 sticky bottom-4">
        <Button onClick={handleSave} loading={saving} className="shadow-lg">
          <Save size={16} /> Guardar cambios
        </Button>
      </div>

      <ConfirmDialog
        open={confirmReset}
        onClose={() => setConfirmReset(false)}
        onConfirm={handleReset}
        loading={resetting}
        title="Restaurar perfil por defecto"
        message="¿Restaurar el perfil del bot a los valores por defecto? Esta acción no se puede deshacer."
      />
    </div>
  )
}
