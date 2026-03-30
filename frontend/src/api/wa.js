import client from './client.js'

export const getWaStatus = () => client.get('/api/wa/status')
export const disconnectWa = () => client.post('/api/wa/disconnect')
