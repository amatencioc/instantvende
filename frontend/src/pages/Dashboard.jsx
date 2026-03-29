import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'
import { MessageSquare, Package, ShoppingCart, TrendingUp } from 'lucide-react'
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from 'recharts'
import { getAnalytics } from '../api/analytics.js'
import StatCard from '../components/ui/StatCard.jsx'
import Card from '../components/ui/Card.jsx'
import { SkeletonCard } from '../components/ui/Skeleton.jsx'

const STATUS_COLORS = {
  pending: '#eab308',
  confirmed: '#3b82f6',
  shipped: '#06b6d4',
  delivered: '#22c55e',
  cancelled: '#ef4444',
}

const STATUS_LABELS = {
  pending: 'Pendiente',
  confirmed: 'Confirmado',
  shipped: 'En camino',
  delivered: 'Entregado',
  cancelled: 'Cancelado',
}

function maskPhone(phone) {
  if (!phone) return '****'
  const str = String(phone)
  return '****' + str.slice(-4)
}

function getGreeting() {
  const h = new Date().getHours()
  if (h < 12) return 'Buenos días'
  if (h < 18) return 'Buenas tardes'
  return 'Buenas noches'
}

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    getAnalytics()
      .then((r) => setData(r.data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const today = format(new Date(), "EEEE d 'de' MMMM", { locale: es })

  if (loading) {
    return (
      <div className="flex flex-col gap-6">
        <div className="h-8 w-64 bg-white/10 rounded-xl animate-pulse" />
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => <SkeletonCard key={i} />)}
        </div>
      </div>
    )
  }

  const ordersByStatus = data?.orders_by_status || {}
  const pieData = Object.entries(ordersByStatus).map(([key, val]) => ({
    name: STATUS_LABELS[key] || key,
    value: val,
    color: STATUS_COLORS[key] || '#888',
  }))

  const topProducts = data?.top_products || []
  const recentConvs = data?.recent_conversations || []

  const confirmedRevenue = (data?.revenue_confirmed || 0) / 100

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">
          {getGreeting()}, <span className="gradient-text">administrador</span>
        </h1>
        <p className="text-white/40 text-sm mt-1 capitalize">{today}</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard
          icon={MessageSquare}
          label="Total Conversaciones"
          value={data?.total_conversations ?? 0}
          color="violet"
        />
        <StatCard
          icon={ShoppingCart}
          label="Pedidos Totales"
          value={data?.total_orders ?? 0}
          color="cyan"
        />
        <StatCard
          icon={TrendingUp}
          label="Ingresos Confirmados"
          value={`S/ ${confirmedRevenue.toFixed(2)}`}
          sub="Confirmados + enviados + entregados"
          color="green"
        />
        <StatCard
          icon={Package}
          label="Productos en Stock"
          value={data?.products_in_stock ?? 0}
          color="yellow"
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Pie chart */}
        <Card>
          <h2 className="text-base font-semibold text-white mb-4">Pedidos por estado</h2>
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={90}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {pieData.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    background: 'rgba(10,10,20,0.95)',
                    border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: 12,
                    color: '#f8fafc',
                  }}
                />
                <Legend
                  formatter={(value) => (
                    <span style={{ color: 'rgba(255,255,255,0.7)', fontSize: 12 }}>
                      {value}
                    </span>
                  )}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[240px] flex items-center justify-center text-white/30 text-sm">
              Sin datos de pedidos
            </div>
          )}
        </Card>

        {/* Bar chart */}
        <Card>
          <h2 className="text-base font-semibold text-white mb-4">Top 5 productos más vendidos</h2>
          {topProducts.length > 0 ? (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={topProducts} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis type="number" tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 11 }} />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={100}
                  tick={{ fill: 'rgba(255,255,255,0.6)', fontSize: 11 }}
                />
                <Tooltip
                  contentStyle={{
                    background: 'rgba(10,10,20,0.95)',
                    border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: 12,
                    color: '#f8fafc',
                  }}
                />
                <Bar dataKey="units_sold" fill="#7c3aed" radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[240px] flex items-center justify-center text-white/30 text-sm">
              Sin datos de ventas
            </div>
          )}
        </Card>
      </div>

      {/* Recent activity */}
      <Card>
        <h2 className="text-base font-semibold text-white mb-4">Actividad reciente</h2>
        {recentConvs.length > 0 ? (
          <div className="flex flex-col gap-2">
            {recentConvs.map((conv, i) => (
              <div
                key={conv.id ?? i}
                onClick={() => navigate(`/conversations/${conv.id}`)}
                className="flex items-center gap-3 p-3 rounded-xl hover:bg-white/5 cursor-pointer transition-colors"
              >
                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-violet-600 to-cyan-500 flex items-center justify-center text-white font-bold text-sm flex-shrink-0">
                  {maskPhone(conv.phone_number).slice(-1)}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-white/80 text-sm font-medium">
                    {maskPhone(conv.phone_number)}
                  </p>
                  <p className="text-white/40 text-xs truncate">
                    {conv.last_message || 'Sin mensajes'}
                  </p>
                </div>
                <span className="text-white/30 text-xs flex-shrink-0">
                  {conv.last_message_at
                    ? format(new Date(conv.last_message_at), 'HH:mm')
                    : ''}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-white/30 text-sm text-center py-8">Sin conversaciones recientes</p>
        )}
      </Card>
    </div>
  )
}
