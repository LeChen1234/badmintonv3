import request from './request'
import type { User, UserCreate, UserUpdate } from '@/types'

export function getUsers(params?: { role?: string; is_active?: boolean }) {
  return request.get<User[]>('/users', { params })
}

export function getUser(id: number) {
  return request.get<User>(`/users/${id}`)
}

export function createUser(data: UserCreate) {
  return request.post<User>('/users', data)
}

export function updateUser(id: number, data: UserUpdate) {
  return request.put<User>(`/users/${id}`, data)
}

export function deleteUser(id: number) {
  return request.delete(`/users/${id}`)
}
