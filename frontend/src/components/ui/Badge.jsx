import clsx from 'clsx'

const variants = {
  green: 'bg-green-500/20 text-green-400 border border-green-500/30',
  yellow: 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30',
  blue: 'bg-blue-500/20 text-blue-400 border border-blue-500/30',
  red: 'bg-red-500/20 text-red-400 border border-red-500/30',
  cyan: 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30',
  violet: 'bg-violet-500/20 text-violet-400 border border-violet-500/30',
  gray: 'bg-white/10 text-white/60 border border-white/10',
}

export default function Badge({ children, variant = 'gray', className = '' }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium',
        variants[variant] || variants.gray,
        className
      )}
    >
      {children}
    </span>
  )
}
