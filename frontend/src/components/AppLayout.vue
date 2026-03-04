<template>
  <el-container class="app-layout">
    <el-aside :width="isCollapsed ? '64px' : '220px'" class="app-sidebar">
      <div class="sidebar-header">
        <img src="/vite.svg" alt="logo" class="logo-icon" />
        <span v-show="!isCollapsed" class="logo-text">标注管理平台</span>
      </div>

      <el-menu
        :default-active="route.path"
        :collapse="isCollapsed"
        :router="true"
        background-color="#1d1e2c"
        text-color="#a0a3b1"
        active-text-color="#409eff"
        class="sidebar-menu"
      >
        <el-menu-item index="/">
          <el-icon><DataAnalysis /></el-icon>
          <template #title>总览仪表盘</template>
        </el-menu-item>

        <el-menu-item v-if="auth.hasRole(UserRole.ADMIN)" index="/users">
          <el-icon><User /></el-icon>
          <template #title>用户管理</template>
        </el-menu-item>

        <el-menu-item index="/tasks">
          <el-icon><Tickets /></el-icon>
          <template #title>任务与标注</template>
        </el-menu-item>

        <el-menu-item index="/progress">
          <el-icon><TrendCharts /></el-icon>
          <template #title>进度监控</template>
        </el-menu-item>

        <el-menu-item
          v-if="auth.hasRole(UserRole.ADMIN, UserRole.EXPERT, UserRole.LEADER)"
          index="/review"
        >
          <el-icon><Checked /></el-icon>
          <template #title>审核面板</template>
        </el-menu-item>

        <el-menu-item
          v-if="auth.hasRole(UserRole.ADMIN, UserRole.EXPERT)"
          index="/export"
        >
          <el-icon><Download /></el-icon>
          <template #title>数据导出</template>
        </el-menu-item>
      </el-menu>

      <div class="sidebar-toggle" @click="isCollapsed = !isCollapsed">
        <el-icon :size="18">
          <DArrowLeft v-if="!isCollapsed" />
          <DArrowRight v-else />
        </el-icon>
      </div>
    </el-aside>

    <el-container>
      <el-header class="app-header">
        <div class="header-left">
          <span class="page-title">{{ route.meta.title || '总览仪表盘' }}</span>
        </div>
        <div class="header-right">
          <el-dropdown trigger="click" @command="handleCommand">
            <span class="user-dropdown">
              <el-avatar :size="32" class="user-avatar">
                {{ auth.displayName.charAt(0) }}
              </el-avatar>
              <span class="user-name">{{ auth.displayName }}</span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item disabled>
                  {{ UserRoleLabel[auth.role!] }}
                </el-dropdown-item>
                <el-dropdown-item divided command="logout">
                  <el-icon><SwitchButton /></el-icon>
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { UserRole, UserRoleLabel } from '@/types'

const route = useRoute()
const auth = useAuthStore()
const isCollapsed = ref(false)

function handleCommand(cmd: string) {
  if (cmd === 'logout') auth.logout()
}
</script>

<style scoped lang="scss">
.app-layout {
  height: 100vh;
}

.app-sidebar {
  background: var(--color-sidebar);
  display: flex;
  flex-direction: column;
  transition: width 0.25s ease;
  overflow: hidden;
}

.sidebar-header {
  height: var(--header-height);
  display: flex;
  align-items: center;
  padding: 0 16px;
  gap: 10px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.logo-icon {
  width: 28px;
  height: 28px;
  flex-shrink: 0;
}

.logo-text {
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  white-space: nowrap;
}

.sidebar-menu {
  flex: 1;
  border-right: none;
  overflow-y: auto;
  padding-top: 8px;
}

.sidebar-toggle {
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #a0a3b1;
  cursor: pointer;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  transition: color 0.2s;

  &:hover {
    color: #fff;
  }
}

.app-header {
  height: var(--header-height);
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  border-bottom: 1px solid #ebeef5;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

.page-title {
  font-size: 17px;
  font-weight: 600;
  color: #303133;
}

.user-dropdown {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: #606266;
}

.user-avatar {
  background: #409eff;
  color: #fff;
  font-weight: 600;
}

.user-name {
  font-size: 14px;
}

.app-main {
  background: var(--color-bg);
  padding: 20px;
  overflow-y: auto;
}
</style>
