import { defineStore } from 'pinia'
import { post } from '../api/http'
import type { UserInfo } from '../api/types'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    user: JSON.parse(localStorage.getItem('user') || 'null') as UserInfo | null,
  }),
  actions: {
    async login(username: string, password: string) {
      const data = await post<{ token: string; user: UserInfo }>('/api/auth/login', {
        username,
        password,
      })
      this.token = data.token
      this.user = data.user
      localStorage.setItem('token', data.token)
      localStorage.setItem('user', JSON.stringify(data.user))
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('token')
      localStorage.removeItem('user')
    },
  },
})