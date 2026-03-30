import client from './client.js'

export const getConversations = () => client.get('/api/conversations')

export const getConversationMessages = (id) =>
  client.get(`/api/conversations/${id}/messages`)

export const toggleBot = (id, enabled) =>
  client.patch(`/api/conversations/${id}/toggle-bot`, null, { params: { enabled } })

export const sendMessage = (id, message) =>
  client.post(`/api/conversations/${id}/send-message`, { message })

export const deleteConversation = (id) =>
  client.delete(`/api/conversations/${id}`)
