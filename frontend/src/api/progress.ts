import request from './request'
import type { OverviewProgress } from '@/types'

export function getOverviewProgress() {
  return request.get<OverviewProgress>('/progress/overview')
}
