import axios from 'axios'
import { ElMessage } from 'element-plus'

export interface ApiResult<T> {
  code: number
  msg: string
  data: T
}

const http = axios.create({ baseURL: '', timeout: 120000 })

http.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

http.interceptors.response.use(
  (response) => {
    const body = response.data as ApiResult<unknown>
    if (body.code !== 0) {
      ElMessage.error(body.msg || '请求失败')
      return Promise.reject(new Error(body.msg))
    }
    return response
  },
  (error) => {
    const body = error.response?.data as ApiResult<unknown> | undefined
    const msg = body?.msg || error.message || '网络错误'
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    ElMessage.error(msg)
    return Promise.reject(error)
  },
)

// 统一解包 Result，业务代码只拿 data
export async function get<T>(url: string, params?: object): Promise<T> {
  const resp = await http.get<ApiResult<T>>(url, { params })
  return resp.data.data
}

export async function post<T>(url: string, data?: object): Promise<T> {
  const resp = await http.post<ApiResult<T>>(url, data)
  return resp.data.data
}