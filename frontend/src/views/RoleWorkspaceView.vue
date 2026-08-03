<template>
  <div class="workspace-page">
    <el-card v-if="!authStore.user" shadow="never">
      <el-skeleton :rows="6" animated />
    </el-card>
    <el-alert
      v-else-if="!allowed"
      type="error"
      :closable="false"
      title="当前账号不能进入这个工作台，正在返回可用工作台。"
      show-icon
    />

    <template v-else>
      <el-card class="workspace-hero" shadow="never">
        <div class="workspace-hero-main">
          <div>
            <div class="workspace-eyebrow">分级权限工作台</div>
            <h1>{{ currentDefinition.label }}</h1>
            <p>{{ currentDefinition.description }}</p>
          </div>
          <div class="workspace-identity">
            <span>当前界面</span>
            <strong>{{ currentDefinition.shortLabel }}</strong>
            <small>实际账号：{{ actualRoleLabel }}</small>
          </div>
        </div>
        <el-alert
          v-if="role !== authStore.user?.role"
          type="info"
          :closable="false"
          title="这是下级工作台视图，只切换页面与菜单；所有操作仍按你的真实账号权限记录。"
          show-icon
        />
      </el-card>

      <el-card class="workspace-layers" shadow="never">
        <template #header>
          <div class="section-head">
            <strong>权限层级</strong>
            <span>高等级继承下级工作台入口，可随时手动切换</span>
          </div>
        </template>
        <div class="layer-track">
          <button
            v-for="(item, index) in definitions"
            :key="item.role"
            type="button"
            class="layer-node"
            :class="{
              active: item.role === role,
              accessible: accessibleRoles.includes(item.role),
              locked: !accessibleRoles.includes(item.role),
            }"
            :disabled="!accessibleRoles.includes(item.role)"
            @click="switchWorkspace(item.role)"
          >
            <span class="layer-index">{{ index + 1 }}</span>
            <span class="layer-copy"><strong>{{ item.shortLabel }}</strong><small>{{ item.scope }}</small></span>
          </button>
        </div>
      </el-card>

      <section v-for="layer in visibleLayers" :key="layer.role" class="capability-layer">
        <div class="capability-title">
          <el-tag :type="layer.role === role ? 'primary' : 'info'" effect="plain">第 {{ layer.level }} 层</el-tag>
          <div><h2>{{ layer.label }}</h2><p>{{ layer.scope }}</p></div>
        </div>
        <div class="workspace-grid">
          <button
            v-for="entry in layer.entries"
            :key="entry.path + entry.title"
            type="button"
            class="workspace-entry"
            @click="router.push(entry.path)"
          >
            <span class="entry-kicker">{{ entry.kicker }}</span>
            <strong>{{ entry.title }}</strong>
            <p>{{ entry.description }}</p>
            <span class="entry-action">进入 →</span>
          </button>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import {
  WORKSPACE_LABELS,
  WORKSPACE_ORDER,
  WORKSPACE_PATHS,
  canOpenWorkspace,
  type WorkspaceRole,
} from '@/constants/workspaces'

type WorkspaceEntry = { kicker: string; title: string; description: string; path: string }
type WorkspaceDefinition = {
  role: WorkspaceRole
  level: number
  shortLabel: string
  label: string
  description: string
  scope: string
  entries: WorkspaceEntry[]
}

const props = defineProps<{ role: WorkspaceRole }>()
const router = useRouter()
const authStore = useAuthStore()

const definitions: WorkspaceDefinition[] = [
  {
    role: 'student', level: 1, shortLabel: '学生', label: '学生标注工作台', scope: '领取任务、客观粗标、自核提交',
    description: '聚焦视频标注的最短路径，不显示审核、研究和系统配置。',
    entries: [
      { kicker: '主任务', title: '我的标注任务', description: '查看分配给自己的任务，继续逐帧或连续动作标注。', path: '/tasks' },
      { kicker: '进度', title: '个人总览', description: '查看当前任务、完成量和待处理状态。', path: '/dashboard' },
      { kicker: '帮助', title: '标注指南', description: '查看学生字段、画布操作与提交规则。', path: '/guide' },
    ],
  },
  {
    role: 'leader', level: 2, shortLabel: '组长', label: '组长质检工作台', scope: '继承学生层，并增加进度与组内复核',
    description: '在学生标注能力上增加进度监控、规范一致性检查和退回处理。',
    entries: [
      { kicker: '质检', title: '组长审核', description: '检查漏标、错人、边界框和规范一致性。', path: '/review' },
      { kicker: '监控', title: '团队进度', description: '查看人员进度和任务完成情况。', path: '/progress' },
      { kicker: '辅助', title: '数据研究概览', description: '查看主动学习与数据价值的辅助结果。', path: '/research' },
    ],
  },
  {
    role: 'expert', level: 3, shortLabel: '专家', label: '体育专家工作台', scope: '继承组长层，并增加专业判定与项目协议',
    description: '只处理动作阶段、质量、受迫性和接触技术等专业判断。',
    entries: [
      { kicker: '专业判定', title: '专家待办队列', description: '处理系统分流出的动作质量与接触技术字段。', path: '/review?panel=expert' },
      { kicker: '协议', title: '项目与采集协议', description: '维护项目范围、数据轨道与标注规范。', path: '/projects' },
      { kicker: '分析', title: '主动学习闭环', description: '查看模型不确定性与数据价值实验。', path: '/research' },
    ],
  },
  {
    role: 'admin', level: 4, shortLabel: '管理员', label: '系统管理员工作台', scope: '继承专家层，并增加人员和任务配置',
    description: '负责账号、项目、任务分配和系统运行配置，不包含最终数据发布。',
    entries: [
      { kicker: '人员', title: '用户与角色', description: '创建账号、调整角色和维护人员状态。', path: '/users' },
      { kicker: '配置', title: '项目管理', description: '创建项目并维护标注组织结构。', path: '/projects' },
      { kicker: '调度', title: '任务分配', description: '分配主标注员、复标员并检查任务状态。', path: '/tasks' },
    ],
  },
  {
    role: 'super_admin', level: 5, shortLabel: '超级管理员', label: '超级管理员工作台', scope: '继承全部层，并增加锁定、导出与最高权限',
    description: '负责最终数据锁定、版本化导出和不可逆管理操作。',
    entries: [
      { kicker: '发布', title: '数据集导出', description: '锁定审核完成的数据并生成版本化研究数据集。', path: '/export' },
      { kicker: '最高权限', title: '账号治理', description: '管理所有角色以及超级管理员级操作。', path: '/users' },
      { kicker: '全局', title: '系统总览', description: '查看全系统项目、任务和标注状态。', path: '/dashboard' },
    ],
  },
]

const currentDefinition = computed(() => definitions.find((item) => item.role === props.role) || definitions[0])
const accessibleRoles = computed(() => authStore.availableWorkspaceRoles)
const allowed = computed(() => canOpenWorkspace(authStore.user?.role, props.role))
const visibleLayers = computed(() => definitions.slice(0, WORKSPACE_ORDER.indexOf(props.role) + 1))
const actualRoleLabel = computed(() => WORKSPACE_LABELS[authStore.user?.role as WorkspaceRole] || '未知')

function switchWorkspace(nextRole: WorkspaceRole) {
  if (!authStore.setWorkspaceRole(nextRole)) {
    ElMessage.warning('当前账号不能进入该工作台')
    return
  }
  router.push(WORKSPACE_PATHS[nextRole])
}

function ensureAllowed() {
  if (!authStore.user || allowed.value) return
  const fallback = authStore.workspaceRole
  ElMessage.warning('已返回当前账号可用的工作台')
  router.replace(WORKSPACE_PATHS[fallback])
}

onMounted(async () => {
  if (!authStore.user) await authStore.fetchUser()
  if (allowed.value) authStore.setWorkspaceRole(props.role)
  ensureAllowed()
})

watch(() => props.role, () => {
  if (allowed.value) authStore.setWorkspaceRole(props.role)
  ensureAllowed()
})
</script>

<style scoped>
.workspace-page { max-width: 1240px; margin: 0 auto; }
.workspace-hero { border: none; background: linear-gradient(135deg, #eef6ff 0%, #f8fbff 58%, #f2f5ff 100%); }
.workspace-hero-main { display: flex; justify-content: space-between; align-items: center; gap: 28px; }
.workspace-eyebrow { color: #409eff; font-size: 13px; font-weight: 700; letter-spacing: .08em; }
.workspace-hero h1 { margin: 9px 0 8px; color: #1f2d3d; font-size: 30px; }
.workspace-hero p { margin: 0 0 14px; color: #606266; line-height: 1.7; }
.workspace-identity { min-width: 180px; padding: 18px; border: 1px solid #d9ecff; border-radius: 12px; background: rgba(255,255,255,.82); display: flex; flex-direction: column; gap: 5px; }
.workspace-identity span, .workspace-identity small { color: #909399; }
.workspace-identity strong { color: #303133; font-size: 20px; }
.workspace-layers { margin-top: 16px; }
.section-head { display: flex; justify-content: space-between; gap: 12px; align-items: center; }
.section-head span { color: #909399; font-size: 12px; }
.layer-track { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; }
.layer-node { display: flex; gap: 10px; align-items: center; padding: 12px; border: 1px solid #dcdfe6; border-radius: 10px; background: #fafafa; text-align: left; cursor: pointer; }
.layer-node.accessible:hover { border-color: #79bbff; background: #f5faff; }
.layer-node.active { border-color: #409eff; background: #ecf5ff; box-shadow: 0 0 0 1px #409eff inset; }
.layer-node.locked { opacity: .42; cursor: not-allowed; }
.layer-index { flex: none; width: 28px; height: 28px; display: grid; place-items: center; border-radius: 50%; color: #fff; background: #909399; font-weight: 700; }
.layer-node.active .layer-index { background: #409eff; }
.layer-copy { min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.layer-copy strong { color: #303133; }
.layer-copy small { color: #909399; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.capability-layer { margin-top: 20px; }
.capability-title { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
.capability-title h2 { margin: 0; color: #303133; font-size: 18px; }
.capability-title p { margin: 4px 0 0; color: #909399; font-size: 12px; }
.workspace-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.workspace-entry { min-height: 170px; padding: 18px; border: 1px solid #e4e7ed; border-radius: 12px; background: #fff; text-align: left; cursor: pointer; transition: .18s ease; }
.workspace-entry:hover { transform: translateY(-2px); border-color: #79bbff; box-shadow: 0 8px 24px rgba(31,45,61,.08); }
.entry-kicker { display: block; margin-bottom: 12px; color: #409eff; font-size: 12px; font-weight: 700; }
.workspace-entry strong { color: #303133; font-size: 17px; }
.workspace-entry p { min-height: 42px; margin: 10px 0 16px; color: #606266; line-height: 1.6; }
.entry-action { color: #409eff; font-size: 13px; }
@media (max-width: 980px) { .layer-track, .workspace-grid { grid-template-columns: 1fr 1fr; } }
@media (max-width: 640px) { .workspace-hero-main { align-items: flex-start; flex-direction: column; } .layer-track, .workspace-grid { grid-template-columns: 1fr; } }
</style>
