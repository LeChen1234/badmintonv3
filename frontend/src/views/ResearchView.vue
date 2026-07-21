<template>
  <div class="research-page">
    <el-card>
      <template #header><strong>主动学习闭环（Active Learning Loop）与基于边际效用的停止准则</strong></template>
      <p class="plain-explanation">通俗解释：系统优先挑选最值得标注的帧，并根据实际训练收益判断是否还需要继续增加标注。</p>
      <el-select v-model="projectId" placeholder="选择项目" style="width: 320px" @change="loadRounds">
        <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
      </el-select>
      <el-alert v-if="state?.stop_recommended" type="success" :closable="false" title="已满足预注册停止准则：单位标注成本的边际性能增益低于阈值" style="margin-top: 16px" />
      <el-alert v-else-if="projectId" type="info" :closable="false" title="尚未满足停止准则：建议继续下一轮等预算数据采集与标注" style="margin-top: 16px" />
      <div v-if="state" class="weights">
        <div v-for="(value, name) in state.current_weights" :key="name" class="weight-item">
          <div><span>{{ componentLabel(String(name)) }}</span><small>{{ componentPlain(String(name)) }}</small></div>
          <el-progress :percentage="Math.round(Number(value) * 100)" />
        </div>
      </div>
    </el-card>

    <el-card v-if="projectId" style="margin-top: 16px">
      <template #header><strong>登记轻量级代理训练（Lightweight Proxy Training）结果</strong></template>
      <p class="plain-explanation">通俗解释：用一个小模型快速训练，检查本轮新增标注是否真的让模型表现变好，不替代最终模型训练。</p>
      <el-collapse class="metric-glossary">
        <el-collapse-item title="指标释义（含通俗解释）" name="metrics">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="Macro-F1">各类别 F1 的宏平均；通俗说：每种动作同等重要，检查整体识别是否均衡。</el-descriptions-item>
            <el-descriptions-item label="Balanced Accuracy">各类别召回率的平均；通俗说：避免样本多的动作掩盖小类别表现。</el-descriptions-item>
            <el-descriptions-item label="NLL（越低越好）">负对数似然；通俗说：模型答错且过度自信时会受到更大惩罚。</el-descriptions-item>
            <el-descriptions-item label="ECE（越低越好）">期望校准误差；通俗说：模型说“80%把握”时，最好真的约有80%正确。</el-descriptions-item>
            <el-descriptions-item label="Bootstrap p 值">重采样显著性检验；通俗说：判断性能提升是否可能只是运气。</el-descriptions-item>
            <el-descriptions-item label="边际效用">新增一轮数据带来的性能增益；通俗说：再投入一小时标注还值不值得。</el-descriptions-item>
          </el-descriptions>
        </el-collapse-item>
      </el-collapse>
      <input ref="reportInput" type="file" accept="application/json,.json" hidden @change="importReport" />
      <el-button plain type="success" style="margin-bottom: 16px" @click="reportInput?.click()">导入代理训练评估报告（JSON）</el-button>
      <el-form :model="form" label-width="150px" class="round-form">
        <el-row :gutter="16">
          <el-col :span="8"><el-form-item label="数据集版本 ID"><el-input v-model="form.dataset_id" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="模型版本"><el-input v-model="form.model_version" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="新增标注数"><el-input-number v-model="form.annotation_count" :min="1" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="标注成本（人时）"><el-input-number v-model="form.annotation_hours" :min="0.01" :step="0.5" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="Macro-F1 均值"><el-input-number v-model="form.macro_f1_mean" :min="0" :max="1" :step="0.001" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="Macro-F1 标准差"><el-input-number v-model="form.macro_f1_std" :min="0" :max="1" :step="0.001" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="重复实验次数"><el-input-number v-model="form.repeat_count" :min="2" :max="100" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="平衡准确率（Balanced Accuracy）"><el-input-number v-model="form.balanced_accuracy_mean" :min="0" :max="1" :step="0.001" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="负对数似然（NLL）"><el-input-number v-model="form.nll_mean" :min="0" :step="0.01" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="期望校准误差（ECE）"><el-input-number v-model="form.ece_mean" :min="0" :max="1" :step="0.001" /></el-form-item></el-col>
        </el-row>
        <el-divider content-position="left">采样函数组件的消融增益（Ablation Gain, ΔMacro-F1）</el-divider>
        <p class="plain-explanation">通俗解释：分别去掉一个选帧指标，观察性能下降多少；下降越多，说明该指标越有用。</p>
        <el-row :gutter="16">
          <el-col v-for="name in components" :key="name" :span="6">
            <el-form-item :label="componentLabel(name)"><el-input-number v-model="form.component_gains[name]" :step="0.001" /></el-form-item>
          </el-col>
        </el-row>
        <el-button type="primary" :loading="saving" @click="saveRound">登记实验结果并更新下一轮采样权重</el-button>
      </el-form>
    </el-card>

    <el-card v-if="state?.rounds?.length" style="margin-top: 16px">
      <template #header><strong>逐轮实验记录与学习曲线（Learning Curve）</strong></template>
      <p class="plain-explanation">通俗解释：横轴是累计投入的标注时间，纵轴是模型性能，用于判断继续标注是否划算。</p>
      <div class="learning-curve">
        <svg viewBox="0 0 760 250" role="img" aria-label="Macro-F1 相对累计标注人时学习曲线">
          <line x1="45" y1="215" x2="735" y2="215" stroke="#909399" />
          <line x1="45" y1="20" x2="45" y2="215" stroke="#909399" />
          <polyline v-if="curvePoints.length > 1" :points="curvePolyline" fill="none" stroke="#409eff" stroke-width="3" />
          <g v-for="point in curvePoints" :key="point.round">
            <circle :cx="point.x" :cy="point.y" r="5" fill="#409eff" />
            <text :x="point.x" :y="point.y - 10" text-anchor="middle" font-size="11">{{ point.f1.toFixed(3) }}</text>
            <text :x="point.x" y="235" text-anchor="middle" font-size="11">{{ point.hours.toFixed(1) }}h</text>
          </g>
          <text x="390" y="248" text-anchor="middle" font-size="12">累计标注人时</text>
          <text x="12" y="120" text-anchor="middle" font-size="12" transform="rotate(-90 12 120)">Macro-F1</text>
        </svg>
      </div>
      <el-table :data="state.rounds" stripe>
        <el-table-column prop="round_index" label="轮次" width="70" />
        <el-table-column prop="dataset_id" label="数据集版本 ID" width="190" />
        <el-table-column prop="annotation_hours" label="人时" width="80" />
        <el-table-column label="Macro-F1"><template #default="{ row }">{{ metric(row.metrics.macro_f1_mean) }}</template></el-table-column>
        <el-table-column label="边际性能增益（ΔMacro-F1）"><template #default="{ row }">{{ metric(row.marginal_utility.delta_macro_f1) }}</template></el-table-column>
        <el-table-column label="单位成本增益（ΔF1/人时）"><template #default="{ row }">{{ metric(row.marginal_utility.gain_per_hour) }}</template></el-table-column>
        <el-table-column label="Bootstrap 双侧 p 值"><template #default="{ row }">{{ metric(row.metrics.statistical_comparison?.macro_f1?.two_sided_p) }}</template></el-table-column>
        <el-table-column label="决策"><template #default="{ row }"><el-tag :type="row.stop_recommended ? 'success' : 'primary'">{{ row.stop_recommended ? '停止' : '继续' }}</el-tag></template></el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { projectApi, researchApi } from '@/api'

const projects = ref<any[]>([])
const projectId = ref<number | null>(null)
const state = ref<any>(null)
const saving = ref(false)
const reportInput = ref<HTMLInputElement | null>(null)
const components = ['motion', 'entropy', 'spectral', 'calculus']
const form = reactive({
  dataset_id: '', model_version: '', selection_strategy: 'information_functional',
  annotation_count: 1, annotation_hours: 1, macro_f1_mean: 0, macro_f1_std: 0, repeat_count: 5,
  balanced_accuracy_mean: 0, nll_mean: 0, ece_mean: 0,
  component_gains: { motion: 0, entropy: 0, spectral: 0, calculus: 0 } as Record<string, number>,
  statistical_comparison: {} as Record<string, any>,
})
const componentLabel = (name: string) => ({
  motion: '姿态运动幅度（Pose Motion Magnitude）',
  entropy: '预测熵（Predictive Entropy）',
  spectral: '频谱高频能量（DCT High-frequency Energy）',
  calculus: '有限差分时序导数（Finite-difference Temporal Derivatives）',
}[name] || name)
const componentPlain = (name: string) => ({
  motion: '人物动作有多大', entropy: '模型有多拿不准', spectral: '动作变化是否快速或复杂',
  calculus: '速度、加速度和动作突变有多明显',
}[name] || '')
const metric = (value: unknown) => typeof value === 'number' ? value.toFixed(4) : '-'
const curvePoints = computed(() => {
  const rounds = state.value?.rounds || []
  let cumulative = 0
  const raw = rounds.map((round: any) => {
    cumulative += Number(round.annotation_hours || 0)
    return { round: round.round_index, hours: cumulative, f1: Number(round.metrics.macro_f1_mean || 0) }
  })
  const maxHours = Math.max(1, ...raw.map((point: any) => point.hours))
  const f1Values = raw.map((point: any) => point.f1)
  const minF1 = Math.max(0, Math.min(...f1Values, 1) - 0.03)
  const maxF1 = Math.min(1, Math.max(...f1Values, 0) + 0.03)
  return raw.map((point: any) => ({ ...point, x: 45 + point.hours / maxHours * 690, y: 215 - (point.f1 - minF1) / Math.max(0.01, maxF1 - minF1) * 195 }))
})
const curvePolyline = computed(() => curvePoints.value.map((point: any) => `${point.x},${point.y}`).join(' '))

async function loadRounds() {
  if (!projectId.value) return
  state.value = (await researchApi.rounds(projectId.value)).data
}

async function saveRound() {
  if (!projectId.value || !form.dataset_id || !form.model_version) {
    ElMessage.warning('请填写项目、Dataset ID 和模型版本')
    return
  }
  saving.value = true
  try {
    const result = await researchApi.createRound(projectId.value, form)
    ElMessage.success(result.data.decision.reason)
    form.dataset_id = ''
    await loadRounds()
  } finally { saving.value = false }
}

async function importReport(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  try {
    const report = JSON.parse(await file.text())
    const imported = report?.research_import
    if (!imported || typeof imported !== 'object') throw new Error('报告缺少 research_import')
    for (const key of ['dataset_id', 'model_version', 'annotation_count', 'annotation_hours', 'macro_f1_mean', 'macro_f1_std', 'repeat_count', 'balanced_accuracy_mean', 'nll_mean', 'ece_mean']) {
      if (imported[key] !== null && imported[key] !== undefined) (form as any)[key] = imported[key]
    }
    if (imported.component_gains) Object.assign(form.component_gains, imported.component_gains)
    if (imported.statistical_comparison) form.statistical_comparison = imported.statistical_comparison
    ElMessage.success('代理训练指标已载入，请核对标注成本与组件消融增益')
  } catch (error: any) {
    ElMessage.error(error?.message || '报告格式无效')
  } finally {
    ;(event.target as HTMLInputElement).value = ''
  }
}

onMounted(async () => {
  projects.value = (await projectApi.list()).data
  if (projects.value.length) { projectId.value = projects.value[0].id; await loadRounds() }
})
</script>

<style scoped>
.weights { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px 30px; margin-top: 18px; }
.weight-item { display: grid; grid-template-columns: 90px 1fr; align-items: center; gap: 10px; }
.weight-item { grid-template-columns: minmax(260px, 1fr) 1.4fr; }
.weight-item small { display: block; margin-top: 3px; color: #909399; line-height: 1.35; }
.plain-explanation { margin: 0 0 14px; color: #606266; font-size: 13px; line-height: 1.6; }
.metric-glossary { margin-bottom: 16px; }
.round-form { max-width: 1100px; }
.learning-curve { max-width: 900px; margin: 0 auto 18px; }
.learning-curve svg { width: 100%; background: #fafafa; border-radius: 8px; }
</style>
