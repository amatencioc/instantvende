import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Bot, BotOff } from 'lucide-react'
import toast from 'react-hot-toast'
import { getConversationMessages, toggleBot, getConversations } from '../api/conversations.js'
import Card from '../components/ui/Card.jsx'
import Button from '../components/ui/Button.jsx'
import Badge from '../components/ui/Badge.jsx'
import { SkeletonCard } from '../components/ui/Skeleton.jsx'

function formatPhone(phone) {
  if (!phone) return 'Sin número'
  return String(phone)
}

export default function ConversationDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [messages, setMessages] = useState([])
  const [conv, setConv] = useState(null)
  const [loading, setLoading] = useState(true)
  const [toggling, setToggling] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    const load = async () => {
      try {
        const [msgsRes, convsRes] = await Promise.all([
          getConversationMessages(id),
          getConversations(),
        ])
        setMessages(msgsRes.data)
        const found = convsRes.data.find((c) => String(c.id) === String(id))
        setConv(found || null)
      } catch {
        toast.error('Error cargando la conversación')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [id])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleToggle = async () => {
    if (!conv) return
    setToggling(true)
    try {
      await toggleBot(conv.id, !conv.bot_enabled)
      setConv((c) => ({ ...c, bot_enabled: !c.bot_enabled }))
      toast.success(`Bot ${conv.bot_enabled ? 'desactivado' : 'activado'}`)
    } catch {
      toast.error('Error al cambiar el estado del bot')
    } finally {
      setToggling(false)
    }
  }

  if (loading) {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <SkeletonCard />
        <div className="lg:col-span-2 flex flex-col gap-2">
          {[...Array(6)].map((_, i) => <SkeletonCard key={i} />)}
        </div>
      </div>
    )
  }

  const clientLabel = conv?.customer_name || formatPhone(conv?.phone)

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 h-[calc(100vh-120px)]">
      {/* Left panel */}
      <div className="flex flex-col gap-4">
        <Button variant="secondary" onClick={() => navigate('/conversations')} className="self-start">
          <ArrowLeft size={16} /> Volver
        </Button>

        <Card className="flex flex-col gap-4">
          <div className="flex flex-col items-center gap-3 text-center">
            <div className="w-16 h-16 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 text-2xl font-bold">
              {clientLabel.slice(-1).toUpperCase()}
            </div>
            <div>
              <p className="text-slate-800 font-semibold text-lg">{clientLabel}</p>
              {conv?.customer_name && (
                <p className="text-slate-400 text-xs">{formatPhone(conv?.phone)}</p>
              )}
              <p className="text-slate-400 text-xs">Cliente</p>
            </div>
          </div>

          <div className="border-t border-slate-200 pt-4 flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span className="text-slate-500 text-sm">Estado del bot</span>
              <Badge variant={conv?.bot_enabled ? 'green' : 'gray'}>
                {conv?.bot_enabled ? 'Activo' : 'Inactivo'}
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500 text-sm">Mensajes</span>
              <span className="text-slate-800 text-sm font-medium">{messages.length}</span>
            </div>
            {conv?.created_at && (
              <div className="flex items-center justify-between">
                <span className="text-slate-500 text-sm">Inicio</span>
                <span className="text-slate-500 text-xs">
                  {new Date(conv.created_at).toLocaleDateString('es-PE')}
                </span>
              </div>
            )}
          </div>

          <Button
            variant={conv?.bot_enabled ? 'danger' : 'primary'}
            onClick={handleToggle}
            loading={toggling}
            className="w-full"
          >
            {conv?.bot_enabled ? (
              <><BotOff size={16} /> Desactivar bot</>
            ) : (
              <><Bot size={16} /> Activar bot</>
            )}
          </Button>
        </Card>
      </div>

      {/* Right panel — chat */}
      <Card className="lg:col-span-2 flex flex-col p-0 overflow-hidden">
        {/* Header */}
        <div className="p-4 border-b border-slate-200">
          <div className="flex items-center justify-between">
            <p className="text-slate-800 font-medium text-sm">{clientLabel}</p>
            <Badge variant={conv?.bot_enabled ? 'green' : 'gray'}>
              {conv?.bot_enabled ? 'Bot activo' : 'Bot inactivo'}
            </Badge>
          </div>
          {conv && !conv.bot_enabled && (
            <div className="mt-2 px-3 py-2 rounded-lg bg-amber-50 border border-amber-200 text-amber-700 text-xs flex items-center gap-2">
              <BotOff size={14} />
              Bot desactivado — respondiendo manualmente
            </div>
          )}
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3 bg-slate-50">
          {messages.length === 0 ? (
            <div className="flex-1 flex items-center justify-center text-slate-400 text-sm">
              Sin mensajes
            </div>
          ) : (
            messages.map((msg, i) => {
              const isBot = msg.is_bot || msg.role === 'assistant' || msg.sender === 'bot'
              return (
                <div
                  key={msg.id ?? i}
                  className={`flex ${isBot ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[75%] px-4 py-2.5 rounded-2xl text-sm ${
                      isBot
                        ? 'bg-indigo-600 text-white rounded-br-md'
                        : 'bg-white text-slate-800 border border-slate-200 rounded-bl-md shadow-sm'
                    }`}
                  >
                    <p className="whitespace-pre-wrap break-words">{msg.content || msg.text || msg.message}</p>
                    {msg.created_at && (
                      <p className={`text-xs mt-1 ${isBot ? 'text-indigo-200' : 'text-slate-400'}`}>
                        {new Date(msg.created_at).toLocaleTimeString('es-PE', {
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </p>
                    )}
                  </div>
                </div>
              )
            })
          )}
          <div ref={bottomRef} />
        </div>
      </Card>
    </div>
  )
}
