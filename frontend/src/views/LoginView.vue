<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance } from 'element-plus'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const formRef = ref<FormInstance>()
const loading = ref(false)
const form = reactive({ username: '', password: '' })
const rules = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function onSubmit() {
  await formRef.value?.validate()
  loading.value = true
  try {
    await auth.login(form.username, form.password)
    ElMessage.success('登录成功')
    router.push('/dashboard')
  } catch {
    // 错误消息由 http 拦截器统一弹出
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div
    style="height: 100vh; display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, #1f2d3d, #2b5876)"
  >
    <el-card style="width: 380px">
      <h2 style="text-align: center; margin-top: 0">校园食堂智能体</h2>
      <p style="text-align: center; color: #909399; font-size: 13px">
        就餐数据分析与菜品优化决策闭环
      </p>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="onSubmit">
        <el-form-item label="账号" prop="username">
          <el-input v-model="form.username" placeholder="admin" size="large" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            placeholder="Admin@123"
            size="large"
            @keyup.enter="onSubmit"
          />
        </el-form-item>
        <el-button
          type="primary"
          size="large"
          style="width: 100%"
          :loading="loading"
          native-type="submit"
        >
          登录
        </el-button>
      </el-form>
      <p style="color: #909399; font-size: 12px; text-align: center; margin-bottom: 0">
        演示账号：admin / Admin@123
      </p>
    </el-card>
  </div>
</template>