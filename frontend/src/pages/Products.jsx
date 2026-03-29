import { useEffect, useState, useMemo } from 'react'
import { useForm } from 'react-hook-form'
import { Plus, Search, Pencil, Trash2, Package } from 'lucide-react'
import toast from 'react-hot-toast'
import { getProducts, createProduct, updateProduct, deleteProduct } from '../api/products.js'
import Card from '../components/ui/Card.jsx'
import Button from '../components/ui/Button.jsx'
import Badge from '../components/ui/Badge.jsx'
import Modal from '../components/ui/Modal.jsx'
import Input from '../components/ui/Input.jsx'
import EmptyState from '../components/ui/EmptyState.jsx'
import ConfirmDialog from '../components/shared/ConfirmDialog.jsx'
import { SkeletonCard } from '../components/ui/Skeleton.jsx'

function stockVariant(stock) {
  if (stock === 0) return 'red'
  if (stock <= 5) return 'yellow'
  return 'green'
}

function stockLabel(stock) {
  if (stock === 0) return '❌ Sin stock'
  if (stock <= 5) return '⚠️ Stock bajo'
  return '✅ En stock'
}

export default function Products() {
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editingProduct, setEditingProduct] = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleting, setDeleting] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const { register, handleSubmit, reset, setValue, watch, formState: { errors } } = useForm()
  const imageUrl = watch('image_url')

  const load = () => {
    setLoading(true)
    getProducts()
      .then((r) => setProducts(r.data))
      .catch(() => toast.error('Error cargando productos'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const filtered = useMemo(() => {
    if (!search) return products
    return products.filter((p) =>
      p.name.toLowerCase().includes(search.toLowerCase())
    )
  }, [products, search])

  const openCreate = () => {
    setEditingProduct(null)
    reset({ name: '', description: '', price: '', stock: '', image_url: '' })
    setModalOpen(true)
  }

  const openEdit = (product) => {
    setEditingProduct(product)
    reset({
      name: product.name,
      description: product.description || '',
      price: (product.price / 100).toFixed(2),
      stock: product.stock,
      image_url: product.image_url || '',
    })
    setModalOpen(true)
  }

  const onSubmit = async (data) => {
    setSubmitting(true)
    const payload = {
      name: data.name,
      description: data.description || '',
      price: Math.round(parseFloat(data.price) * 100),
      stock: parseInt(data.stock, 10),
      image_url: data.image_url || null,
    }
    try {
      if (editingProduct) {
        await updateProduct(editingProduct.id, payload)
        toast.success('Producto actualizado')
      } else {
        await createProduct(payload)
        toast.success('Producto creado')
      }
      setModalOpen(false)
      load()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error guardando producto')
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await deleteProduct(deleteTarget.id)
      toast.success('Producto eliminado')
      setDeleteTarget(null)
      load()
    } catch {
      toast.error('Error eliminando producto')
    } finally {
      setDeleting(false)
    }
  }

  if (loading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {[...Array(6)].map((_, i) => <SkeletonCard key={i} />)}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-5">
      {/* Header */}
      <div className="flex flex-wrap gap-3 items-center justify-between">
        <div className="relative flex-1 min-w-[200px]">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Buscar producto..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-white border border-slate-300 rounded-xl pl-9 pr-4 py-2 text-sm text-slate-800 placeholder-slate-400 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 transition-all"
          />
        </div>
        <Button onClick={openCreate}>
          <Plus size={16} /> Nuevo producto
        </Button>
      </div>

      {/* Grid */}
      {filtered.length === 0 ? (
        <EmptyState
          icon={Package}
          title="Sin productos"
          description="Crea tu primer producto para empezar"
          action={<Button onClick={openCreate}><Plus size={16} /> Crear producto</Button>}
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map((product) => (
            <div
              key={product.id}
              className="bg-white border border-slate-200 rounded-xl shadow-sm flex flex-col gap-3 overflow-hidden hover:shadow-md transition-shadow duration-200"
            >
              {/* Image */}
              <div className="w-full h-40 bg-slate-100 flex items-center justify-center overflow-hidden">
                {product.image_url ? (
                  <img
                    src={product.image_url}
                    alt={product.name}
                    className="w-full h-full object-cover"
                    onError={(e) => { e.target.style.display = 'none' }}
                  />
                ) : (
                  <Package size={40} className="text-slate-300" />
                )}
              </div>

              <div className="p-4 flex flex-col gap-2">
                <h3 className="text-slate-800 font-semibold text-sm leading-snug">{product.name}</h3>
                {product.description && (
                  <p className="text-slate-400 text-xs line-clamp-2">{product.description}</p>
                )}
                <div className="flex items-center justify-between mt-1">
                  <span className="text-slate-800 font-bold">
                    S/ {(product.price / 100).toFixed(2)}
                  </span>
                  <Badge variant={stockVariant(product.stock)}>
                    {stockLabel(product.stock)}
                  </Badge>
                </div>
                <p className="text-slate-400 text-xs">Stock: {product.stock} unidades</p>

                <div className="flex gap-2 mt-1">
                  <Button
                    variant="secondary"
                    onClick={() => openEdit(product)}
                    className="flex-1 !text-xs !py-1.5"
                  >
                    <Pencil size={12} /> Editar
                  </Button>
                  <Button
                    variant="danger"
                    onClick={() => setDeleteTarget(product)}
                    className="!text-xs !py-1.5"
                  >
                    <Trash2 size={12} />
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create/Edit Modal */}
      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editingProduct ? 'Editar producto' : 'Nuevo producto'}
      >
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <Input
            label="Nombre *"
            placeholder="Ej: Crema hidratante"
            {...register('name', { required: 'El nombre es requerido', maxLength: 200 })}
            error={errors.name?.message}
          />

          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium text-slate-700">Descripción</label>
            <textarea
              placeholder="Descripción del producto..."
              rows={3}
              className="w-full bg-white border border-slate-300 rounded-xl px-4 py-2.5 text-slate-800 placeholder-slate-400 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 transition-all resize-none text-sm"
              {...register('description', { maxLength: 2000 })}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Input
              label="Precio (S/)"
              type="number"
              step="0.01"
              min="0"
              placeholder="0.00"
              {...register('price', { required: 'El precio es requerido', min: 0 })}
              error={errors.price?.message}
            />
            <Input
              label="Stock"
              type="number"
              min="0"
              placeholder="0"
              {...register('stock', { required: 'El stock es requerido', min: 0 })}
              error={errors.stock?.message}
            />
          </div>

          <Input
            label="URL de imagen (opcional)"
            placeholder="https://..."
            {...register('image_url')}
          />

          {imageUrl && (
            <div className="w-full h-28 rounded-xl overflow-hidden bg-slate-100 border border-slate-200">
              <img
                src={imageUrl}
                alt="Preview"
                className="w-full h-full object-cover"
                onError={(e) => { e.target.style.display = 'none' }}
              />
            </div>
          )}

          <div className="flex gap-3 justify-end pt-2">
            <Button variant="secondary" type="button" onClick={() => setModalOpen(false)}>
              Cancelar
            </Button>
            <Button type="submit" loading={submitting}>
              {editingProduct ? 'Guardar cambios' : 'Crear producto'}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Delete confirm */}
      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleDelete}
        loading={deleting}
        title="Eliminar producto"
        message={`¿Eliminar "${deleteTarget?.name}"? Esta acción no se puede deshacer.`}
      />
    </div>
  )
}
