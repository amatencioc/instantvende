import client from './client.js'

export const registerVendor = (data) => client.post('/api/vendors/register', data)
export const loginVendor = (data) => client.post('/api/vendors/login', data)
export const getVendors = () => client.get('/api/vendors/me')
