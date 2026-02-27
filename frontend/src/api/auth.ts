import request from './request'
import type { LoginRequest, Token, User } from '@/types'

export function login(data: LoginRequest) {
  return request.post<Token>('/auth/login', data)
}

export function getCurrentUser() {
  return request.get<User>('/auth/me')
}
