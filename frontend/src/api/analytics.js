import client from './client.js'

export const getAnalytics = () => client.get('/api/analytics')
