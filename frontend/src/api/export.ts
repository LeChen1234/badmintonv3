import request from './request'
import type { ExportRequest, ExportResponse } from '@/types'

export function exportProject(projectId: number, data: ExportRequest) {
  return request.post<ExportResponse>(`/export/${projectId}`, data)
}

export function downloadExport(projectId: number, data: ExportRequest) {
  return request.post(`/export/${projectId}/download`, data, { responseType: 'blob' })
}
