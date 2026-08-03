import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import {
  WORKSPACE_PATHS,
  isWorkspaceRole,
  workspaceLevel,
  type WorkspaceRole,
} from '@/constants/workspaces'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    component: () => import('@/views/LayoutView.vue'),
    meta: { requiresAuth: true },
    children: [
      { path: '', redirect: '/workspace' },
      { path: 'workspace', name: 'Workspace', component: () => import('@/views/workspaces/WorkspaceRedirectView.vue') },
      { path: 'workspace/student', name: 'StudentWorkspace', component: () => import('@/views/workspaces/StudentWorkspaceView.vue') },
      { path: 'workspace/leader', name: 'LeaderWorkspace', component: () => import('@/views/workspaces/LeaderWorkspaceView.vue') },
      { path: 'workspace/expert', name: 'ExpertWorkspace', component: () => import('@/views/workspaces/ExpertWorkspaceView.vue') },
      { path: 'workspace/admin', name: 'AdminWorkspace', component: () => import('@/views/workspaces/AdminWorkspaceView.vue') },
      { path: 'workspace/super-admin', name: 'SuperAdminWorkspace', component: () => import('@/views/workspaces/SuperAdminWorkspaceView.vue') },
      { path: 'dashboard', name: 'Dashboard', component: () => import('@/views/DashboardView.vue'), meta: { minWorkspaceRole: 'student' } },
      { path: 'projects', name: 'Projects', component: () => import('@/views/ProjectManageView.vue'), meta: { minWorkspaceRole: 'expert' } },
      { path: 'users', name: 'Users', component: () => import('@/views/UserManageView.vue'), meta: { minWorkspaceRole: 'admin' } },
      { path: 'tasks', name: 'Tasks', component: () => import('@/views/TaskManageView.vue'), meta: { minWorkspaceRole: 'student' } },
      { path: 'progress', name: 'Progress', component: () => import('@/views/ProgressView.vue'), meta: { minWorkspaceRole: 'leader' } },
      { path: 'review', name: 'Review', component: () => import('@/views/ReviewView.vue'), meta: { minWorkspaceRole: 'leader' } },
      { path: 'export', name: 'Export', component: () => import('@/views/ExportView.vue'), meta: { minWorkspaceRole: 'super_admin' } },
      { path: 'research', name: 'Research', component: () => import('@/views/ResearchView.vue'), meta: { minWorkspaceRole: 'leader' } },
      { path: 'guide', name: 'Guide', component: () => import('@/views/GuideView.vue'), meta: { minWorkspaceRole: 'student' } },
      { path: 'annotate/:batchId', name: 'Annotate', component: () => import('@/views/AnnotationView.vue'), meta: { minWorkspaceRole: 'student' } },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('token')
  if (to.meta.requiresAuth !== false && !token) {
    next('/login')
    return
  }
  const minimum = to.meta.minWorkspaceRole as WorkspaceRole | undefined
  const savedWorkspace = localStorage.getItem('workspace_role')
  const currentWorkspace: WorkspaceRole = isWorkspaceRole(savedWorkspace) ? savedWorkspace : 'student'
  if (minimum && workspaceLevel(currentWorkspace) < workspaceLevel(minimum)) {
    next(WORKSPACE_PATHS[currentWorkspace])
    return
  }
  next()
})

export default router
