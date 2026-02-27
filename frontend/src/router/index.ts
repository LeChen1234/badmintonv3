import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

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
      { path: '', redirect: '/dashboard' },
      { path: 'dashboard', name: 'Dashboard', component: () => import('@/views/DashboardView.vue') },
      { path: 'users', name: 'Users', component: () => import('@/views/UserManageView.vue') },
      { path: 'tasks', name: 'Tasks', component: () => import('@/views/TaskManageView.vue') },
      { path: 'progress', name: 'Progress', component: () => import('@/views/ProgressView.vue') },
      { path: 'review', name: 'Review', component: () => import('@/views/ReviewView.vue') },
      { path: 'export', name: 'Export', component: () => import('@/views/ExportView.vue') },
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
  } else {
    next()
  }
})

export default router
