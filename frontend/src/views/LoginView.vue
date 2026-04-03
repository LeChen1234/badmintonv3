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
        <el-form-item label="图片验证码" prop="captcha_answer">
          <div class="captcha-row">
            <el-input
              v-model="registerForm.captcha_answer"
              placeholder="请输入图片中的字符"
              size="large"
              @keyup.enter="handleRegister"
            />
            <el-button size="large" @click="fetchCaptcha">刷新</el-button>
          </div>
          <div class="captcha-image-wrap">
            <img
              v-if="captchaImage"
              :src="captchaImage"
              alt="captcha"
              class="captcha-image"
              @click="fetchCaptcha"
            />
            <div v-else class="captcha-fallback">验证码加载中...</div>
          </div>
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
import { ref, reactive, onMounted, watch } from 'vue'
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
const captchaImage = ref('')

const loginForm = reactive({ username: '', password: '' })
const loginRules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const registerForm = reactive({
  username: '',
  display_name: '',
  password: '',
  confirmPassword: '',
  captcha_id: '',
  captcha_answer: '',
})
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
  captcha_answer: [{ required: true, message: '请输入验证码', trigger: 'blur' }],
}

async function fetchCaptcha() {
  try {
    const res = await authApi.getCaptcha()
    registerForm.captcha_id = res.data.captcha_id
    captchaImage.value = res.data.image_base64
    registerForm.captcha_answer = ''
  } catch {
    captchaImage.value = ''
  }
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
  if (!registerForm.captcha_id) {
    await fetchCaptcha()
  }

  const valid = await registerFormRef.value?.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    await authApi.register({
      username: registerForm.username,
      password: registerForm.password,
      display_name: registerForm.display_name,
      captcha_id: registerForm.captcha_id,
      captcha_answer: registerForm.captcha_answer,
    })
    ElMessage.success('注册成功，请登录')
    mode.value = 'login'
    loginForm.username = registerForm.username
    loginForm.password = ''
  } catch {
    await fetchCaptcha()
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
    if (allowRegister.value) await fetchCaptcha()
  } catch {
    allowRegister.value = true
    await fetchCaptcha()
  }
})

watch(mode, async (newMode) => {
  if (newMode === 'register' && allowRegister.value !== false) {
    await fetchCaptcha()
  }
})
</script>

<style scoped>
.login-wrapper {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
.login-card {
  width: 420px;
  padding: 40px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
}
.login-header {
  text-align: center;
  margin-bottom: 24px;
}
.login-header h1 {
  margin: 0 0 8px;
  font-size: 22px;
  color: #303133;
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
  margin-bottom: 24px;
}
.tab-switch span {
  font-size: 16px;
  color: #909399;
  cursor: pointer;
  padding-bottom: 6px;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
}
.tab-switch span.active {
  color: #409eff;
  border-bottom-color: #409eff;
  font-weight: 600;
}
.login-btn {
  width: 100%;
}

.captcha-row {
  display: flex;
  gap: 8px;
  width: 100%;
}

.captcha-question {
  margin-top: 8px;
  color: #606266;
  font-size: 13px;
}

.captcha-image-wrap {
  margin-top: 8px;
}

.captcha-image {
  height: 64px;
  width: 180px;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  cursor: pointer;
  background: #f5f7fa;
}

.captcha-fallback {
  height: 64px;
  width: 180px;
  border: 1px dashed #dcdfe6;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #909399;
  font-size: 12px;
}
</style>
