import request from './request'
import type { ReviewRecord } from '@/types'

export function getReviews(taskId: number) {
  return request.get<ReviewRecord[]>(`/review/${taskId}/history`)
}

export function submitReview(taskId: number, comment?: string) {
  return request.post(`/review/${taskId}/submit`, { comment })
}

export function approveReview(taskId: number, comment?: string) {
  return request.post(`/review/${taskId}/approve`, { comment })
}

export function rejectReview(taskId: number, comment?: string) {
  return request.post(`/review/${taskId}/reject`, { comment })
}
