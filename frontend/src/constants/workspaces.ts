export type WorkspaceRole = 'student' | 'leader' | 'expert' | 'admin' | 'super_admin'

export const WORKSPACE_ORDER: WorkspaceRole[] = [
  'student',
  'leader',
  'expert',
  'admin',
  'super_admin',
]

export const WORKSPACE_LABELS: Record<WorkspaceRole, string> = {
  student: '学生标注',
  leader: '组长质检',
  expert: '体育专家',
  admin: '系统管理',
  super_admin: '超级管理',
}

export const WORKSPACE_PATHS: Record<WorkspaceRole, string> = {
  student: '/workspace/student',
  leader: '/workspace/leader',
  expert: '/workspace/expert',
  admin: '/workspace/admin',
  super_admin: '/workspace/super-admin',
}

export function isWorkspaceRole(value: unknown): value is WorkspaceRole {
  return typeof value === 'string' && WORKSPACE_ORDER.includes(value as WorkspaceRole)
}

export function workspaceLevel(role: WorkspaceRole): number {
  return WORKSPACE_ORDER.indexOf(role)
}

export function availableWorkspaces(actualRole: string | null | undefined): WorkspaceRole[] {
  if (!isWorkspaceRole(actualRole)) return []
  return WORKSPACE_ORDER.slice(0, workspaceLevel(actualRole) + 1)
}

export function canOpenWorkspace(actualRole: string | null | undefined, target: WorkspaceRole): boolean {
  return availableWorkspaces(actualRole).includes(target)
}

export function defaultWorkspace(actualRole: string | null | undefined): WorkspaceRole {
  return isWorkspaceRole(actualRole) ? actualRole : 'student'
}

export function workspaceAtLeast(current: WorkspaceRole, required: WorkspaceRole): boolean {
  return workspaceLevel(current) >= workspaceLevel(required)
}
