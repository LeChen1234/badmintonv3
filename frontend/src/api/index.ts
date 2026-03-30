import request from './request'

export const configApi = {
  getConfig: () => request.get<{ allow_public_register: boolean; ml_backend_enabled: boolean }>('/config'),
}

export const authApi = {
  login: (username: string, password: string) =>
    request.post('/auth/login', { username, password }),
  register: (data: { username: string; password: string; display_name: string }) =>
    request.post('/auth/register', data),
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
  delete: (id: number) => request.delete(`/tasks/${id}`),
  assign: (id: number, userId: number) => request.post(`/tasks/${id}/assign`, null, { params: { user_id: userId } }),
  triggerMl: (id: number) => request.post(`/tasks/${id}/trigger-ml`),
  upload: (batchId: number, formData: FormData) =>
    request.post(`/tasks/${batchId}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300000,
    }),
  getUploadedChunks: (batchId: number, uploadId: string) =>
    request.get<{ uploaded_chunks: number[] }>(`/tasks/${batchId}/upload/${uploadId}`),
  getMediaProcessStatus: (batchId: number) => request.get(`/tasks/${batchId}/media-process-status`),
  updateMetadata: (
    batchId: number,
    data: {
      match_date?: string;
      match_name?: string;
      players?: Array<{ id?: number; uuid?: string; name?: string; gender?: 'male' | 'female'; age?: number; height_cm?: number }>;
    },
  ) =>
    request.put(`/tasks/${batchId}/metadata`, data),
  confirmMetadata: (batchId: number) => request.post(`/tasks/${batchId}/metadata/confirm`),
  getFrames: (batchId: number) => request.get(`/tasks/${batchId}/frames`),
  getFrameImageUrl: (batchId: number, frameIndex: number) =>
    `/tasks/${batchId}/frame/${frameIndex}/image`,
  /** 算法辅助：当前帧多人姿态估计，返回 persons 数组，每人一组 25 关键点 */
  predictKeypoints: (batchId: number, frameIndex: number) =>
    request.get<{
      persons: { keypoints: { name: string; x: number; y: number; visibility: number }[] }[];
    }>(`/tasks/${batchId}/frame/${frameIndex}/predict-keypoints`, { timeout: 60000 }),
}

export const annotationApi = {
  list: (taskBatchId: number, params?: any) =>
    request.get('/annotations', { params: { task_batch_id: taskBatchId, ...params } }),
  create: (data: any) => request.post('/annotations', data),
  batchCreate: (data: any) => request.post('/annotations/batch', data),
  update: (id: number, data: any) => request.put(`/annotations/${id}`, data),
  delete: (id: number) => request.delete(`/annotations/${id}`),
  submit: (taskBatchId: number) => request.post('/annotations/submit', null, { params: { task_batch_id: taskBatchId } }),
  confirm: (data: any) => request.post('/annotations/confirm', data),
  triggerMl: (taskBatchId: number) => request.post(`/annotations/trigger-ml/${taskBatchId}`),
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
  download: (projectId: number, filename: string) =>
    request.get(`/export/${projectId}/download`, { params: { filename }, responseType: 'blob' }),
  confirmedCount: (projectId: number) => request.get(`/export/${projectId}/confirmed-count`),
}
