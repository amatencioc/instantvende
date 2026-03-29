import client from './client.js'

export const getProducts = () => client.get('/api/products')

export const createProduct = (data) => client.post('/api/products', data)

export const updateProduct = (id, data) => client.put(`/api/products/${id}`, data)

export const deleteProduct = (id) => client.delete(`/api/products/${id}`)
