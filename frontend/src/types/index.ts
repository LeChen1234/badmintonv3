export enum UserRole {
  ADMIN = 'admin',
  EXPERT = 'expert',
  LEADER = 'leader',
  STUDENT = 'student',
}

export const UserRoleLabel: Record<UserRole, string> = {
  [UserRole.ADMIN]: '系统管理员',
  [UserRole.EXPERT]: '标注专家',
  [UserRole.LEADER]: '标注组长',
  [UserRole.STUDENT]: '学生标注员',
}

export enum TaskStatus {
  PENDING = 'pending',
  ANNOTATING = 'annotating',
  SELF_REVIEW = 'self_review',
  LEADER_REVIEW = 'leader_review',
  EXPERT_REVIEW = 'expert_review',
  LOCKED = 'locked',
}

export const TaskStatusLabel: Record<TaskStatus, string> = {
  [TaskStatus.PENDING]: '待分配',
  [TaskStatus.ANNOTATING]: '标注中',
  [TaskStatus.SELF_REVIEW]: '自核中',
  [TaskStatus.LEADER_REVIEW]: '组长核对',
  [TaskStatus.EXPERT_REVIEW]: '专家审核',
  [TaskStatus.LOCKED]: '已锁定',
}

export const TaskStatusType: Record<TaskStatus, string> = {
  [TaskStatus.PENDING]: 'info',
  [TaskStatus.ANNOTATING]: 'primary',
  [TaskStatus.SELF_REVIEW]: 'warning',
  [TaskStatus.LEADER_REVIEW]: 'warning',
  [TaskStatus.EXPERT_REVIEW]: 'warning',
  [TaskStatus.LOCKED]: 'success',
}

export enum ReviewLevel {
  SELF = 'self',
  LEADER = 'leader',
  EXPERT = 'expert',
}

export const ReviewLevelLabel: Record<ReviewLevel, string> = {
  [ReviewLevel.SELF]: '自核',
  [ReviewLevel.LEADER]: '组长核对',
  [ReviewLevel.EXPERT]: '专家审核',
}

export enum ReviewResult {
  PASS = 'pass',
  REJECT = 'reject',
}

export interface LoginRequest {
  username: string
  password: string
}

export interface Token {
  access_token: string
  token_type: string
}

export interface TokenPayload {
  sub: number
  role: string
  username: string
}

export interface User {
  id: number
  username: string
  role: UserRole
  display_name: string
  ls_user_id: number | null
  is_active: boolean
  created_at: string
}

export interface UserCreate {
  username: string
  password: string
  role: UserRole
  display_name: string
  ls_user_id?: number | null
}

export interface UserUpdate {
  role?: UserRole
  display_name?: string
  is_active?: boolean
  ls_user_id?: number | null
}

export interface Project {
  id: number
  name: string
  description: string | null
  ls_project_id: number | null
  created_by: number
  created_at: string
}

export interface ProjectCreate {
  name: string
  description?: string
  template_type?: string
}

export interface TaskBatch {
  id: number
  project_id: number
  name: string
  action_category: string | null
  assigned_to: number | null
  status: TaskStatus
  frame_start: number | null
  frame_end: number | null
  total_frames: number
  completed_frames: number
  deadline: string | null
  created_at: string
}

export interface TaskBatchCreate {
  project_id: number
  name: string
  action_category?: string
  assigned_to?: number
  frame_start?: number
  frame_end?: number
  total_frames?: number
  deadline?: string
}

export interface TaskBatchUpdate {
  assigned_to?: number
  status?: TaskStatus
  completed_frames?: number
  deadline?: string
}

export interface ReviewRecord {
  id: number
  task_batch_id: number
  reviewer_id: number
  review_level: ReviewLevel
  result: ReviewResult
  comment: string | null
  created_at: string
}

export interface ReviewSubmit {
  review_level: ReviewLevel
  result: ReviewResult
  comment?: string
}

export interface ProjectProgress {
  project_id: number
  project_name: string
  total_batches: number
  status_counts: Record<string, number>
  total_frames: number
  completed_frames: number
  completion_rate: number
}

export interface AnnotatorProgress {
  user_id: number
  display_name: string
  assigned_batches: number
  completed_batches: number
  total_frames: number
  completed_frames: number
}

export interface OverviewProgress {
  total_projects: number
  total_batches: number
  total_frames: number
  completed_frames: number
  overall_rate: number
  projects: ProjectProgress[]
  annotators: AnnotatorProgress[]
}

export interface ExportRequest {
  format: string
  include_predictions?: boolean
  only_reviewed?: boolean
}

export interface ExportResponse {
  filename: string
  format: string
  record_count: number
  download_url: string | null
}
