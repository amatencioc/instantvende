import axios from 'axios'
import useAuthStore from '../store/useAuthStore.js'
import toast from 'react-hot-toast'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  timeout: 30000,
})

client.interceptors.request.use((config) => {
  const apiKey = useAuthStore.getState().apiKey
  if (apiKey) {
    config.headers['X-API-Key'] = apiKey
  }
  return config
})

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 || error.response?.status === 403) {
      useAuthStore.getState().logout()
      window.location.href = '/login'
    } else if (error.response?.status >= 500) {
      toast.error('Error del servidor. Intenta de nuevo.')
    }
    return Promise.reject(error)
  }
)

export default client
