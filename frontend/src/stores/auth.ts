import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api'
import router from '@/router'
import {
  WORKSPACE_PATHS,
  availableWorkspaces,
  defaultWorkspace,
  isWorkspaceRole,
  type WorkspaceRole,
} from '@/constants/workspaces'

interface UserInfo {
  id: number
  username: string
  role: string
  display_name: string
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref<UserInfo | null>(null)
  const savedWorkspace = localStorage.getItem('workspace_role')
  const workspaceRole = ref<WorkspaceRole>(isWorkspaceRole(savedWorkspace) ? savedWorkspace : 'student')

  const displayName = computed(() => user.value?.display_name || '用户')
  const role = computed(() => user.value?.role || null)
  const availableWorkspaceRoles = computed(() => availableWorkspaces(user.value?.role))

  function hasRole(...roles: string[]): boolean {
    return !!user.value && roles.includes(user.value.role)
  }

  async function login(username: string, password: string) {
    const res = await authApi.login(username, password)
    token.value = res.data.access_token
    localStorage.setItem('token', token.value)
    await fetchUser()
    router.push(WORKSPACE_PATHS[workspaceRole.value])
  }

  async function fetchUser() {
    const res = await authApi.me()
    user.value = res.data
    normalizeWorkspaceRole()
  }

  function normalizeWorkspaceRole() {
    const allowed = availableWorkspaces(user.value?.role)
    const hasSavedPreference = isWorkspaceRole(localStorage.getItem('workspace_role'))
    if (!hasSavedPreference || !allowed.includes(workspaceRole.value)) {
      workspaceRole.value = defaultWorkspace(user.value?.role)
    }
    localStorage.setItem('workspace_role', workspaceRole.value)
  }

  function setWorkspaceRole(nextRole: WorkspaceRole): boolean {
    if (!availableWorkspaceRoles.value.includes(nextRole)) return false
    workspaceRole.value = nextRole
    localStorage.setItem('workspace_role', nextRole)
    return true
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('workspace_role')
    workspaceRole.value = 'student'
    router.push('/login')
  }

  return {
    token,
    user,
    displayName,
    role,
    workspaceRole,
    availableWorkspaceRoles,
    hasRole,
    login,
    fetchUser,
    setWorkspaceRole,
    logout,
  }
})
