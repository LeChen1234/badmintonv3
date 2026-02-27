import request from './request'

export const authApi = {
  login: (username: string, password: string) =>
    request.post('/auth/login', { username, password }),
  me: () => request.get('/auth/me'),
}

export const userApi = {
  list: (params?: any) => request.get('/users', { params }),
  create: (data: any) => request.post('/users', data),
  get: (id: number) => request.get(`/users/${id}`),
  update: (id: number, data: any) => request.put(`/users/${id}`, data),
  delete: (id: number) => request.delete(`/users/${id}`),
}

export const projectApi = {
  list: (params?: any) => request.get('/projects', { params }),
  create: (data: any) => request.post('/projects', data),
  get: (id: number) => request.get(`/projects/${id}`),
  update: (id: number, data: any) => request.put(`/projects/${id}`, data),
  delete: (id: number) => request.delete(`/projects/${id}`),
}

export const taskApi = {
  list: (params?: any) => request.get('/tasks', { params }),
  create: (data: any) => request.post('/tasks/batch', data),
  get: (id: number) => request.get(`/tasks/${id}`),
  update: (id: number, data: any) => request.put(`/tasks/${id}`, data),
  assign: (id: number, userId: number) => request.post(`/tasks/${id}/assign`, null, { params: { user_id: userId } }),
  triggerMl: (id: number) => request.post(`/tasks/${id}/trigger-ml`),
}

export const reviewApi = {
  submit: (taskId: number, data?: any) => request.post(`/review/${taskId}/submit`, data || {}),
  approve: (taskId: number, data: any) => request.post(`/review/${taskId}/approve`, data),
  reject: (taskId: number, data: any) => request.post(`/review/${taskId}/reject`, data),
  history: (taskId: number) => request.get(`/review/${taskId}/history`),
}

export const progressApi = {
  overview: () => request.get('/progress/overview'),
}

export const exportApi = {
  export: (projectId: number, data: any) => request.post(`/export/${projectId}`, data),
  download: (projectId: number, data: any) => request.post(`/export/${projectId}/download`, data, { responseType: 'blob' }),
}
