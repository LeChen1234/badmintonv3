import request from './request'
import type { TaskBatch, TaskBatchCreate, TaskBatchUpdate } from '@/types'

export function getTaskBatches(params?: { project_id?: number; assigned_to?: number; status?: string }) {
  return request.get<TaskBatch[]>('/tasks', { params })
}

export function getTaskBatch(id: number) {
  return request.get<TaskBatch>(`/tasks/${id}`)
}

export function createTaskBatch(data: TaskBatchCreate) {
  return request.post<TaskBatch>('/tasks/batch', data)
}

export function updateTaskBatch(id: number, data: TaskBatchUpdate) {
  return request.put<TaskBatch>(`/tasks/${id}`, data)
}

export function assignTask(batchId: number, userId: number) {
  return request.post(`/tasks/${batchId}/assign`, null, { params: { user_id: userId } })
}

export function triggerML(taskId: number) {
  return request.post(`/tasks/${taskId}/trigger-ml`)
}
