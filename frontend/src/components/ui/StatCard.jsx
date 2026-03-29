import { motion } from 'framer-motion'
import Card from './Card.jsx'

export default function StatCard({ icon: Icon, label, value, sub, color = 'indigo' }) {
  const iconColors = {
    indigo: 'bg-indigo-50 text-indigo-600',
    violet: 'bg-violet-50 text-violet-600',
    cyan: 'bg-cyan-50 text-cyan-600',
    green: 'bg-emerald-50 text-emerald-600',
    yellow: 'bg-amber-50 text-amber-600',
  }

  return (
    <motion.div
      whileHover={{ scale: 1.02 }}
      transition={{ duration: 0.2 }}
    >
      <Card className="flex items-start gap-4">
        <div
          className={`w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0 ${iconColors[color] || iconColors.indigo}`}
        >
          <Icon size={22} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-slate-500 text-sm">{label}</p>
          <p className="text-2xl font-bold text-slate-800 mt-0.5">{value}</p>
          {sub && <p className="text-slate-400 text-xs mt-1">{sub}</p>}
        </div>
      </Card>
    </motion.div>
  )
}
