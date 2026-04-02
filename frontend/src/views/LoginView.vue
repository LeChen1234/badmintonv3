<template>
  <div class="login-wrapper">
    <div class="login-card">
      <div class="login-header">
        <h1>羽毛球训练动作标注系统</h1>
        <p>Badminton Action Annotation Platform</p>
      </div>

      <div class="tab-switch" v-if="allowRegister !== false">
        <span :class="{ active: mode === 'login' }" @click="mode = 'login'">登录</span>
        <span :class="{ active: mode === 'register' }" @click="mode = 'register'">注册</span>
      </div>
      <div v-else class="tab-switch single"><span class="active">登录</span></div>

      <el-form v-if="mode === 'login'" ref="loginFormRef" :model="loginForm" :rules="loginRules" label-position="top">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="loginForm.username" prefix-icon="User" placeholder="请输入用户名" size="large" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="loginForm.password" type="password" prefix-icon="Lock" placeholder="请输入密码"
            show-password size="large" @keyup.enter="handleLogin" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" size="large" class="login-btn" @click="handleLogin">
            登 录
          </el-button>
        </el-form-item>
      </el-form>

      <el-form v-else ref="registerFormRef" :model="registerForm" :rules="registerRules" label-position="top">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="registerForm.username" prefix-icon="User" placeholder="3-64位字符" size="large" />
        </el-form-item>
        <el-form-item label="显示名称" prop="display_name">
          <el-input v-model="registerForm.display_name" placeholder="您的姓名或昵称" size="large" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="registerForm.password" type="password" prefix-icon="Lock" placeholder="至少6位"
            show-password size="large" />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input v-model="registerForm.confirmPassword" type="password" prefix-icon="Lock" placeholder="再次输入密码"
            show-password size="large" @keyup.enter="handleRegister" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" size="large" class="login-btn" @click="handleRegister">
            注 册
          </el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { authApi, configApi } from '@/api'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

const authStore = useAuthStore()
const mode = ref<'login' | 'register'>('login')
const allowRegister = ref<boolean | null>(null)
const loginFormRef = ref<FormInstance>()
const registerFormRef = ref<FormInstance>()
const loading = ref(false)

const loginForm = reactive({ username: '', password: '' })
const loginRules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const registerForm = reactive({ username: '', display_name: '', password: '', confirmPassword: '' })
const registerRules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 64, message: '用户名长度 3-64 位', trigger: 'blur' },
  ],
  display_name: [{ required: true, message: '请输入显示名称', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 128, message: '密码至少6位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    {
      validator: (_rule: any, value: string, callback: Function) => {
        if (value !== registerForm.password) callback(new Error('两次密码不一致'))
        else callback()
      },
      trigger: 'blur',
    },
  ],
}

async function handleLogin() {
  const valid = await loginFormRef.value?.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    await authStore.login(loginForm.username, loginForm.password)
    ElMessage.success('登录成功')
  } catch {
    ElMessage.error('登录失败，请检查用户名和密码')
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  const valid = await registerFormRef.value?.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    await authApi.register({
      username: registerForm.username,
      password: registerForm.password,
      display_name: registerForm.display_name,
    })
    ElMessage.success('注册成功，请登录')
    mode.value = 'login'
    loginForm.username = registerForm.username
    loginForm.password = ''
  } catch {
    /* error handled by interceptor */
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    const res = await configApi.getConfig()
    allowRegister.value = res.data?.allow_public_register ?? true
    if (!allowRegister.value) mode.value = 'login'
  } catch {
    allowRegister.value = true
  }
})
</script>

<style scoped>
.login-wrapper {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-bg);
  padding: var(--base-padding);
}

.login-card {
  width: 100%;
  max-width: 420px;
  padding: 40px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
  transition: var(--transition-base);
}

.login-header {
  text-align: center;
  margin-bottom: var(--base-padding);
}

.login-header h1 {
  margin: 0 0 8px;
  font-size: 22px;
  color: #303133;
  font-weight: 700;
}

.login-header p {
  margin: 0;
  color: #909399;
  font-size: 13px;
}

.tab-switch {
  display: flex;
  justify-content: center;
  gap: 32px;
  margin-bottom: var(--base-padding);
}

.tab-switch span {
  font-size: 16px;
  color: #909399;
  cursor: pointer;
  padding-bottom: 6px;
  border-bottom: 2px solid transparent;
  transition: var(--transition-base);
}

.tab-switch span.active {
  color: #409eff;
  border-bottom-color: #409eff;
  font-weight: 600;
}

.tab-switch span:hover:not(.active) {
  color: #606266;
}

.login-btn {
  width: 100%;
  height: 44px;
  font-size: 16px;
  border-radius: 4px;
  transition: var(--transition-base);
}

.login-btn:hover {
  transform: translateY(-1px);
}

@media (max-width: 480px) {
  .login-card {
    padding: var(--base-padding);
    border-radius: 8px;
  }

  .login-header h1 {
    font-size: 18px;
  }

  .tab-switch {
    gap: 24px;
  }
}
</style>
