import request from './request'

export const configApi = {
  getConfig: () => request.get<{ allow_public_register: boolean; ml_backend_enabled: boolean }>('/config'),
}

export const authApi = {
  login: (username: string, password: string) =>
    request.post('/auth/login', { username, password }),
  register: (data: {
    username: string
    password: string
    display_name: string
  }) =>
    request.post('/auth/register', data),
  me: () => request.get('/auth/me'),
  changePassword: (data: { old_password: string; new_password: string; confirm_password: string }) =>
    request.post('/auth/change-password', data),
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
      match_format?: 'singles' | 'doubles' | null;
      capture_metadata?: {
        capture_mode: 'competition' | 'controlled_training';
        annotation_goal: 'action_sequence' | 'technique_quality';
        camera_view?: 'front' | 'rear' | 'left' | 'right' | 'front_left' | 'front_right' | 'rear_left' | 'rear_right' | 'other';
        camera_height: 'low' | 'eye_level' | 'high' | 'unknown';
        capture_session_id?: string;
        target_action?: string;
        marker_protocol: 'video_landmarks' | 'physical_markers';
        recording_notes?: string;
        source_reference?: string;
        source_platform?: string;
        device_model?: string;
        recording_fps?: number;
        recording_design?: 'natural_training' | 'prescribed_standard' | 'prescribed_variation' | 'mixed';
        feed_method?: 'coach' | 'machine' | 'self' | 'rally' | 'unknown';
        repetition_group_id?: string;
        bridge_view_id?: string;
        intended_variation?: string;
      };
      players?: Array<{ id?: number; uuid?: string; name?: string; subject_code?: string; gender?: 'male' | 'female'; age?: number; height_cm?: number; racket_hand?: 'left' | 'right' }>;
    },
  ) =>
    request.put(`/tasks/${batchId}/metadata`, data),
  confirmMetadata: (batchId: number) => request.post(`/tasks/${batchId}/metadata/confirm`),
  getFrames: (batchId: number) => request.get(`/tasks/${batchId}/frames`),
  getFramePriorities: (batchId: number) => request.get(`/tasks/${batchId}/frame-priorities`),
  getTeacherSurrogateQuality: (batchId: number) => request.get(`/tasks/${batchId}/teacher-surrogate-quality`),
  getDataValueReport: (batchId: number) => request.get(`/tasks/${batchId}/data-value-report`),
  reviewFrame: (batchId: number, frameIndex: number, data: { is_rejected: boolean; reason?: string }) =>
    request.put(`/tasks/${batchId}/frame/${frameIndex}/review`, data),
  getFrameImageUrl: (batchId: number, frameIndex: number) =>
    `/tasks/${batchId}/frame/${frameIndex}/image`,
  getFrameImageBlob: (batchId: number, frameIndex: number) =>
    request.get(`/tasks/${batchId}/frame/${frameIndex}/image`, { responseType: 'blob' }),
  /** 多人姿态预标注及质量评估结果。 */
  predictKeypoints: (batchId: number, frameIndex: number, box: { x: number; y: number; w: number; h: number }) =>
    request.get<{
        persons: {
          keypoints: { name: string; x: number; y: number; visibility: number }[]
          bbox: [number, number, number, number]
          detection_confidence: number
          visible_keypoints: number
          source: 'yolo-full' | 'yolo-tile' | string
          assist?: {
          confidence: number
          uncertainty: number
          review_priority: number
          suggested_phase: string | null
          suggested_quality: string | null
          phase_probabilities: Record<string, number>
          features: Record<string, number | string>
          reasons: string[]
        }
      }[]
      algorithm_version: string
    }>(`/tasks/${batchId}/frame/${frameIndex}/predict-keypoints`, {
      params: { box_x: box.x, box_y: box.y, box_w: box.w, box_h: box.h },
      timeout: 60000,
    }),
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

export const segmentApi = {
  list: (taskBatchId: number, params?: any) =>
    request.get('/segments', { params: { task_batch_id: taskBatchId, ...params } }),
  create: (data: {
    task_batch_id: number
    selected_player_id: number
    start_frame: number
    end_frame: number
    action_type: string
    action_phase?: string
    context?: Record<string, unknown>
    execution?: Record<string, unknown>
    outcome?: Record<string, unknown>
    evidence?: Record<string, unknown>
    notes?: string
  }) => request.post('/segments', data),
  update: (id: number, data: any) => request.put(`/segments/${id}`, data),
  delete: (id: number) => request.delete(`/segments/${id}`),
  submit: (taskBatchId: number) =>
    request.post('/segments/submit', null, { params: { task_batch_id: taskBatchId } }),
  confirm: (segmentIds: number[]) =>
    request.post('/segments/confirm', { segment_ids: segmentIds }),
}

export const reviewApi = {
  expertQueue: (taskBatchId?: number) => request.get('/review/expert-queue', { params: { task_batch_id: taskBatchId } }),
  submit: (taskId: number, data?: any) => request.post(`/review/${taskId}/submit`, data || {}),
  approve: (taskId: number, data: any) => request.post(`/review/${taskId}/approve`, data),
  reject: (taskId: number, data: any) => request.post(`/review/${taskId}/reject`, data),
  history: (taskId: number) => request.get(`/review/${taskId}/history`),
  agreement: (taskId: number) => request.get(`/review/${taskId}/agreement`),
  disagreements: (taskId: number) => request.get(`/review/${taskId}/disagreements`),
  adjudicate: (taskId: number, data: any) => request.post(`/review/${taskId}/adjudicate`, data),
}

export const progressApi = {
  overview: () => request.get('/progress/overview'),
}

export const researchApi = {
  rounds: (projectId: number) => request.get(`/research/${projectId}/rounds`),
  createRound: (projectId: number, data: any) => request.post(`/research/${projectId}/rounds`, data),
}

export const exportApi = {
  export: (projectId: number, data: any) => request.post(`/export/${projectId}`, data),
  download: (projectId: number, filename: string) =>
    request.get(`/export/${projectId}/download`, { params: { filename }, responseType: 'blob' }),
  confirmedCount: (projectId: number) => request.get(`/export/${projectId}/confirmed-count`),
}
