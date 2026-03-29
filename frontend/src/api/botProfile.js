import client from './client.js'

export const getBotProfile = () => client.get('/api/bot-profile')

export const updateBotProfile = (data) => client.put('/api/bot-profile', data)

export const resetBotProfile = () => client.post('/api/bot-profile/reset')
