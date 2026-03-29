import clsx from 'clsx'

const variants = {
  primary:
    'bg-gradient-to-r from-violet-600 to-cyan-500 text-white hover:opacity-90',
  secondary:
    'bg-white/10 text-white/80 hover:bg-white/15 border border-white/10',
  danger: 'bg-red-500/20 text-red-400 hover:bg-red-500/30 border border-red-500/30',
  ghost: 'text-white/60 hover:text-white hover:bg-white/5',
}

export default function Button({
  children,
  variant = 'primary',
  loading = false,
  disabled = false,
  className = '',
  ...props
}) {
  return (
    <button
      disabled={disabled || loading}
      className={clsx(
        'inline-flex items-center justify-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed',
        variants[variant] || variants.secondary,
        className
      )}
      {...props}
    >
      {loading && (
        <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8v8H4z"
          />
        </svg>
      )}
      {children}
    </button>
  )
}
