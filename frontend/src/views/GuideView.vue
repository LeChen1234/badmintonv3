<template>
  <div class="guide-page">
    <el-card class="hero-card" shadow="never">
      <div class="hero-content">
        <div>
          <el-tag type="primary" effect="dark">首次使用建议阅读</el-tag>
          <h1>羽毛球视频标注系统新手指南</h1>
          <p>从视频上传到数据导出的完整操作说明。建议先阅读“标准流程”，再根据自己的角色查看对应章节。</p>
        </div>
        <el-button type="primary" size="large" @click="$router.push('/tasks')">进入任务管理</el-button>
      </div>
    </el-card>

    <el-row :gutter="16" class="summary-row">
      <el-col v-for="item in summaries" :key="item.title" :xs="24" :sm="12" :lg="6">
        <el-card shadow="hover" class="summary-card">
          <strong>{{ item.title }}</strong>
          <p>{{ item.text }}</p>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="section-card">
      <template #header><strong>一、标准操作流程</strong></template>
      <el-steps :active="6" finish-status="success" align-center>
        <el-step title="创建任务" description="管理员设置项目和标注员" />
        <el-step title="上传视频" description="校验重复并生成视频 ID" />
        <el-step title="选择数据轨道" description="区分比赛时序与抵近质量数据" />
        <el-step title="逐人粗标" description="学生画框、修正关键点并标动作片段" />
        <el-step title="专家判定" description="只处理专业技术属性" />
        <el-step title="审核导出" description="完成复核、锁定和版本化导出" />
      </el-steps>
      <el-alert class="flow-tip" type="info" :closable="false"
        title="推荐顺序：选择人员 → 绘制边界框 → 运行框内姿态预标注 → 修正关键点 → 填写基础动作 → 保存。" />
    </el-card>

    <el-card shadow="never" class="section-card">
      <template #header><strong>二、按角色查看职责</strong></template>
      <el-tabs v-model="activeRole">
        <el-tab-pane label="学生标注员" name="student">
          <GuideList :items="studentSteps" />
          <el-alert type="success" :closable="false" title="学生只负责可直接观察的粗标内容，不需要判断动作质量、拍面姿态等专家字段。" />
        </el-tab-pane>
        <el-tab-pane label="体育专家" name="expert">
          <GuideList :items="expertSteps" />
          <el-alert type="warning" :closable="false" title="从“审核流程 → 专家判定队列”进入，只处理系统列出的专业判断，无需重新绘制学生已完成的边界框和骨架。" />
        </el-tab-pane>
        <el-tab-pane label="组长/管理员" name="manager">
          <GuideList :items="managerSteps" />
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-card shadow="never" class="section-card">
      <template #header><strong>三、视频与采集协议</strong></template>
      <el-collapse accordion>
        <el-collapse-item title="1. 上传视频" name="upload">
          <p>每个任务只接收一个视频文件。支持 MP4、AVI、MOV、MKV、WebM 和 FLV。大文件自动分块上传，可在网络中断后继续。</p>
          <p>系统使用 SHA-256 内容指纹检测重复视频。相同内容即使文件名不同，也会被识别为重复。上传成功后生成独立的视频 UUID。</p>
        </el-collapse-item>
        <el-collapse-item title="2. 先选择正确的数据轨道" name="protocol">
          <p><strong>比赛/动作时序轨：</strong>适合动作类别、阶段、受迫性、移动和战术。远景比赛画面不能据此作精细生物力学质量结论。</p>
          <p><strong>抵近训练质量轨：</strong>适合动作质量、完整动作序列和清晰可见的球拍接触细节。必须填写目标动作、拍摄视角和受试者。</p>
          <p>反光标记点方案只记录实际完成实体布点的受控实验；普通视频不能把模型推测点冒充观测点。</p>
        </el-collapse-item>
        <el-collapse-item title="3. 选择单打或双打" name="format">
          <p><strong>单打：</strong>必须录入 2 名运动员；<strong>双打：</strong>必须录入 4 名运动员。人数不匹配时不能确认比赛信息。</p>
        </el-collapse-item>
        <el-collapse-item title="4. 录入运动员或受试者信息" name="players">
          <p>姓名为必填项。受试者编码建议使用稳定且不包含真实身份的信息，例如 PLAYER_001，以便跨比赛统计且保护隐私。</p>
        </el-collapse-item>
        <el-collapse-item title="5. 记录机位和会话编号" name="camera">
          <p>同一动作的不同视角使用相同采集会话编号，并分别填写正面、背面、左右侧和机位高度，便于后续研究跨视角不变性。</p>
        </el-collapse-item>
        <el-collapse-item title="6. 帧时间戳" name="timestamp">
          <p>每张抽取帧都记录其在原视频中的毫秒时间戳。时间戳显示在画面左下角，并随 JSON、CSV 和 COCO 数据一起导出。</p>
        </el-collapse-item>
      </el-collapse>
    </el-card>

    <el-card shadow="never" class="section-card">
      <template #header><strong>四、逐帧标注详细操作</strong></template>
      <div class="instruction-grid">
        <article v-for="(item, index) in annotationSteps" :key="item.title" class="instruction-item">
          <span class="step-number">{{ index + 1 }}</span>
          <div><h3>{{ item.title }}</h3><p>{{ item.text }}</p></div>
        </article>
      </div>
      <el-divider content-position="left">常用画布操作</el-divider>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="缩放">鼠标滚轮，或画面上方的 + / − 按钮</el-descriptions-item>
        <el-descriptions-item label="平移">按住空格并拖动，或使用鼠标中键拖动</el-descriptions-item>
        <el-descriptions-item label="设置关键点">选择右侧关键点名称，再点击图像位置</el-descriptions-item>
        <el-descriptions-item label="修正关键点">直接拖动已经显示的关键点</el-descriptions-item>
        <el-descriptions-item label="调整点大小">使用画面上方“关键点尺寸”滑块；不会改变数据坐标</el-descriptions-item>
        <el-descriptions-item label="切换人物">在“本帧人物记录”中点击对应人员的“编辑”按钮</el-descriptions-item>
        <el-descriptions-item label="隐藏人物">取消人员姓名前的勾选，只隐藏图层，不删除数据</el-descriptions-item>
        <el-descriptions-item label="保存快捷键">Ctrl+S（macOS 使用 Command+S）</el-descriptions-item>
        <el-descriptions-item label="连续动作片段">先选人物和动作，在开始帧设起点，移动到结束帧后保存</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card shadow="never" class="section-card">
      <template #header><strong>五、质量控制与审核</strong></template>
      <el-timeline>
        <el-timeline-item timestamp="学生粗标" type="primary">完成人员身份、边界框、关键点、基础动作类型和接触事件。</el-timeline-item>
        <el-timeline-item timestamp="学生自核" type="warning">检查漏人、错人、框越界、左右肢体错误和关键点遗漏。</el-timeline-item>
        <el-timeline-item timestamp="组长核对" type="warning">检查标注规范一致性和任务完整性，问题记录退回学生。</el-timeline-item>
        <el-timeline-item timestamp="专家判定" type="danger">判断动作阶段、质量、受迫性、拍面姿态、支撑脚和技术偏差。</el-timeline-item>
        <el-timeline-item timestamp="锁定与导出" type="success">完成分歧裁决后锁定数据，生成带版本和指纹的数据集。</el-timeline-item>
      </el-timeline>
    </el-card>

    <el-card shadow="never" class="section-card">
      <template #header><strong>六、主动学习页面怎么用</strong></template>
      <p>主动学习用于优先选择最有标注价值的帧。非研究人员通常不需要修改其中参数。</p>
      <el-descriptions :column="1" border>
        <el-descriptions-item label="预测熵">模型有多不确定；越高通常越值得人工检查。</el-descriptions-item>
        <el-descriptions-item label="姿态运动幅度">人物动作有多大，用于减少静止或高度重复的帧。</el-descriptions-item>
        <el-descriptions-item label="频谱高频能量">动作变化是否快速、复杂。</el-descriptions-item>
        <el-descriptions-item label="有限差分时序导数">速度、加速度和动作突变是否明显。</el-descriptions-item>
        <el-descriptions-item label="边际效用">新增一轮标注带来的实际模型提升，用于判断继续标注是否值得。</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card shadow="never" class="section-card">
      <template #header><strong>七、常见问题</strong></template>
      <el-collapse accordion>
        <el-collapse-item v-for="faq in faqs" :key="faq.question" :title="faq.question">
          <p>{{ faq.answer }}</p>
        </el-collapse-item>
      </el-collapse>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { defineComponent, h, ref } from 'vue'

const GuideList = defineComponent({
  props: { items: { type: Array as () => string[], required: true } },
  setup(props) {
    return () => h('ol', { class: 'role-list' }, props.items.map((item) => h('li', item)))
  },
})

const activeRole = ref('student')
const summaries = [
  { title: '先区分数据轨道', text: '比赛视频做时序和战术，抵近训练视频才做精细动作质量。' },
  { title: '逐人独立标注', text: '每名运动员拥有独立的身份、边界框、骨架和动作记录。' },
  { title: '框内姿态预标注', text: '先画人物框，再对框内人物生成骨架，避免识别到场外人员。' },
  { title: '学生与专家分工', text: '学生完成客观粗标，专家只处理需要专业知识的判断。' },
]
const studentSteps = [
  '在任务管理中打开分配给自己的任务。',
  '确认采集场景、标注目标、机位和运动员或受试者信息无误。',
  '逐帧点击“新增人物”，选择姓名后绘制人物边界框。',
  '运行框内姿态预标注，人工修正错误或缺失的关键点。',
  '对完整动作设置起止帧，保存连续动作片段；不要把同一动作机械复制到每一帧。',
  '填写基础动作类型和是否为击球接触事件，然后保存。',
  '完成全部帧后进行自核并提交审核。',
]
const expertSteps = [
  '进入“审核流程”，打开“体育专家判定队列”。',
  '按照待办原因进入指定任务、帧和人员记录。',
  '参考学生边界框和骨架，仅判断专家字段。',
  '填写动作阶段、动作质量、受迫性和接触技术属性。',
  '保存后记录自动移出专家待办队列。',
]
const managerSteps = [
  '创建项目和任务，指定主标注员及独立复标员。',
  '检查视频处理状态、比赛元信息和标注进度。',
  '处理学生自核与组长核对流程，明确填写退回原因。',
  '确认专家待办和盲法分歧全部解决后执行终审。',
  '锁定标注并从导出页面生成版本化数据集。',
]
const annotationSteps = [
  { title: '新增人物记录', text: '点击“新增人物”，系统进入人物边界框模式。每帧中的每名运动员分别保存。' },
  { title: '选择人员身份', text: '从下拉列表选择当前准备标注的运动员。不要仅凭衣服颜色猜测，必要时参考前后帧。' },
  { title: '绘制人物边界框', text: '从人物最外侧拖出矩形，覆盖完整人体并尽量减少其他人的区域。' },
  { title: '生成并修正骨架', text: '运行姿态预标注后检查所有关键点。遮挡点可降低可见性或清除，不要把点放在估计位置后当作真实观测。' },
  { title: '填写学生字段', text: '选择基础动作类型，标记本帧是否为击球接触。专家字段由体育专家填写。' },
  { title: '记录连续动作片段', text: '选择人物和动作，在动作开始帧设置起点，移动至结束帧后保存；系统自动记录原视频时间戳。' },
  { title: '保存并检查多人图层', text: '保存后使用显示开关检查不同运动员的框和骨架是否混淆，再继续下一人或下一帧。' },
]
const faqs = [
  { question: '为什么运行姿态预标注前必须先画框？', answer: '整幅比赛画面可能包含裁判、观众和场边人员。人物框限定了检测范围，使结果只对应当前选择的运动员。' },
  { question: '隐藏人物图层会删除数据吗？', answer: '不会。显示开关只影响当前画布，保存的数据不会改变。需要修改时重新勾选并点击“编辑”。' },
  { question: '模型生成的关键点可以直接保存吗？', answer: '不建议直接保存。必须检查左右肢体、遮挡点、手腕和脚踝。球拍与击球位置使用接触几何单独标注，不属于人体预标注点。' },
  { question: '比赛远景视频可以评价动作质量吗？', answer: '只能标直接可见、证据充分的内容。远景比赛视频主要用于动作时序、受迫性、移动和战术；精细动作质量应使用抵近、清晰、连续的训练视频。' },
  { question: '上传提示视频重复怎么办？', answer: '系统按文件内容而不是文件名查重。请查找提示中的视频 ID，避免同一比赛重复进入数据集。' },
  { question: '单打或双打人数填错怎么办？', answer: '在比赛信息确认前切换比赛类型并补齐姓名。已经被标注引用的运动员不能直接删除，需要先处理相关标注。' },
  { question: '关键点太小或缩放后不好拖动怎么办？', answer: '使用画面上方的“关键点尺寸”滑块。点的屏幕尺寸和拖动命中范围不会随图像缩放改变。' },
  { question: '动作类型应该逐帧重复填写吗？', answer: '完整动作应优先使用“连续动作片段”：在开始帧设起点，在结束帧保存。单帧动作字段保留给关键帧和人物姿态记录。' },
  { question: '什么时候应该交给专家？', answer: '动作阶段、动作质量、受迫性、拍面姿态、支撑脚和技术偏差均由专家判断；学生无需猜测。' },
  { question: '保存后为什么仍显示需要复核？', answer: '低置信、遮挡、接触事件或专业字段会自动进入专家队列。这是正常的质量控制流程，不表示学生标注失败。' },
]
</script>

<style scoped>
.guide-page { max-width: 1280px; margin: 0 auto; }
.hero-card { border: none; background: linear-gradient(135deg, #ecf5ff, #f4f4ff); }
.hero-content { display: flex; justify-content: space-between; align-items: center; gap: 28px; }
.hero-content h1 { margin: 14px 0 8px; color: #1f2d3d; font-size: 30px; }
.hero-content p { margin: 0; color: #606266; line-height: 1.7; }
.summary-row { margin-top: 16px; }
.summary-card { height: 100%; }
.summary-card strong { color: #303133; }
.summary-card p { margin: 8px 0 0; color: #606266; line-height: 1.6; font-size: 13px; }
.section-card { margin-top: 16px; }
.flow-tip { margin-top: 22px; }
.role-list { margin: 0 0 16px; padding-left: 24px; color: #303133; line-height: 2; }
.instruction-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.instruction-item { display: flex; gap: 12px; padding: 14px; border: 1px solid #ebeef5; border-radius: 8px; }
.instruction-item h3 { margin: 0 0 6px; font-size: 15px; }
.instruction-item p { margin: 0; color: #606266; line-height: 1.6; font-size: 13px; }
.step-number { flex: none; display: grid; place-items: center; width: 28px; height: 28px; color: white; background: #409eff; border-radius: 50%; font-weight: 700; }
@media (max-width: 800px) {
  .hero-content { align-items: flex-start; flex-direction: column; }
  .instruction-grid { grid-template-columns: 1fr; }
}
</style>
