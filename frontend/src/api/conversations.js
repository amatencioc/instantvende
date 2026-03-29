import client from './client.js'

export const getConversations = () => client.get('/api/conversations')

export const getConversationMessages = (id) =>
  client.get(`/api/conversations/${id}/messages`)

export const toggleBot = (id, enabled) =>
  client.patch(`/api/conversations/${id}/toggle-bot?enabled=${enabled}`)
