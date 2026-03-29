import clsx from 'clsx'

export default function Input({
  label,
  error,
  className = '',
  type = 'text',
  ...props
}) {
  return (
    <div className="flex flex-col gap-1">
      {label && (
        <label className="text-sm font-medium text-white/70">{label}</label>
      )}
      <input
        type={type}
        className={clsx(
          'w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-white placeholder-white/30 outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500/30 transition-all duration-200',
          error && 'border-red-500/50 focus:border-red-500',
          className
        )}
        {...props}
      />
      {error && <p className="text-xs text-red-400">{error}</p>}
    </div>
  )
}
