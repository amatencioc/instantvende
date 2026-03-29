import client from './client.js'

export const getOrders = () => client.get('/api/orders')

export const getOrder = (id) => client.get(`/api/orders/${id}`)

export const updateOrderStatus = (id, status) =>
  client.patch(`/api/orders/${id}/status`, { status })
