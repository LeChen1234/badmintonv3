import { defineStore } from 'pinia'
import { ref } from 'vue'
import { authApi } from '@/api'
import router from '@/router'

interface UserInfo {
  id: number
  username: string
  role: string
  display_name: string
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref<UserInfo | null>(null)

  async function login(username: string, password: string) {
    const res = await authApi.login(username, password)
    token.value = res.data.access_token
    localStorage.setItem('token', token.value)
    await fetchUser()
    router.push('/dashboard')
  }

  async function fetchUser() {
    const res = await authApi.me()
    user.value = res.data
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
    router.push('/login')
  }

  return { token, user, login, fetchUser, logout }
})
