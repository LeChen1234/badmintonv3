import request from './request'
import type { Project, ProjectCreate } from '@/types'

export function getProjects() {
  return request.get<Project[]>('/projects')
}

export function getProject(id: number) {
  return request.get<Project>(`/projects/${id}`)
}

export function createProject(data: ProjectCreate) {
  return request.post<Project>('/projects', data)
}

export function deleteProject(id: number) {
  return request.delete(`/projects/${id}`)
}
