<template>
  <div>
    <el-card>
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <el-button @click="$router.push('/tasks')" type="info" plain size="small">
              返回任务列表
            </el-button>
            <span style="margin-left: 12px; font-weight: 600;">
              标注任务 · {{ batchName }} · 帧 {{ currentFrame }}/{{ totalFrames }}
              <span v-if="currentTimestampMs !== null" class="frame-timestamp">· {{ formatTimestamp(currentTimestampMs) }}</span>
            </span>
          </div>
          <div class="header-right">
            <el-tag v-if="currentAnnotation?.annotator_name" type="info" style="margin-right: 8px;">
              标注人: {{ currentAnnotation.annotator_name }}
            </el-tag>
            <el-tag :type="statusTagType">{{ statusLabel }}</el-tag>
          </div>
        </div>
      </template>

      <el-alert
        v-if="mediaProcessStatus !== 'idle'"
        :title="mediaProcessTitle"
        :description="mediaProcessMessage || undefined"
        :type="mediaProcessAlertType"
        :closable="false"
        show-icon
        style="margin-bottom: 16px;"
      />

      <div
        v-if="isMediaProcessing && mediaProcessPercent !== null"
        class="media-processing-progress"
      >
        <div class="media-processing-progress-head">
          <span>后台处理进度</span>
          <span>{{ mediaProcessPercent }}%</span>
        </div>
        <el-progress :percentage="mediaProcessPercent" :stroke-width="10" />
        <p v-if="mediaProcessProgressText" class="media-processing-progress-text">{{ mediaProcessProgressText }}</p>
      </div>

      <div v-if="chunkUploadActive" class="chunk-upload-progress">
        <div class="chunk-upload-head">
          <span class="chunk-upload-title">视频上传进度</span>
          <span class="chunk-upload-meta">
            {{ chunkUploadedCount }}/{{ chunkTotalCount }} 分块
            <span v-if="chunkUploadETA" class="chunk-eta">{{ chunkUploadETA }}</span>
          </span>
        </div>
        <el-progress :percentage="chunkUploadPercent" :stroke-width="12" />
      </div>

      <!-- 无帧时上传源视频 -->
      <div v-if="totalFrames === 0" class="upload-section">
        <el-upload
          ref="uploadRef"
          class="upload-area"
          drag
          :disabled="isMediaProcessing"
          :auto-upload="false"
          :limit="1"
          :on-change="onFileChange"
          :on-exceed="() => ElMessage.warning('每个任务只能上传一个视频')"
          accept=".mp4,.avi,.mov,.mkv,.webm,.flv"
        >
          <el-icon class="upload-icon"><UploadFilled /></el-icon>
          <div class="upload-text">
            <p>将视频拖到此处，或点击选择文件</p>
            <p class="upload-hint">每个任务接收一个视频；系统校验内容重复后生成独立视频 ID，并为抽取帧记录时间戳。</p>
          </div>
        </el-upload>

        <div v-if="isVideoSelected" class="yolo-settings-card">
          <div class="yolo-settings-head">
            <span class="yolo-settings-title">视频预处理设置</span>
            <el-switch v-model="useYoloFilter" active-text="启用 YOLO 动作过滤" inactive-text="仅均匀抽帧" />
          </div>
          <p class="yolo-settings-desc">建议只在视频上传时开启。系统会先计算本视频的帧间欧氏距离分布，再按你选择的百分位自动筛帧。</p>

          <div v-if="useYoloFilter" class="threshold-controls">
            <span class="threshold-label">动作百分位 (P)</span>
            <el-input-number
              v-model="motionPercentile"
              :min="0"
              :max="100"
              :step="1"
              :precision="0"
              style="width: 160px"
            />
            <div class="threshold-preset-group">
              <el-button size="small" plain @click="motionPercentile = 80">P80</el-button>
              <el-button size="small" plain @click="motionPercentile = 90">P90</el-button>
              <el-button size="small" plain @click="motionPercentile = 95">P95</el-button>
            </div>
          </div>
        </div>

        <div class="upload-actions">
          <el-button type="primary" :loading="uploading" @click="submitUpload" :disabled="!pendingFiles.length || isMediaProcessing">
            开始上传 ({{ pendingFiles.length }} 个文件)
          </el-button>
        </div>
      </div>

      <div v-if="totalFrames === 0 || !metadataConfirmed" class="metadata-step-card">
        <div class="metadata-step-head">
          <span class="metadata-step-title">步骤 2：填写任务元信息并确认</span>
          <el-tag :type="metadataConfirmed ? 'success' : 'warning'">
            {{ metadataConfirmed ? '已确认' : '待确认' }}
          </el-tag>
        </div>
        <p class="metadata-step-desc">
          请先选择单打或双打，再填写全部参赛运动员。单打固定 2 人，双打固定 4 人。
        </p>

        <el-form label-position="top" class="metadata-form">
          <el-form-item label="比赛类型（必填）">
            <el-radio-group v-model="metadataForm.match_format" @change="onMatchFormatChange">
              <el-radio-button value="singles">单打（2 人）</el-radio-button>
              <el-radio-button value="doubles">双打（4 人）</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="比赛日期（必填）">
            <el-date-picker
              v-model="metadataForm.match_date"
              type="date"
              value-format="YYYY-MM-DD"
              format="YYYY-MM-DD"
              placeholder="选择比赛日期"
              style="width: 100%"
              clearable
            />
          </el-form-item>
          <el-form-item label="比赛名称（必填）">
            <el-input v-model="metadataForm.match_name" maxlength="256" show-word-limit placeholder="例如：2026 校际羽毛球联赛" />
          </el-form-item>

          <div class="metadata-player-head">
            <span>选手信息</span>
            <el-button size="small" type="primary" plain :disabled="metadataForm.players.length >= expectedPlayerCount" @click="addPlayer">
              + 添加选手
            </el-button>
          </div>

          <div class="metadata-player-list">
            <div v-for="(player, idx) in metadataForm.players" :key="idx" class="metadata-player-card">
              <div class="metadata-player-title-row">
                <span class="metadata-player-title">选手 {{ idx + 1 }}</span>
                <el-button size="small" text type="danger" @click="removePlayer(idx)">移除</el-button>
              </div>
              <el-row :gutter="10">
                <el-col :xs="24" :sm="12">
                  <el-form-item label="姓名（必填）">
                    <el-input v-model="player.name" maxlength="128" placeholder="如：张三" />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="12">
                  <el-form-item label="匿名受试者编码">
                    <el-input v-model="player.subject_code" maxlength="64" placeholder="ATHLETE_001（跨比赛保持一致）" />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="12">
                  <el-form-item label="性别（可选）">
                    <el-select v-model="player.gender" clearable placeholder="请选择">
                      <el-option label="男" value="male" />
                      <el-option label="女" value="female" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="12">
                  <el-form-item label="年龄（可选）">
                    <el-input-number v-model="player.age" :min="1" :max="99" controls-position="right" style="width: 100%" />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="12">
                  <el-form-item label="身高 cm（可选）">
                    <el-input-number v-model="player.height_cm" :min="80" :max="260" controls-position="right" style="width: 100%" />
                  </el-form-item>
                </el-col>
              </el-row>
            </div>
          </div>
        </el-form>

        <div class="metadata-actions">
          <el-button :loading="metadataSaving" @click="saveBatchMetadata">保存元信息</el-button>
          <el-button type="success" :loading="metadataConfirming" @click="confirmBatchMetadata">
            确认并开始标注
          </el-button>
        </div>
      </div>

      <template v-else-if="canAnnotate">
        <el-row :gutter="20">
          <el-col :span="16">
            <div class="frame-area">
              <div class="frame-zoom-toolbar" v-if="frameImageUrl">
                <el-button size="small" @click="zoomOutFrame" :disabled="frameZoom <= MIN_FRAME_ZOOM">-</el-button>
                <el-button size="small" @click="resetFrameZoom" :disabled="frameZoom === 1">重置</el-button>
                <el-button size="small" @click="zoomInFrame" :disabled="frameZoom >= MAX_FRAME_ZOOM">+</el-button>
                <span class="frame-zoom-text">缩放 {{ Math.round(frameZoom * 100) }}%</span>
                <span class="frame-zoom-hint">滚轮缩放；空格/中键拖动</span>
                <span class="point-size-label">关键点尺寸</span>
                <el-slider
                  v-model="keypointSizePx"
                  class="point-size-slider"
                  :min="3"
                  :max="14"
                  :step="1"
                  :show-tooltip="true"
                  :format-tooltip="(value: number) => `${value}px`"
                  aria-label="关键点显示尺寸"
                />
                <span class="point-size-value">{{ keypointSizePx }} px</span>
              </div>
              <!-- 当前帧、标注画布和状态叠加层 -->
              <div class="frame-wrapper" v-if="frameImageUrl">
                <div
                  class="frame-viewport"
                  :class="{ 'is-pannable': frameZoom > 1 || framePanX !== 0 || framePanY !== 0, 'is-panning': isPanningViewport }"
                  @wheel.prevent="onFrameWheel"
                  @mousedown.capture="onViewportMouseDown"
                >
                  <div class="frame-img-wrap" ref="frameWrapRef" :style="frameTransformStyle">
                    <img
                      ref="frameImgRef"
                      :src="frameImageUrl"
                      class="frame-img"
                      alt="当前帧"
                      @error="onImageError"
                      @load="drawKeypointsCanvas"
                    />
                    <div class="image-timestamp" v-if="currentTimestampMs !== null">
                      {{ formatTimestamp(currentTimestampMs) }}
                    </div>
                    <canvas
                      ref="canvasRef"
                      class="keypoints-canvas"
                      @click="onCanvasClick"
                      @mousedown="onCanvasMouseDown"
                      @mousemove="onCanvasMouseMove"
                      @mouseup="onCanvasMouseUp"
                      @mouseleave="onCanvasMouseUp"
                    />
                  </div>
                </div>
                <div class="annotation-overlay" v-if="currentAnnotation || selectedPlayerLabel || form.action_type || form.action_phase || form.quality_rating || form.is_contact_event">
                  <div class="overlay-tags">
                    <el-tag v-if="selectedPlayerLabel" type="info" size="small">{{ selectedPlayerLabel }}</el-tag>
                    <el-tag v-if="form.action_type" type="primary" size="small">{{ actionTypeLabel(form.action_type) }}</el-tag>
                    <el-tag v-if="form.action_phase" type="success" size="small">{{ actionPhaseLabel(form.action_phase) }}</el-tag>
                    <el-tag v-if="form.quality_rating" type="warning" size="small">{{ qualityLabel(form.quality_rating) }}</el-tag>
                    <el-tag v-if="form.is_forced_action" type="danger" size="small">受迫性动作</el-tag>
                    <el-tag v-if="form.is_contact_event" type="danger" size="small" effect="dark">击球接触</el-tag>
                    <el-tag v-if="form.is_contact_event && contactForm.contact_zone" size="small">
                      击球区：{{ contactZoneLabel(contactForm.contact_zone) }}
                    </el-tag>
                    <el-tag v-if="hasBBox" type="success" size="small">人物框已标注</el-tag>
                  </div>
                  <div class="overlay-annotator" v-if="currentAnnotation?.annotator_name">
                    标注员：{{ currentAnnotation.annotator_name }} · {{ statusLabel }}
                  </div>
                </div>
              </div>
              <div class="frame-placeholder" v-else>
                <el-icon :size="48"><Picture /></el-icon>
                <p>帧 #{{ currentFrame }}</p>
                <p class="frame-hint" v-if="loadingImage">正在加载图像…</p>
                <p class="frame-hint" v-else>当前帧无可用图像</p>
              </div>
            </div>

            <div class="frame-nav">
              <el-button :disabled="currentFrame <= 1" @click="prevFrame">上一帧</el-button>
              <el-input-number
                v-model="currentFrame"
                :min="1"
                :max="totalFrames"
                size="small"
                style="width: 120px; margin: 0 12px;"
                @change="loadAnnotation"
              />
              <el-button :disabled="currentFrame >= totalFrames" @click="nextFrame">下一帧</el-button>
              <span style="margin-left: 16px; color: #909399; font-size: 13px;">
                已标注 {{ annotatedCount }}/{{ totalFrames }} 帧
              </span>
            </div>

            <div class="re-upload-row">
              <el-button size="small" type="info" plain :disabled="isMediaProcessing" @click="showReUpload = true">重新上传图片/视频</el-button>
            </div>
          </el-col>

          <el-col :span="8">
            <el-form label-width="90px" label-position="top" class="annotation-form">
              <el-alert
                :type="isStudentAnnotator ? 'info' : 'warning'"
                :closable="false"
                :title="isStudentAnnotator ? '学生粗标：身份、边界框、关键点、基础动作与接触事件' : '专家判定：阶段、质量、受迫性与接触技术属性'"
                style="margin-bottom: 14px"
              />
              <el-form-item label="本帧人物记录">
                <div class="frame-person-records">
                  <div
                    v-for="record in frameAnnotations"
                    :key="record.id"
                    class="person-layer-row"
                  >
                    <el-checkbox
                      :model-value="isAnnotationVisible(record.id)"
                      @change="toggleAnnotationVisibility(record.id)"
                    >{{ playerName(record.selected_player_id) }}</el-checkbox>
                    <el-button size="small" :type="currentAnnotation?.id === record.id ? 'primary' : undefined"
                      @click="selectFrameAnnotation(record)">编辑</el-button>
                  </div>
                  <el-button size="small" plain @click="startNewPersonAnnotation">新增人物</el-button>
                </div>
              </el-form-item>
              <el-form-item label="选手（必选）">
                <el-select v-model="form.selected_player_id" placeholder="为当前边界框选择人员" style="width: 100%;" @change="onPlayerSelectionChange">
                  <el-option v-for="opt in annotationPlayerOptions" :key="opt.id" :label="opt.label" :value="opt.id" />
                </el-select>
              </el-form-item>

              <el-form-item label="动作类型（必选）">
                <el-select v-model="form.action_type" placeholder="选择动作类型" style="width: 100%;">
                  <el-option v-for="opt in taxonomy.actions" :key="opt.value" :label="opt.label" :value="opt.value" />
                </el-select>
              </el-form-item>

              <el-form-item label="动作阶段">
                <el-select v-model="form.action_phase" placeholder="由体育专家判定" clearable style="width: 100%;" :disabled="isStudentAnnotator">
                  <el-option v-for="opt in taxonomy.phases" :key="opt.value" :label="opt.label" :value="opt.value" />
                </el-select>
              </el-form-item>

              <el-form-item label="动作质量">
                <el-select v-model="form.quality_rating" placeholder="由体育专家判定" clearable style="width: 100%;" :disabled="isStudentAnnotator">
                  <el-option v-for="opt in taxonomy.qualities" :key="opt.value" :label="opt.label" :value="opt.value" />
                </el-select>
              </el-form-item>

              <el-form-item label="受迫性动作">
                <el-radio-group v-model="form.is_forced_action" :disabled="isStudentAnnotator">
                  <el-radio :label="false">否</el-radio>
                  <el-radio :label="true">是</el-radio>
                </el-radio-group>
              </el-form-item>

              <el-divider content-position="left">击球接触标注</el-divider>
              <el-form-item label="本帧为击球接触事件">
                <el-switch v-model="form.is_contact_event" @change="onContactEventToggle" />
              </el-form-item>
              <template v-if="form.is_contact_event">
              <el-form-item label="接触帧容差（±1 帧）">
                  <el-switch v-model="contactForm.tolerance_flag" />
                </el-form-item>
                <el-form-item label="拍面击球区">
                  <el-select v-model="contactForm.contact_zone" clearable placeholder="由体育专家判定" style="width: 100%;" :disabled="isStudentAnnotator">
                    <el-option v-for="z in CONTACT_ZONES" :key="z.value" :label="z.label" :value="z.value" />
                  </el-select>
                </el-form-item>
              <el-form-item label="拍面姿态">
                  <el-select v-model="contactForm.face_attitude" clearable placeholder="由体育专家判定" style="width: 100%;" :disabled="isStudentAnnotator">
                    <el-option v-for="a in FACE_ATTITUDES" :key="a.value" :label="a.label" :value="a.value" />
                  </el-select>
                </el-form-item>
                <el-form-item label="支撑脚">
                  <el-select v-model="contactForm.support_foot" clearable placeholder="由体育专家判定" style="width: 100%;" :disabled="isStudentAnnotator">
                    <el-option v-for="f in SUPPORT_FEET" :key="f.value" :label="f.label" :value="f.value" />
                  </el-select>
                </el-form-item>
              <el-form-item label="技术偏差属性">
                  <el-select v-model="contactForm.error_attributes" multiple clearable placeholder="由体育专家判定" style="width: 100%;" :disabled="isStudentAnnotator">
                    <el-option v-for="e in ERROR_ATTRIBUTES" :key="e.value" :label="e.label" :value="e.value" />
                  </el-select>
                </el-form-item>
              <el-form-item label="拍面归一化坐标 (u, v)">
                  <span class="uv-readout">
                    {{
                      contactForm.contact_uv.u != null && contactForm.contact_uv.v != null
                        ? `u=${contactForm.contact_uv.u}, v=${contactForm.contact_uv.v}`
                        : '标齐拍面四角与击球点后自动计算'
                    }}
                  </span>
                </el-form-item>
                <el-form-item label="接触几何标注">
                  <div class="layer-mode-actions">
                    <el-button
                      size="small"
                      :type="annotationLayerMode === 'contact_face' ? 'primary' : undefined"
                      @click="switchToContactFaceMode"
                    >拍面四角</el-button>
                    <el-button
                      size="small"
                      :type="annotationLayerMode === 'contact_point' ? 'primary' : undefined"
                      @click="annotationLayerMode = 'contact_point'"
                    >击球点</el-button>
                    <el-button
                      size="small"
                      :type="annotationLayerMode === 'contact_shuttle' ? 'primary' : undefined"
                      @click="annotationLayerMode = 'contact_shuttle'"
                    >羽毛球点</el-button>
                  </div>
                  <div class="keypoint-hint" v-if="annotationLayerMode === 'contact_face'">
                    依次点选：{{ FACE_CORNER_LABELS[contactForm.face_corners[selectedFaceCornerIndex]?.name] || '拍面角点' }}
                    （当前 {{ selectedFaceCornerIndex + 1 }}/4）
                  </div>
                  <div class="keypoint-hint" v-else-if="annotationLayerMode === 'contact_point'">
                    在拍面投影内点击击球接触位置（图像坐标；会反算面参数 u,v）
                  </div>
                  <div class="keypoint-hint" v-else-if="annotationLayerMode === 'contact_shuttle'">
                    点击羽毛球位置；不可见时可跳过
                  </div>
                  <div class="keypoint-actions" style="margin-top: 8px;">
                    <el-button size="small" @click="clearContactGeometry">清除接触几何</el-button>
                  </div>
                </el-form-item>
              </template>

              <el-form-item label="备注">
                <el-input v-model="form.notes" type="textarea" :rows="3" placeholder="可选备注" />
              </el-form-item>

              <el-divider />
              <el-form-item label="标注图层">
                <div class="layer-mode-actions">
                  <el-button :type="annotationLayerMode === 'skeleton' ? 'primary' : undefined" @click="switchToSkeletonMode">人体关键点</el-button>
                  <el-button :type="annotationLayerMode === 'box' ? 'primary' : undefined" @click="startBoxAnnotation">人物边界框</el-button>
                  <el-button plain @click="clearBBox" :disabled="!hasBBox">清除边界框</el-button>
                </div>
                <div class="keypoint-hint" v-if="annotationLayerMode === 'box'">
                  在图像区域按住并拖动指针，释放后完成边界框标注。
                </div>
              </el-form-item>

              <el-divider />
              <el-form-item label="关键点标注（25 点）" v-if="annotationLayerMode === 'skeleton'">
                <div class="keypoint-hint">选择关键点后在图像中定位；可直接拖动已有点进行修正。顶部滑块仅调整显示尺寸，不改变标注坐标。</div>
                <div class="keypoint-buttons">
                  <el-button
                    v-for="(kp, idx) in keypointsList"
                    :key="kp.name"
                    size="small"
                    :type="selectedKeypointIndex === idx ? 'primary' : undefined"
                    :class="{ 'keypoint-btn-set': kp.visibility > 0 }"
                    @click="selectedKeypointIndex = idx"
                  >
                    <span class="keypoint-btn-dot" :style="{ background: KEYPOINT_COLORS[idx] }" />
                    {{ KEYPOINT_LABELS[kp.name] || kp.name }}
                  </el-button>
                </div>
                <div class="keypoint-actions">
                  <el-button size="small" type="primary" :loading="predictingKeypoints" @click="applyPredictKeypoints">
                    运行多人姿态预标注
                  </el-button>
                  <el-button size="small" @click="clearCurrentKeypoint">清除当前点</el-button>
                  <el-button size="small" @click="clearAllKeypoints">清除全部</el-button>
                </div>
                <el-alert v-if="currentAssist" class="assist-panel" :closable="false"
                  :type="currentAssist.review_priority >= 0.65 ? 'warning' : 'success'">
                  <template #title>
                    姿态估计质量控制（Pose Estimation Quality Control） · 规范 {{ taxonomyVersion }} ·
                    估计置信度 {{ percent(currentAssist.confidence) }} · 人工复核优先级 {{ percent(currentAssist.review_priority) }}
                  </template>
                  <div class="assist-detail">
                    <span>建议阶段：{{ currentAssist.suggested_phase ? actionPhaseLabel(currentAssist.suggested_phase) : '不自动判断' }}</span>
                    <span>姿态完整度：{{ Number(currentAssist.features?.quality_energy || 0).toFixed(2) }}</span>
                    <span>预测不确定度：{{ Number(currentAssist.uncertainty || 0).toFixed(2) }}</span>
                  </div>
                  <div class="assist-reasons">通俗解释：置信度表示当前骨架有多可信；不确定度越高、复核优先级越高，就越需要人工检查。</div>
                  <div class="assist-reasons">{{ (currentAssist.reasons || []).join('；') }}</div>
                  <el-button v-if="currentAssist.suggested_phase || currentAssist.suggested_quality"
                    size="small" type="primary" plain @click="acceptAssistSuggestion">采用建议</el-button>
                </el-alert>
              </el-form-item>

              <el-divider />

              <div class="action-buttons">
                <el-button type="primary" @click="saveAnnotation" :loading="saving">
                  {{ currentAnnotation ? '更新标注' : '保存标注' }}
                </el-button>
                <el-button type="success" @click="saveAndNext" :loading="saving">
                  保存并下一帧
                </el-button>
              </div>

              <el-divider />

              <div class="batch-actions">
                <el-button type="warning" @click="submitAll" :loading="submitting" style="width: 100%; margin-bottom: 8px;">
                  提交所有草稿
                </el-button>
                <el-button v-if="canConfirm" type="success" @click="confirmAll" :loading="confirming" style="width: 100%;">
                  确认所有已提交标注
                </el-button>
              </div>
            </el-form>
          </el-col>
        </el-row>
      </template>
    </el-card>

    <el-dialog v-model="showReUpload" title="重新上传" width="500px">
      <p>重新上传将替换当前任务下的所有帧，已有标注会保留帧序号对应关系。</p>
      <template #footer>
        <el-button @click="showReUpload = false">取消</el-button>
        <el-button type="primary" @click="goReUpload">去上传</el-button>
      </template>
    </el-dialog>

      <el-dialog v-model="showPersonSelect" title="全图多人检测结果" width="560px">
        <p>检测到 {{ predictedPersons.length }} 人，已按画面从左到右排列。低置信候选会保留给人工确认：</p>
        <div class="person-select-btns">
        <el-button
          v-for="(person, idx) in predictedPersons"
          :key="idx"
          type="primary"
          plain
          @click="applyPredictedPerson(idx)"
        >
            第 {{ idx + 1 }} 人 · 检测 {{ percent(person.detection_confidence) }}
            · 可见点 {{ person.visible_keypoints }}/23 · {{ person.source === 'yolo-tile' ? '小目标增强' : '全图检测' }}
          </el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { annotationApi, taskApi } from '@/api'
import request from '@/api/request'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import { Picture, UploadFilled } from '@element-plus/icons-vue'
import type { UploadFile, UploadFiles, UploadInstance } from 'element-plus'
import {
  KEYPOINT_NAMES,
  SKELETON_EDGES,
  KEYPOINT_LABELS,
  KEYPOINT_COLORS,
  createEmptyKeypoints,
  keypointsFromApi,
  type KeypointItem,
} from '@/constants/keypoints'
import {
  CONTACT_ZONES,
  FACE_ATTITUDES,
  SUPPORT_FEET,
  ERROR_ATTRIBUTES,
  FACE_CORNER_LABELS,
  emptyContactPayload,
  normalizeContactPayload,
  recomputeContactUv,
  type ContactPayload,
} from '@/constants/contact'

const route = useRoute()
const authStore = useAuthStore()
const batchId = Number(route.params.batchId)
const isStudentAnnotator = computed(() => authStore.role === 'student')

const batchName = ref('')
const totalFrames = ref(0)
const currentFrame = ref(1)
const annotatedCount = ref(0)
const currentAnnotation = ref<any>(null)
const frameAnnotations = ref<any[]>([])
const hiddenAnnotationIds = ref<Set<number>>(new Set())
const frameTimestamps = ref<Record<number, number>>({})
const currentTimestampMs = computed(() => frameTimestamps.value[currentFrame.value] ?? null)
const saving = ref(false)
const submitting = ref(false)
const confirming = ref(false)
const uploading = ref(false)
const loadingImage = ref(false)
const showReUpload = ref(false)

const frameImageUrl = ref<string | null>(null)
const pendingFiles = ref<UploadFile[]>([])
const uploadRef = ref<UploadInstance>()
const VIDEO_CHUNK_SIZE = 8 * 1024 * 1024
const chunkUploadActive = ref(false)
const chunkUploadedCount = ref(0)
const chunkTotalCount = ref(0)
const chunkUploadPercent = ref(0)
const chunkUploadETA = ref('')

const useYoloFilter = ref(false)
const motionPercentile = ref(90)

type PlayerMeta = {
  id?: number
  uuid?: string
  name: string
  subject_code: string
  gender: 'male' | 'female' | ''
  age: number | null
  height_cm: number | null
}

function createEmptyPlayer(): PlayerMeta {
  return { name: '', subject_code: '', gender: '', age: null, height_cm: null }
}

const metadataForm = reactive({
  match_format: '' as 'singles' | 'doubles' | '',
  match_date: '',
  match_name: '',
  players: [createEmptyPlayer()] as PlayerMeta[],
})
const metadataConfirmed = ref(false)
const metadataSaving = ref(false)
const metadataConfirming = ref(false)
const mediaProcessStatus = ref<'idle' | 'queued' | 'processing' | 'completed' | 'failed'>('idle')
const mediaProcessMessage = ref('')
const mediaProcessStartedAt = ref<string | null>(null)
const mediaProcessFinishedAt = ref<string | null>(null)
const mediaProcessPercent = ref<number | null>(null)
const mediaProcessProgressText = ref('')
let mediaStatusPollTimer: number | null = null

const isVideoSelected = computed(
  () =>
    pendingFiles.value.length === 1 &&
    /\.(mp4|avi|mov|mkv|webm|flv)$/i.test(pendingFiles.value[0]?.name || ''),
)
const isMediaProcessing = computed(
  () => mediaProcessStatus.value === 'queued' || mediaProcessStatus.value === 'processing',
)
const hasUploadedMedia = computed(
  () => totalFrames.value > 0 || mediaProcessStatus.value !== 'idle',
)
const metadataReady = computed(() =>
  !!metadataForm.match_date && !!metadataForm.match_name.trim() && !!metadataForm.match_format
  && metadataForm.players.length === expectedPlayerCount.value
  && metadataForm.players.every((p) => !!p.name.trim()),
)
const canAnnotate = computed(
  () => totalFrames.value > 0 && metadataConfirmed.value,
)
const annotationPlayerOptions = computed(() =>
  metadataForm.players
    .map((p, idx) => {
      const id = Number(p.id)
      if (!Number.isFinite(id)) return null
      const name = p.name.trim() || `选手${idx + 1}`
      const tags = [
        p.gender === 'male' ? '男' : p.gender === 'female' ? '女' : '',
        p.age ? `${p.age}岁` : '',
        p.height_cm ? `${p.height_cm}cm` : '',
      ].filter(Boolean)
      const label = tags.length ? `${name}（${tags.join(' / ')}）` : name
      return { id, label }
    })
    .filter((p): p is { id: number; label: string } => !!p),
)
const selectedPlayerLabel = computed(() => {
  const id = form.selected_player_id
  if (!id) return ''
  const found = annotationPlayerOptions.value.find((p) => p.id === id)
  return found?.label || ''
})
const mediaProcessTitle = computed(() => {
  if (mediaProcessStatus.value === 'queued') return '视频已上传，等待后台处理'
  if (mediaProcessStatus.value === 'processing') return '视频正在后台处理中'
  if (mediaProcessStatus.value === 'completed') return '媒体处理完成'
  if (mediaProcessStatus.value === 'failed') return '媒体处理失败'
  return ''
})
const mediaProcessAlertType = computed(() => {
  if (mediaProcessStatus.value === 'failed') return 'error'
  if (mediaProcessStatus.value === 'completed') return 'success'
  return 'info'
})

const form = reactive({
  selected_player_id: null as number | null,
  action_type: '',
  action_phase: '',
  quality_rating: '',
  is_forced_action: false,
  notes: '',
  box_x: null as number | null,
  box_y: null as number | null,
  box_w: null as number | null,
  box_h: null as number | null,
  is_contact_event: false,
})
const expectedPlayerCount = computed(() => metadataForm.match_format === 'doubles' ? 4 : 2)
const playerName = (playerId: number | null) => annotationPlayerOptions.value.find((p) => p.id === playerId)?.label || '未指定人员'
const formatTimestamp = (milliseconds: number) => {
  const total = Math.max(0, Math.round(milliseconds))
  const minutes = Math.floor(total / 60000)
  const seconds = Math.floor((total % 60000) / 1000)
  const millis = total % 1000
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}.${String(millis).padStart(3, '0')}`
}

type TaxonomyOption = { value: string; label: string }
const taxonomy = reactive({
  actions: [] as TaxonomyOption[],
  phases: [] as TaxonomyOption[],
  qualities: [] as TaxonomyOption[],
})
const taxonomyVersion = ref('unknown')
const assistAccepted = ref(false)
let frameOpenedAt = performance.now()

async function loadTaxonomy() {
  const response = await request.get('/config')
  const source = response.data?.annotation_taxonomy
  if (!source?.actions?.length || !source?.phases?.length || !source?.qualities?.length) {
    throw new Error('标注分类配置不可用')
  }
  taxonomy.actions = source.actions
  taxonomy.phases = source.phases
  taxonomy.qualities = source.qualities
  taxonomyVersion.value = String(source.version || 'unknown')
}

const contactForm = reactive<ContactPayload>(emptyContactPayload())
const selectedFaceCornerIndex = ref(0)

const annotationLayerMode = ref<'skeleton' | 'box' | 'contact_face' | 'contact_point' | 'contact_shuttle'>('skeleton')
const isDrawingBox = ref(false)
const draftBox = ref<{ x1: number; y1: number; x2: number; y2: number } | null>(null)
const hasBBox = computed(
  () => form.box_x !== null && form.box_y !== null && form.box_w !== null && form.box_h !== null && form.box_w > 0 && form.box_h > 0,
)

const keypointsList = ref<KeypointItem[]>(createEmptyKeypoints())
const selectedKeypointIndex = ref(0)
const frameImgRef = ref<HTMLImageElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const frameWrapRef = ref<HTMLDivElement | null>(null)
const MIN_FRAME_ZOOM = 0.5
const MAX_FRAME_ZOOM = 4
const FRAME_ZOOM_STEP = 0.1
const storedKeypointSize = Number(window.localStorage.getItem('annotation-keypoint-size-px'))
const keypointSizePx = ref(Number.isFinite(storedKeypointSize) && storedKeypointSize >= 3 && storedKeypointSize <= 14 ? storedKeypointSize : 7)
const frameZoom = ref(1)
const framePanX = ref(0)
const framePanY = ref(0)
const isSpacePressed = ref(false)
const isPanningViewport = ref(false)
const panStartClientX = ref(0)
const panStartClientY = ref(0)
const panStartX = ref(0)
const panStartY = ref(0)
const frameTransformStyle = computed(() => ({
  transform: `translate(${framePanX.value}px, ${framePanY.value}px) scale(${frameZoom.value})`,
  transformOrigin: 'top left',
}))
const draggingPointIndex = ref<number | null>(null)
const predictingKeypoints = ref(false)
const didDragThisPointer = ref(false)
interface AssistResult {
  confidence: number
  uncertainty: number
  review_priority: number
  suggested_phase: string | null
  suggested_quality: string | null
  phase_probabilities: Record<string, number>
  features: Record<string, number | string>
  reasons: string[]
}
type PredictedPerson = {
  keypoints: { name: string; x: number; y: number; visibility: number }[]
  bbox: [number, number, number, number]
  detection_confidence: number
  visible_keypoints: number
  source: string
  assist?: AssistResult
}
const predictedPersons = ref<PredictedPerson[]>([])
const currentAssist = ref<AssistResult | null>(null)
const percent = (value: number) => `${Math.round(Math.max(0, Math.min(1, value || 0)) * 100)}%`
const showPersonSelect = ref(false)

const optionLabel = (options: TaxonomyOption[], value: string) => options.find((item) => item.value === value)?.label || value
const actionTypeLabel = (v: string) => optionLabel(taxonomy.actions, v)
const actionPhaseLabel = (v: string) => optionLabel(taxonomy.phases, v)
const qualityLabel = (v: string) => optionLabel(taxonomy.qualities, v)
const contactZoneLabel = (v: string) => CONTACT_ZONES.find((z) => z.value === v)?.label || v

function onContactEventToggle(val: string | number | boolean) {
  if (val) {
    if (!form.action_phase || form.action_phase === 'impact') {
      form.action_phase = 'contact'
    }
  } else if (annotationLayerMode.value.startsWith('contact')) {
    annotationLayerMode.value = 'skeleton'
  }
}

function switchToContactFaceMode() {
  annotationLayerMode.value = 'contact_face'
  selectedFaceCornerIndex.value = 0
}

function clearContactGeometry() {
  const fresh = emptyContactPayload()
  fresh.tolerance_flag = contactForm.tolerance_flag
  fresh.contact_zone = contactForm.contact_zone
  fresh.face_attitude = contactForm.face_attitude
  fresh.support_foot = contactForm.support_foot
  fresh.error_attributes = [...contactForm.error_attributes]
  Object.assign(contactForm, fresh)
  selectedFaceCornerIndex.value = 0
  drawKeypointsCanvas()
}

function assignContactPayload(src: ContactPayload) {
  contactForm.tolerance_flag = src.tolerance_flag
  contactForm.shuttle = { ...src.shuttle }
  contactForm.face_corners = src.face_corners.map((c) => ({ ...c }))
  contactForm.contact_point = { ...src.contact_point }
  contactForm.contact_uv = { ...src.contact_uv }
  contactForm.contact_zone = src.contact_zone
  contactForm.face_attitude = src.face_attitude
  contactForm.support_foot = src.support_foot
  contactForm.error_attributes = [...src.error_attributes]
}

const canConfirm = computed(() => {
  const role = authStore.user?.role
  return role === 'super_admin' || role === 'admin' || role === 'expert' || role === 'leader'
})

const statusLabels: Record<string, string> = { draft: '草稿', submitted: '已提交', confirmed: '已确认', rejected: '已退回' }
const statusTagTypes: Record<string, string> = { draft: '', submitted: 'warning', confirmed: 'success', rejected: 'danger' }

const statusLabel = computed(() => {
  if (!currentAnnotation.value) return '未标注'
  const s = currentAnnotation.value.status as string
  return statusLabels[s] ?? s
})

const statusTagType = computed(() => {
  if (!currentAnnotation.value) return 'info'
  const s = currentAnnotation.value.status as string
  return statusTagTypes[s] ?? 'info'
})

function applyMediaProcessState(data: any) {
  mediaProcessStatus.value = (data?.media_process_status || 'idle') as typeof mediaProcessStatus.value
  mediaProcessMessage.value = data?.media_process_message || ''
  mediaProcessStartedAt.value = data?.media_process_started_at || null
  mediaProcessFinishedAt.value = data?.media_process_finished_at || null

  if (mediaProcessStatus.value !== 'queued' && mediaProcessStatus.value !== 'processing') {
    mediaProcessPercent.value = null
    mediaProcessProgressText.value = ''
    return
  }

  const msg = mediaProcessMessage.value
  const progressMatch = msg.match(/([\u4e00-\u9fa5A-Za-z]+)\s*(\d+)\s*\/\s*(\d+),\s*(\d+)%/)
  if (!progressMatch) {
    mediaProcessPercent.value = null
    mediaProcessProgressText.value = ''
    return
  }

  const stage = progressMatch[1] || ''
  const current = Number(progressMatch[2])
  const total = Number(progressMatch[3])
  const percent = Number(progressMatch[4])

  mediaProcessPercent.value = Number.isFinite(percent) ? Math.max(0, Math.min(100, percent)) : null
  if (Number.isFinite(current) && Number.isFinite(total) && total > 0) {
    mediaProcessProgressText.value = `${stage} ${current}/${total}`
  } else {
    mediaProcessProgressText.value = ''
  }
}

function applyBatchMetadataState(data: any) {
  metadataForm.match_format = data?.match_format === 'doubles' ? 'doubles' : data?.match_format === 'singles' ? 'singles' : ''
  metadataForm.match_date = data?.match_date || ''
  metadataForm.match_name = data?.match_name || ''
  const players = Array.isArray(data?.players) ? data.players : []
  const normalized = players
    .slice(0, 4)
    .map((p: any) => ({
      id: Number.isInteger(p?.id) ? p.id : undefined,
      uuid: typeof p?.uuid === 'string' ? p.uuid : undefined,
      name: typeof p?.name === 'string' ? p.name : '',
      subject_code: typeof p?.subject_code === 'string' ? p.subject_code : '',
      gender: p?.gender === 'male' || p?.gender === 'female' ? p.gender : '',
      age: Number.isInteger(p?.age) ? p.age : null,
      height_cm: Number.isInteger(p?.height_cm) ? p.height_cm : null,
    }))
  metadataForm.players = normalized.length ? normalized : [createEmptyPlayer()]
  metadataConfirmed.value = !!data?.metadata_confirmed
}

function addPlayer() {
  if (metadataForm.players.length >= expectedPlayerCount.value) return
  metadataForm.players.push(createEmptyPlayer())
}

function onMatchFormatChange() {
  const expected = expectedPlayerCount.value
  while (metadataForm.players.length < expected) metadataForm.players.push(createEmptyPlayer())
  if (metadataForm.players.length > expected) metadataForm.players.splice(expected)
}

function removePlayer(index: number) {
  if (metadataForm.players.length <= 1) {
    metadataForm.players[0] = createEmptyPlayer()
    return
  }
  metadataForm.players.splice(index, 1)
}

function buildMetadataPlayersPayload() {
  return metadataForm.players
    .slice(0, 4)
    .map((p) => ({
      id: Number.isInteger(p.id) ? p.id : undefined,
      uuid: p.uuid || undefined,
      name: p.name.trim() || undefined,
      subject_code: p.subject_code.trim() || undefined,
      gender: p.gender || undefined,
      age: Number.isInteger(p.age) ? p.age ?? undefined : undefined,
      height_cm: Number.isInteger(p.height_cm) ? p.height_cm ?? undefined : undefined,
    }))
    .filter((p) => p.name)
}

function stopMediaStatusPolling() {
  if (mediaStatusPollTimer !== null) {
    window.clearInterval(mediaStatusPollTimer)
    mediaStatusPollTimer = null
  }
}

function startMediaStatusPolling() {
  if (mediaStatusPollTimer !== null) return
  mediaStatusPollTimer = window.setInterval(() => {
    void refreshMediaProcessStatus()
  }, 3000)
}

async function refreshMediaProcessStatus() {
  try {
    const prevStatus = mediaProcessStatus.value
    const res = await taskApi.getMediaProcessStatus(batchId)
    applyMediaProcessState(res.data)
    if (isMediaProcessing.value) {
      return
    }
    stopMediaStatusPolling()
    if (prevStatus !== mediaProcessStatus.value && mediaProcessStatus.value === 'completed') {
      await loadBatchInfo()
      if (canAnnotate.value) {
        await jumpToFirstUnannotatedFrame()
        await loadAnnotation()
      }
      ElMessage.success(mediaProcessMessage.value || '视频处理完成')
    }
    if (prevStatus !== mediaProcessStatus.value && mediaProcessStatus.value === 'failed') {
      ElMessage.error(mediaProcessMessage.value || '视频处理失败')
    }
  } catch {
    stopMediaStatusPolling()
  }
}

async function loadBatchInfo() {
  try {
    const res = await taskApi.get(batchId)
    batchName.value = res.data.name
    applyMediaProcessState(res.data)
    applyBatchMetadataState(res.data)
    const framesRes = await taskApi.getFrames(batchId)
    const frames = (framesRes.data || []) as { frame_index: number; file_path: string; timestamp_ms: number }[]
    frameTimestamps.value = Object.fromEntries(frames.map((frame) => [frame.frame_index, Number(frame.timestamp_ms || 0)]))
    if (frames.length === 0) {
      totalFrames.value = 0
    } else {
      totalFrames.value = res.data.total_frames ?? frames.length
    }
  } catch { /* handled */ }
}

function revokeFrameImageUrl() {
  if (frameImageUrl.value) {
    URL.revokeObjectURL(frameImageUrl.value)
    frameImageUrl.value = null
  }
}

function onImageError() {
  revokeFrameImageUrl()
  loadingImage.value = false
}

async function loadFrameImage() {
  currentAssist.value = null
  if (totalFrames.value < 1 || currentFrame.value < 1) return
  revokeFrameImageUrl()
  loadingImage.value = true
  try {
    const url = taskApi.getFrameImageUrl(batchId, currentFrame.value)
    const res = await request.get(url, { responseType: 'blob' })
    frameImageUrl.value = URL.createObjectURL(res.data)
  } catch { /* handled */ }
  finally { loadingImage.value = false }
}

function clearPersonAnnotationForm(keepPlayer = false) {
  currentAnnotation.value = null
  if (!keepPlayer) form.selected_player_id = null
  form.action_type = ''
  form.action_phase = ''
  form.quality_rating = ''
  form.is_forced_action = false
  form.notes = ''
  form.is_contact_event = false
  assignContactPayload(emptyContactPayload())
  form.box_x = null
  form.box_y = null
  form.box_w = null
  form.box_h = null
  keypointsList.value = createEmptyKeypoints()
  currentAssist.value = null
}

function applyFrameAnnotation(annotation: any) {
  currentAnnotation.value = annotation
  form.selected_player_id = Number.isInteger(annotation.selected_player_id) ? annotation.selected_player_id : null
  form.action_type = annotation.action_type || ''
  form.action_phase = annotation.action_phase || ''
  form.quality_rating = annotation.quality_rating || ''
  form.is_forced_action = !!annotation.is_forced_action
  form.notes = annotation.notes || ''
  form.is_contact_event = !!annotation.is_contact_event
  assignContactPayload(normalizeContactPayload(annotation.contact))
  form.box_x = typeof annotation.box_x === 'number' ? annotation.box_x : null
  form.box_y = typeof annotation.box_y === 'number' ? annotation.box_y : null
  form.box_w = typeof annotation.box_w === 'number' ? annotation.box_w : null
  form.box_h = typeof annotation.box_h === 'number' ? annotation.box_h : null
  keypointsList.value = keypointsFromApi(annotation.keypoints)
  currentAssist.value = annotation.assist_metadata || null
  assistAccepted.value = !!annotation.assist_accepted
}

function selectFrameAnnotation(annotation: any) {
  applyFrameAnnotation(annotation)
  drawKeypointsCanvas()
}

function isAnnotationVisible(annotationId: number) {
  return !hiddenAnnotationIds.value.has(annotationId)
}

function toggleAnnotationVisibility(annotationId: number) {
  const next = new Set(hiddenAnnotationIds.value)
  if (next.has(annotationId)) next.delete(annotationId)
  else next.add(annotationId)
  hiddenAnnotationIds.value = next
  drawKeypointsCanvas()
}

function startNewPersonAnnotation() {
  clearPersonAnnotationForm()
  annotationLayerMode.value = 'box'
  ElMessage.info('请先选择人员身份，再绘制该人物的边界框')
}

function onPlayerSelectionChange(playerId: number) {
  const existing = frameAnnotations.value.find((item) => item.selected_player_id === playerId)
  if (existing) {
    applyFrameAnnotation(existing)
  } else if (currentAnnotation.value?.selected_player_id !== playerId) {
    clearPersonAnnotationForm(true)
    form.selected_player_id = playerId
    annotationLayerMode.value = 'box'
  }
  drawKeypointsCanvas()
}

async function loadAnnotation(preferredPlayerId?: number | null, preferredAnnotationId?: number | null) {
  frameOpenedAt = performance.now()
  assistAccepted.value = false
  try {
    const res = await annotationApi.list(batchId, { frame_index: currentFrame.value })
    frameAnnotations.value = Array.isArray(res.data) ? res.data : []
    hiddenAnnotationIds.value = new Set()
    if (frameAnnotations.value.length > 0) {
      const chosen = frameAnnotations.value.find((item) => item.id === preferredAnnotationId)
        || frameAnnotations.value.find((item) => item.selected_player_id === preferredPlayerId)
        || frameAnnotations.value[0]
      applyFrameAnnotation(chosen)
    } else {
      frameAnnotations.value = []
      clearPersonAnnotationForm()
    }
  } catch { /* handled */ }
  await loadFrameImage()
}

async function loadAnnotatedCount(): Promise<Set<number>> {
  try {
    const res = await annotationApi.list(batchId, { limit: 2000 })
    const frames: Set<number> = new Set((res.data || []).map((a: any) => Number(a.frame_index)))
    annotatedCount.value = frames.size
    return frames
  } catch {
    return new Set<number>()
  }
}

async function jumpToFirstUnannotatedFrame() {
  if (totalFrames.value <= 0) return
  const annotatedFrames = await loadAnnotatedCount()
  let targetFrame = 1
  for (let i = 1; i <= totalFrames.value; i++) {
    if (!annotatedFrames.has(i)) {
      targetFrame = i
      break
    }
  }
  currentFrame.value = targetFrame
}

function getKeypointsPayload() {
  return keypointsList.value.filter((kp) => kp.visibility > 0).map((kp) => ({ name: kp.name, x: kp.x, y: kp.y, visibility: kp.visibility }))
}

async function saveAnnotation() {
  if (!form.selected_player_id) {
    ElMessage.warning('请选择选手')
    return
  }
  if (!form.action_type) {
    ElMessage.warning('请选择动作类型')
    return
  }
  if (!hasBBox.value) {
    ElMessage.warning('请先绘制当前人员的边界框')
    return
  }

  saving.value = true
  try {
    const kpPayload = getKeypointsPayload()
    if (form.is_contact_event) {
      recomputeContactUv(contactForm)
    }
    const contactPayload = form.is_contact_event
      ? JSON.parse(JSON.stringify(contactForm))
      : null
    const provenance = {
      assist_metadata: currentAssist.value ? JSON.parse(JSON.stringify(currentAssist.value)) : null,
      assist_accepted: assistAccepted.value,
      annotation_duration_ms: Math.max(0, Math.round(performance.now() - frameOpenedAt)),
    }
    if (currentAnnotation.value) {
      await annotationApi.update(currentAnnotation.value.id, {
        keypoints: kpPayload.length ? kpPayload : null,
        box_x: form.box_x,
        box_y: form.box_y,
        box_w: form.box_w,
        box_h: form.box_h,
        selected_player_id: form.selected_player_id,
        action_type: form.action_type || null,
        action_phase: form.action_phase || null,
        quality_rating: form.quality_rating || null,
        is_forced_action: form.is_forced_action,
        notes: form.notes || null,
        is_contact_event: form.is_contact_event,
        contact: contactPayload,
        ...provenance,
      })
      ElMessage.success('标注已更新')
    } else {
      await annotationApi.create({
        task_batch_id: batchId,
        frame_index: currentFrame.value,
        keypoints: kpPayload.length ? kpPayload : null,
        box_x: form.box_x,
        box_y: form.box_y,
        box_w: form.box_w,
        box_h: form.box_h,
        selected_player_id: form.selected_player_id,
        action_type: form.action_type || null,
        action_phase: form.action_phase || null,
        quality_rating: form.quality_rating || null,
        is_forced_action: form.is_forced_action,
        notes: form.notes || null,
        is_contact_event: form.is_contact_event,
        contact: contactPayload,
        ...provenance,
      })
      ElMessage.success('标注已保存')
    }
    await loadAnnotation(form.selected_player_id)
    await loadAnnotatedCount()
  } catch { /* handled */ }
  finally { saving.value = false }
}

async function saveAndNext() {
  await saveAnnotation()
  if (currentFrame.value < totalFrames.value) {
    currentFrame.value++
    await loadAnnotation()
  }
}

function prevFrame() {
  if (currentFrame.value > 1) {
    currentFrame.value--
    loadAnnotation()
  }
}

function nextFrame() {
  if (currentFrame.value < totalFrames.value) {
    currentFrame.value++
    loadAnnotation()
  }
}

async function submitAll() {
  submitting.value = true
  try {
    await annotationApi.submit(batchId)
    ElMessage.success('所有草稿已提交')
    await loadAnnotation()
  } catch { /* handled */ }
  finally { submitting.value = false }
}

async function confirmAll() {
  confirming.value = true
  try {
    await annotationApi.confirm({ task_batch_id: batchId })
    ElMessage.success('所有已提交标注已确认')
    await loadAnnotation()
  } catch { /* handled */ }
  finally { confirming.value = false }
}

function onFileChange(_file: UploadFile, fileList: UploadFiles) {
  pendingFiles.value = fileList
}

function generateHash(str: string) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash) + str.charCodeAt(i);
    hash |= 0;
  }
  return "up_" + (hash >>> 0).toString(16).padStart(8, '0');
}

async function uploadVideoInChunks(file: File) {
  const totalChunks = Math.max(1, Math.ceil(file.size / VIDEO_CHUNK_SIZE))
  const rawId = `${file.name}_${file.size}_${file.lastModified}`
  // 使用简单的哈希生成 uploadId 兼容 HTTP 环境
  const uploadId = `${generateHash(file.name)}_${file.size}_${file.lastModified}`.replace(/[^a-zA-Z0-9_\-=+/]/g, '_')
  let finalResponse: any = null

  let uploadedChunks = new Set<number>()
  try {
    const res = await taskApi.getUploadedChunks(batchId, uploadId)
    uploadedChunks = new Set(res.data.uploaded_chunks || [])
  } catch {
    // 获取失败或不存在时忽略
  }

  chunkUploadActive.value = true
  chunkTotalCount.value = totalChunks
  chunkUploadedCount.value = uploadedChunks.size
  chunkUploadPercent.value = Math.min(100, Math.round((uploadedChunks.size / totalChunks) * 100))
  chunkUploadETA.value = '计算中...'

  const startTime = Date.now()
  let newlyUploaded = 0

  for (let index = 0; index < totalChunks; index++) {
    if (uploadedChunks.has(index) && index !== totalChunks - 1) {
      continue
    }

    const start = index * VIDEO_CHUNK_SIZE
    const end = Math.min(start + VIDEO_CHUNK_SIZE, file.size)
    const piece = file.slice(start, end)

    const formData = new FormData()
    formData.append('chunk', piece, file.name)
    formData.append('upload_id', uploadId)
    formData.append('chunk_index', String(index))
    formData.append('total_chunks', String(totalChunks))
    formData.append('original_filename', file.name)
    formData.append('use_yolo_filter', String(useYoloFilter.value))
    if (useYoloFilter.value) {
      formData.append('motion_percentile', String(motionPercentile.value))
    }

    finalResponse = await taskApi.upload(batchId, formData)
    if (!uploadedChunks.has(index)) {
      uploadedChunks.add(index)
    }
    newlyUploaded++
    chunkUploadedCount.value = uploadedChunks.size
    chunkUploadPercent.value = Math.min(100, Math.round((chunkUploadedCount.value / totalChunks) * 100))
    
    const elapsed = (Date.now() - startTime) / 1000
    const avgTimePerChunk = elapsed / newlyUploaded
    const remainingChunks = totalChunks - chunkUploadedCount.value
    if (remainingChunks > 0) {
      const etaSeconds = Math.round(avgTimePerChunk * remainingChunks)
      if (etaSeconds > 60) {
        chunkUploadETA.value = `预计剩余 ${Math.floor(etaSeconds / 60)} 分 ${etaSeconds % 60} 秒`
      } else {
        chunkUploadETA.value = `预计剩余 ${etaSeconds} 秒`
      }
    } else {
      chunkUploadETA.value = '即将完成...'
    }
  }

  return finalResponse
}

async function submitUpload() {
  if (!pendingFiles.value.length || isMediaProcessing.value) return
  const isVideo = pendingFiles.value.length === 1 && /\.(mp4|avi|mov|mkv|webm|flv)$/i.test(pendingFiles.value[0].name || '')
  if (!isVideo) {
    ElMessage.warning('仅支持上传一个视频文件')
    return
  }
  uploading.value = true
  try {
    let res: any
    const video = pendingFiles.value[0].raw
    if (!video) {
      ElMessage.warning('视频文件无效，请重新选择')
      return
    }
    res = await uploadVideoInChunks(video)

    pendingFiles.value = []
    uploadRef.value?.clearFiles()
    if (res.status === 202) {
      mediaProcessStatus.value = 'queued'
      mediaProcessMessage.value = res.data?.message || '视频已上传，正在后台处理中。'
      ElMessage.success(mediaProcessMessage.value)
      startMediaStatusPolling()
      await refreshMediaProcessStatus()
    } else {
      ElMessage.success('上传成功')
      await loadBatchInfo()
      if (canAnnotate.value) {
        await jumpToFirstUnannotatedFrame()
        await loadAnnotation()
      }
    }
  } catch { /* handled */ }
  finally {
    uploading.value = false
    chunkUploadActive.value = false
    chunkUploadedCount.value = 0
    chunkTotalCount.value = 0
    chunkUploadPercent.value = 0
    chunkUploadETA.value = ''
  }
}

async function saveBatchMetadata(showSuccessMessage = true): Promise<boolean> {
  metadataSaving.value = true
  try {
    const players = buildMetadataPlayersPayload()
    const res = await taskApi.updateMetadata(batchId, {
      match_format: metadataForm.match_format || undefined,
      match_date: metadataForm.match_date || undefined,
      match_name: metadataForm.match_name.trim(),
      players,
    })
    applyBatchMetadataState(res.data)
    if (showSuccessMessage) {
      ElMessage.success('元信息已保存，请继续二次确认')
    }
    return true
  } catch {
    // 错误已由 request 拦截器提示
    return false
  } finally {
    metadataSaving.value = false
  }
}

async function confirmBatchMetadata() {
  if (!hasUploadedMedia.value) {
    ElMessage.warning('请先上传媒体，再确认元信息')
    return
  }

  if (!metadataReady.value) {
    ElMessage.warning(`请填写比赛信息及全部 ${expectedPlayerCount.value} 名运动员姓名`)
    return
  }

  metadataConfirming.value = true
  try {
    const saved = await saveBatchMetadata(false)
    if (!saved) return
    const res = await taskApi.confirmMetadata(batchId)
    applyBatchMetadataState(res.data)
    ElMessage.success('元信息确认完成，可以开始标注')
    if (totalFrames.value > 0) {
      await jumpToFirstUnannotatedFrame()
      await loadAnnotation()
    }
  } catch {
    // 错误已由 request 拦截器提示
  } finally {
    metadataConfirming.value = false
  }
}

function goReUpload() {
  showReUpload.value = false
  totalFrames.value = 0
  revokeFrameImageUrl()
  loadBatchInfo()
}

function clampFrameZoom(value: number) {
  return Math.max(MIN_FRAME_ZOOM, Math.min(MAX_FRAME_ZOOM, Number(value.toFixed(2))))
}

function setFrameZoom(value: number) {
  frameZoom.value = clampFrameZoom(value)
  drawKeypointsCanvas()
}

function zoomInFrame() {
  setFrameZoom(frameZoom.value + FRAME_ZOOM_STEP)
}

function zoomOutFrame() {
  setFrameZoom(frameZoom.value - FRAME_ZOOM_STEP)
}

function resetFrameZoom() {
  frameZoom.value = 1
  framePanX.value = 0
  framePanY.value = 0
}

function onFrameWheel(e: WheelEvent) {
  const delta = e.deltaY < 0 ? FRAME_ZOOM_STEP : -FRAME_ZOOM_STEP
  setFrameZoom(frameZoom.value + delta)
}

function endViewportPan() {
  isPanningViewport.value = false
  window.removeEventListener('mousemove', onViewportMouseMove)
  window.removeEventListener('mouseup', onViewportMouseUp)
}

function onViewportMouseMove(e: MouseEvent) {
  if (!isPanningViewport.value) return
  framePanX.value = panStartX.value + (e.clientX - panStartClientX.value)
  framePanY.value = panStartY.value + (e.clientY - panStartClientY.value)
}

function onViewportMouseUp() {
  endViewportPan()
}

function onViewportMouseDown(e: MouseEvent) {
  const byMiddleButton = e.button === 1
  const bySpaceAndLeft = isSpacePressed.value && e.button === 0
  if (!byMiddleButton && !bySpaceAndLeft) return
  e.preventDefault()
  e.stopPropagation()
  isPanningViewport.value = true
  panStartClientX.value = e.clientX
  panStartClientY.value = e.clientY
  panStartX.value = framePanX.value
  panStartY.value = framePanY.value
  window.addEventListener('mousemove', onViewportMouseMove)
  window.addEventListener('mouseup', onViewportMouseUp)
}

function drawKeypointsCanvas() {
  nextTick(() => {
    const canvas = canvasRef.value
    const img = frameImgRef.value
    if (!canvas || !img || !img.complete) return
    const w = img.offsetWidth
    const h = img.offsetHeight
    if (w <= 0 || h <= 0) return
    canvas.width = w
    canvas.height = h
    canvas.style.width = w + 'px'
    canvas.style.height = h + 'px'
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const inverseZoom = 1 / Math.max(frameZoom.value, 0.01)
    ctx.clearRect(0, 0, w, h)

    const layerColors = ['#00d4ff', '#ff8a00', '#d946ef', '#84cc16']
    const drawSavedPersonLayer = (record: any, layerIndex: number) => {
      if (!isAnnotationVisible(record.id) || record.id === currentAnnotation.value?.id) return
      const color = layerColors[layerIndex % layerColors.length]
      const bx = Number(record.box_x); const by = Number(record.box_y)
      const bw = Number(record.box_w); const bh = Number(record.box_h)
      if ([bx, by, bw, bh].every(Number.isFinite) && bw > 0 && bh > 0) {
        const x = bx / 100 * w; const y = by / 100 * h
        ctx.strokeStyle = color
        ctx.lineWidth = 2 * inverseZoom
        ctx.strokeRect(x, y, bw / 100 * w, bh / 100 * h)
        ctx.fillStyle = color
        ctx.font = `${Math.max(8, 12 * inverseZoom)}px "Microsoft YaHei", sans-serif`
        ctx.fillText(playerName(record.selected_player_id), x + 4 * inverseZoom, y + 14 * inverseZoom)
      }
      const points = keypointsFromApi(record.keypoints)
      ctx.strokeStyle = color
      ctx.lineWidth = 1.5 * inverseZoom
      for (const [start, end] of SKELETON_EDGES) {
        const a = points[start]; const b = points[end]
        if (!a || !b || a.visibility <= 0 || b.visibility <= 0) continue
        ctx.beginPath()
        ctx.moveTo(a.x / 100 * w, a.y / 100 * h)
        ctx.lineTo(b.x / 100 * w, b.y / 100 * h)
        ctx.stroke()
      }
      ctx.fillStyle = color
      for (const point of points) {
        if (point.visibility <= 0) continue
        ctx.beginPath()
        ctx.arc(point.x / 100 * w, point.y / 100 * h, keypointSizePx.value * inverseZoom, 0, Math.PI * 2)
        ctx.fill()
      }
    }
    frameAnnotations.value.forEach(drawSavedPersonLayer)
    const currentLayerVisible = !currentAnnotation.value || isAnnotationVisible(currentAnnotation.value.id)

    if (annotationLayerMode.value === 'box') {
      const drawRect = (
        x: number,
        y: number,
        rw: number,
        rh: number,
        style: { stroke: string; fill: string; label: string; dashed?: boolean; point: string },
      ) => {
        const px = (x / 100) * w
        const py = (y / 100) * h
        const pw = (rw / 100) * w
        const ph = (rh / 100) * h

        ctx.fillStyle = style.fill
        ctx.fillRect(px, py, pw, ph)

        ctx.save()
        ctx.shadowColor = style.stroke
        ctx.shadowBlur = 10
        ctx.strokeStyle = style.stroke
        ctx.lineWidth = 3 * inverseZoom
        if (style.dashed) {
          ctx.setLineDash([8, 5])
        } else {
          ctx.setLineDash([])
        }
        ctx.strokeRect(px, py, pw, ph)
        ctx.restore()
        ctx.setLineDash([])

        const anchorR = keypointSizePx.value * inverseZoom
        const corners = [
          [px, py],
          [px + pw, py],
          [px, py + ph],
          [px + pw, py + ph],
        ]
        for (const [cx, cy] of corners) {
          ctx.beginPath()
          ctx.fillStyle = style.point
          ctx.strokeStyle = '#ffffff'
          ctx.lineWidth = 1.5 * inverseZoom
          ctx.arc(cx, cy, anchorR, 0, Math.PI * 2)
          ctx.fill()
          ctx.stroke()
        }

        const labelText = style.label
        ctx.font = '600 12px "Microsoft YaHei", sans-serif'
        const padX = 8
        const labelW = ctx.measureText(labelText).width + padX * 2
        const labelH = 20
        const labelX = px
        const labelY = Math.max(0, py - labelH - 4)
        ctx.fillStyle = style.stroke
        ctx.fillRect(labelX, labelY, labelW, labelH)
        ctx.fillStyle = '#ffffff'
        ctx.fillText(labelText, labelX + padX, labelY + 14)
      }

      if (hasBBox.value && currentLayerVisible) {
        drawRect(form.box_x as number, form.box_y as number, form.box_w as number, form.box_h as number, {
          stroke: '#22c55e',
          fill: 'rgba(34, 197, 94, 0.18)',
          point: '#22c55e',
          label: '人物框',
        })
      }

      if (draftBox.value) {
        const x = Math.min(draftBox.value.x1, draftBox.value.x2)
        const y = Math.min(draftBox.value.y1, draftBox.value.y2)
        const rw = Math.abs(draftBox.value.x2 - draftBox.value.x1)
        const rh = Math.abs(draftBox.value.y2 - draftBox.value.y1)
        drawRect(x, y, rw, rh, {
          stroke: '#f59e0b',
          fill: 'rgba(245, 158, 11, 0.18)',
          point: '#f59e0b',
          label: '框选中',
          dashed: true,
        })
      }
      return
    }

    const kps = currentLayerVisible ? keypointsList.value : []
    ctx.strokeStyle = 'rgba(0, 200, 100, 0.8)'
    ctx.lineWidth = 2 * inverseZoom
    for (const [i, j] of SKELETON_EDGES) {
      if (i >= kps.length || j >= kps.length) continue
      const a = kps[i]
      const b = kps[j]
      if (a.visibility > 0 && b.visibility > 0) {
        const x1 = (a.x / 100) * w
        const y1 = (a.y / 100) * h
        const x2 = (b.x / 100) * w
        const y2 = (b.y / 100) * h
        ctx.beginPath()
        ctx.moveTo(x1, y1)
        ctx.lineTo(x2, y2)
        ctx.stroke()
      }
    }
    for (let i = 0; i < kps.length; i++) {
      const kp = kps[i]
      if (kp.visibility <= 0) continue
      const x = (kp.x / 100) * w
      const y = (kp.y / 100) * h
      const color = KEYPOINT_COLORS[i] || '#409eff'
      ctx.fillStyle = color
      ctx.strokeStyle = i === selectedKeypointIndex.value ? '#ff0' : '#fff'
      ctx.lineWidth = (i === selectedKeypointIndex.value ? 2 : 1) * inverseZoom
      ctx.beginPath()
      const radius = (keypointSizePx.value + (i === selectedKeypointIndex.value ? 2 : 0)) * inverseZoom
      ctx.arc(x, y, radius, 0, Math.PI * 2)
      ctx.fill()
      ctx.stroke()
    }

    if (form.is_contact_event && currentLayerVisible) {
      drawContactOverlay(ctx, w, h)
    }
  })
}

function drawContactOverlay(ctx: CanvasRenderingContext2D, w: number, h: number) {
  const inverseZoom = 1 / Math.max(frameZoom.value, 0.01)
  const pointRadius = keypointSizePx.value * inverseZoom
  const corners = contactForm.face_corners.filter((c) => c.visibility > 0)
  if (corners.length >= 2) {
    const order = ['face_top', 'face_right', 'face_bottom', 'face_left']
    const pts = order
      .map((name) => contactForm.face_corners.find((c) => c.name === name && c.visibility > 0))
      .filter(Boolean) as { x: number; y: number }[]
    if (pts.length >= 3) {
      ctx.beginPath()
      ctx.moveTo((pts[0].x / 100) * w, (pts[0].y / 100) * h)
      for (let i = 1; i < pts.length; i++) {
        ctx.lineTo((pts[i].x / 100) * w, (pts[i].y / 100) * h)
      }
      ctx.closePath()
      ctx.fillStyle = 'rgba(255, 87, 34, 0.18)'
      ctx.strokeStyle = '#ff5722'
      ctx.lineWidth = 2 * inverseZoom
      ctx.fill()
      ctx.stroke()
    }
  }
  for (const c of contactForm.face_corners) {
    if (c.visibility <= 0) continue
    const x = (c.x / 100) * w
    const y = (c.y / 100) * h
    ctx.fillStyle = '#ff5722'
    ctx.strokeStyle = '#fff'
    ctx.lineWidth = 1.5 * inverseZoom
    ctx.beginPath()
    ctx.arc(x, y, pointRadius, 0, Math.PI * 2)
    ctx.fill()
    ctx.stroke()
  }
  const cp = contactForm.contact_point
  if (cp.visibility > 0 && cp.x != null && cp.y != null) {
    const x = (cp.x / 100) * w
    const y = (cp.y / 100) * h
    ctx.strokeStyle = '#e91e63'
    ctx.lineWidth = 2 * inverseZoom
    ctx.beginPath()
    ctx.moveTo(x - pointRadius - 2 * inverseZoom, y)
    ctx.lineTo(x + pointRadius + 2 * inverseZoom, y)
    ctx.moveTo(x, y - pointRadius - 2 * inverseZoom)
    ctx.lineTo(x, y + pointRadius + 2 * inverseZoom)
    ctx.stroke()
    ctx.beginPath()
    ctx.arc(x, y, pointRadius, 0, Math.PI * 2)
    ctx.stroke()
  }
  const sh = contactForm.shuttle
  if (sh.visibility > 0 && sh.x != null && sh.y != null) {
    const x = (sh.x / 100) * w
    const y = (sh.y / 100) * h
    ctx.fillStyle = '#ffeb3b'
    ctx.strokeStyle = '#333'
    ctx.lineWidth = 1.5 * inverseZoom
    ctx.beginPath()
    ctx.arc(x, y, pointRadius, 0, Math.PI * 2)
    ctx.fill()
    ctx.stroke()
  }
}

function onCanvasClick(e: MouseEvent) {
  if (annotationLayerMode.value === 'box') return
  if (didDragThisPointer.value) {
    didDragThisPointer.value = false
    return
  }
  const canvas = canvasRef.value
  if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  const x = Math.max(0, Math.min(100, ((e.clientX - rect.left) / rect.width) * 100))
  const y = Math.max(0, Math.min(100, ((e.clientY - rect.top) / rect.height) * 100))

  if (annotationLayerMode.value === 'contact_face') {
    const idx = selectedFaceCornerIndex.value
    const corner = contactForm.face_corners[idx]
    if (corner) {
      corner.x = Number(x.toFixed(2))
      corner.y = Number(y.toFixed(2))
      corner.visibility = 2
      selectedFaceCornerIndex.value = Math.min(idx + 1, contactForm.face_corners.length - 1)
      recomputeContactUv(contactForm)
      drawKeypointsCanvas()
    }
    return
  }
  if (annotationLayerMode.value === 'contact_point') {
    contactForm.contact_point = { x: Number(x.toFixed(2)), y: Number(y.toFixed(2)), visibility: 2 }
    recomputeContactUv(contactForm)
    drawKeypointsCanvas()
    return
  }
  if (annotationLayerMode.value === 'contact_shuttle') {
    contactForm.shuttle = { x: Number(x.toFixed(2)), y: Number(y.toFixed(2)), visibility: 2 }
    drawKeypointsCanvas()
    return
  }

  const hit = hitTestKeypoint(canvas, e.clientX, e.clientY)
  if (hit >= 0) {
    selectedKeypointIndex.value = hit
    return
  }
  const idx = selectedKeypointIndex.value
  if (idx >= 0 && idx < keypointsList.value.length) {
    keypointsList.value[idx] = {
      ...keypointsList.value[idx],
      x,
      y,
      visibility: 2,
    }
    keypointsList.value = [...keypointsList.value]
    drawKeypointsCanvas()
  }
}

function hitTestKeypoint(canvas: HTMLCanvasElement, clientX: number, clientY: number): number {
  const rect = canvas.getBoundingClientRect()
  const hitRadiusPx = Math.max(10, keypointSizePx.value + 5)
  const kps = keypointsList.value
  for (let i = kps.length - 1; i >= 0; i--) {
    if (kps[i].visibility <= 0) continue
    const pointClientX = rect.left + (kps[i].x / 100) * rect.width
    const pointClientY = rect.top + (kps[i].y / 100) * rect.height
    if (Math.hypot(pointClientX - clientX, pointClientY - clientY) <= hitRadiusPx) return i
  }
  return -1
}

function onCanvasMouseDown(e: MouseEvent) {
  const canvas = canvasRef.value
  if (!canvas) return

  if (annotationLayerMode.value === 'box') {
    const rect = canvas.getBoundingClientRect()
    const x = ((e.clientX - rect.left) / rect.width) * 100
    const y = ((e.clientY - rect.top) / rect.height) * 100
    isDrawingBox.value = true
    draftBox.value = { x1: x, y1: y, x2: x, y2: y }
    drawKeypointsCanvas()
    return
  }

  if (
    annotationLayerMode.value === 'contact_face' ||
    annotationLayerMode.value === 'contact_point' ||
    annotationLayerMode.value === 'contact_shuttle'
  ) {
    return
  }

  didDragThisPointer.value = false
  const rect = canvas.getBoundingClientRect()
  const x = ((e.clientX - rect.left) / rect.width) * 100
  const y = ((e.clientY - rect.top) / rect.height) * 100
  let idx = hitTestKeypoint(canvas, e.clientX, e.clientY)
  if (idx >= 0) {
    draggingPointIndex.value = idx
    selectedKeypointIndex.value = idx
  } else {
    idx = selectedKeypointIndex.value
    if (idx >= 0 && idx < keypointsList.value.length) {
      draggingPointIndex.value = idx
      keypointsList.value[idx] = {
        ...keypointsList.value[idx],
        x: Math.max(0, Math.min(100, x)),
        y: Math.max(0, Math.min(100, y)),
        visibility: 2,
      }
      keypointsList.value = [...keypointsList.value]
      drawKeypointsCanvas()
    }
  }
}

function onCanvasMouseMove(e: MouseEvent) {
  if (annotationLayerMode.value === 'box') {
    if (!isDrawingBox.value || !draftBox.value) return
    const canvas = canvasRef.value
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()
    draftBox.value = {
      ...draftBox.value,
      x2: ((e.clientX - rect.left) / rect.width) * 100,
      y2: ((e.clientY - rect.top) / rect.height) * 100,
    }
    drawKeypointsCanvas()
    return
  }

  if (draggingPointIndex.value === null) return
  didDragThisPointer.value = true
  const canvas = canvasRef.value
  if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  const x = ((e.clientX - rect.left) / rect.width) * 100
  const y = ((e.clientY - rect.top) / rect.height) * 100
  const idx = draggingPointIndex.value
  keypointsList.value[idx] = {
    ...keypointsList.value[idx],
    x: Math.max(0, Math.min(100, x)),
    y: Math.max(0, Math.min(100, y)),
  }
  keypointsList.value = [...keypointsList.value]
  drawKeypointsCanvas()
}

function onCanvasMouseUp() {
  if (annotationLayerMode.value === 'box') {
    if (isDrawingBox.value && draftBox.value) {
      const x = Math.max(0, Math.min(100, Math.min(draftBox.value.x1, draftBox.value.x2)))
      const y = Math.max(0, Math.min(100, Math.min(draftBox.value.y1, draftBox.value.y2)))
      const rw = Math.max(0, Math.min(100, Math.abs(draftBox.value.x2 - draftBox.value.x1)))
      const rh = Math.max(0, Math.min(100, Math.abs(draftBox.value.y2 - draftBox.value.y1)))
      if (rw >= 0.5 && rh >= 0.5) {
        form.box_x = Number(x.toFixed(2))
        form.box_y = Number(y.toFixed(2))
        form.box_w = Number(rw.toFixed(2))
        form.box_h = Number(rh.toFixed(2))
        ElMessage.success('人物框标注完成')
      }
    }
    isDrawingBox.value = false
    draftBox.value = null
    // Stay in box mode after mouse release; user chooses when to switch mode.
    // This avoids accidental keypoint placement caused by the trailing click event.
    drawKeypointsCanvas()
    return
  }

  draggingPointIndex.value = null
}

function startBoxAnnotation() {
  annotationLayerMode.value = 'box'
  draftBox.value = null
  isDrawingBox.value = false
  drawKeypointsCanvas()
}

function switchToSkeletonMode() {
  annotationLayerMode.value = 'skeleton'
  draftBox.value = null
  isDrawingBox.value = false
  drawKeypointsCanvas()
}

function clearBBox() {
  form.box_x = null
  form.box_y = null
  form.box_w = null
  form.box_h = null
  draftBox.value = null
  isDrawingBox.value = false
  drawKeypointsCanvas()
}

function clearCurrentKeypoint() {
  const idx = selectedKeypointIndex.value
  if (idx >= 0 && idx < keypointsList.value.length) {
    keypointsList.value[idx] = { ...keypointsList.value[idx], x: 0, y: 0, visibility: 0 }
    keypointsList.value = [...keypointsList.value]
    drawKeypointsCanvas()
  }
}

function clearAllKeypoints() {
  keypointsList.value = createEmptyKeypoints()
  drawKeypointsCanvas()
}

async function applyPredictKeypoints() {
    if (totalFrames.value < 1 || currentFrame.value < 1) return
    if (!hasBBox.value) {
      ElMessage.warning('请先绘制人物边界框，再运行姿态预标注')
      return
    }
    if (!form.selected_player_id) {
      ElMessage.warning('请先为当前边界框选择人员身份')
      return
    }
  predictingKeypoints.value = true
  predictedPersons.value = []
  currentAssist.value = null
  showPersonSelect.value = false
  try {
      const res = await taskApi.predictKeypoints(batchId, currentFrame.value, {
        x: form.box_x as number, y: form.box_y as number,
        w: form.box_w as number, h: form.box_h as number,
      })
    const persons = res.data?.persons
    if (!Array.isArray(persons) || persons.length === 0) {
      ElMessage.warning('未检测到人体关键点，请确认画面中有人体')
      return
    }
    if (persons.length === 1) {
      keypointsList.value = keypointsFromApi(persons[0].keypoints)
      currentAssist.value = persons[0].assist || null
      drawKeypointsCanvas()
      ElMessage.success('已应用算法骨架，可继续微调或补标球拍等点位')
      return
    }
    predictedPersons.value = persons
    showPersonSelect.value = true
  } catch {
    // 错误已由 request 拦截器提示
  } finally {
    predictingKeypoints.value = false
  }
}

function applyPredictedPerson(personIndex: number) {
  const persons = predictedPersons.value
  if (personIndex >= 0 && personIndex < persons.length) {
    keypointsList.value = keypointsFromApi(persons[personIndex].keypoints)
    currentAssist.value = persons[personIndex].assist || null
    drawKeypointsCanvas()
    ElMessage.success('已应用第 ' + (personIndex + 1) + ' 人骨架，可继续微调或补标球拍')
  }
  showPersonSelect.value = false
  predictedPersons.value = []
}

function acceptAssistSuggestion() {
  if (!currentAssist.value) return
  if (currentAssist.value.suggested_phase) form.action_phase = currentAssist.value.suggested_phase
  if (currentAssist.value.suggested_quality) form.quality_rating = currentAssist.value.suggested_quality
  assistAccepted.value = true
  ElMessage.success('已应用预标注建议，请核验后保存')
}

function onKeydown(e: KeyboardEvent) {
  if (!canAnnotate.value) return
  const target = e.target as HTMLElement
  if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || (target as HTMLInputElement).isContentEditable) return
  if (e.key === ' ') {
    isSpacePressed.value = true
    e.preventDefault()
    return
  }
  if (e.key === 'ArrowLeft') {
    e.preventDefault()
    prevFrame()
  } else if (e.key === 'ArrowRight') {
    e.preventDefault()
    nextFrame()
  } else if (e.key === 's' && (e.ctrlKey || e.metaKey)) {
    e.preventDefault()
    saveAnnotation()
  }
}

function onKeyup(e: KeyboardEvent) {
  if (e.key === ' ') {
    isSpacePressed.value = false
  }
}

watch(currentFrame, () => loadAnnotation())
watch(keypointsList, () => drawKeypointsCanvas(), { deep: true })
watch(keypointSizePx, (value) => {
  window.localStorage.setItem('annotation-keypoint-size-px', String(value))
  drawKeypointsCanvas()
})
watch(
  () => [form.box_x, form.box_y, form.box_w, form.box_h, annotationLayerMode.value],
  () => drawKeypointsCanvas(),
)
onMounted(async () => {
  await loadTaxonomy()
  await loadBatchInfo()
  if (isMediaProcessing.value) {
    startMediaStatusPolling()
  }
  if (canAnnotate.value) {
    const requestedFrame = Number(route.query.frame)
    const requestedAnnotation = Number(route.query.annotation)
    if (Number.isInteger(requestedFrame) && requestedFrame >= 1 && requestedFrame <= totalFrames.value) {
      currentFrame.value = requestedFrame
      await loadAnnotation(null, Number.isInteger(requestedAnnotation) ? requestedAnnotation : null)
    } else {
      await jumpToFirstUnannotatedFrame()
      await loadAnnotation()
    }
  }
  window.addEventListener('keydown', onKeydown)
  window.addEventListener('keyup', onKeyup)
})
onUnmounted(() => {
  stopMediaStatusPolling()
  window.removeEventListener('keydown', onKeydown)
  window.removeEventListener('keyup', onKeyup)
  endViewportPan()
  revokeFrameImageUrl()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header-left, .header-right {
  display: flex;
  align-items: center;
}

.upload-section {
  padding: 24px 0;
}
.upload-area {
  width: 100%;
}
.upload-area :deep(.el-upload-dragger) {
  width: 100%;
  padding: 48px;
}
.upload-icon {
  font-size: 64px;
  color: var(--el-color-primary);
}
.upload-text {
  margin-top: 16px;
  color: #606266;
}
.upload-hint {
  font-size: 12px;
  color: #909399;
  margin-top: 8px;
}
.media-processing-progress {
  margin: -6px 0 16px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #f7fbff;
  border: 1px solid #d9ecff;
}
.media-processing-progress-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  color: #606266;
  margin-bottom: 8px;
}
.media-processing-progress-text {
  margin: 8px 0 0;
  font-size: 12px;
  color: #909399;
}
.yolo-settings-card {
  margin-top: 14px;
  padding: 14px 16px;
  border: 1px solid #d9ecff;
  border-radius: 8px;
  background: linear-gradient(180deg, #f5f9ff 0%, #f8fbff 100%);
}
.yolo-settings-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.yolo-settings-title {
  font-size: 14px;
  font-weight: 600;
  color: #1f2d3d;
}
.yolo-settings-desc {
  margin: 8px 0 0;
  font-size: 12px;
  color: #5f6b7a;
}
.threshold-controls {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.threshold-label {
  font-size: 13px;
  color: #334155;
}
.threshold-preset-group {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.upload-actions {
  margin-top: 16px;
}

.chunk-upload-progress {
  margin: -4px 0 16px;
  padding: 12px 14px;
  border: 1px solid #e6efff;
  border-radius: 8px;
  background: #f8fbff;
}
.chunk-upload-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.chunk-upload-title {
  font-size: 13px;
  font-weight: 600;
  color: #1f2d3d;
}
.chunk-upload-meta {
  font-size: 12px;
  color: #5f6b7a;
}
.chunk-eta {
  margin-left: 8px;
  color: #909399;
}

.metadata-step-card {
  margin-top: 16px;
  padding: 16px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fff;
}
.metadata-step-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.metadata-step-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}
.metadata-step-desc {
  margin: 8px 0 12px;
  font-size: 13px;
  color: #606266;
}
.metadata-form {
  max-width: 560px;
}
.metadata-player-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.metadata-player-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.metadata-player-card {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 10px 12px 2px;
  background: #fcfdff;
}
.metadata-player-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}
.metadata-player-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}
.metadata-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.frame-area {
  border: 2px dashed #dcdfe6;
  border-radius: 8px;
  min-height: 400px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fafafa;
  margin-bottom: 16px;
  position: relative;
}
.frame-zoom-toolbar {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 2;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  max-width: calc(100% - 36px);
  padding: 6px 8px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid #ebeef5;
}
.frame-zoom-text {
  font-size: 12px;
  color: #303133;
  min-width: 72px;
}
.frame-zoom-hint {
  font-size: 12px;
  color: #909399;
}
.frame-wrapper {
  position: relative;
  width: 100%;
  min-height: 400px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.frame-viewport {
  max-width: 100%;
  max-height: 520px;
  overflow: auto;
  cursor: default;
}
.frame-viewport.is-pannable {
  cursor: grab;
}
.frame-viewport.is-panning {
  cursor: grabbing;
}
.frame-img-wrap {
  position: relative;
  display: inline-block;
}
.frame-img {
  display: block;
  max-width: 100%;
  max-height: 500px;
  object-fit: contain;
  vertical-align: top;
}
.keypoints-canvas {
  position: absolute;
  left: 0;
  top: 0;
  pointer-events: auto;
  cursor: crosshair;
}
.keypoint-hint {
  font-size: 12px;
  color: #909399;
  margin-bottom: 10px;
  line-height: 1.4;
}
.keypoint-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.keypoint-buttons .el-button {
  margin: 0;
}
.layer-mode-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.keypoint-btn-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: middle;
}
.keypoint-btn-set {
  font-weight: 600;
}
.annotation-overlay {
  position: absolute;
  left: 0;
  top: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 12px;
}
.overlay-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.overlay-annotator {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.95);
  background: rgba(0, 0, 0, 0.5);
  padding: 4px 8px;
  border-radius: 4px;
  align-self: flex-start;
}
.frame-placeholder {
  text-align: center;
  color: #909399;
}
.frame-placeholder p {
  margin: 8px 0 0;
  font-size: 16px;
}
.frame-hint {
  font-size: 12px !important;
  color: #c0c4cc;
}
.frame-nav {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}
.re-upload-row {
  margin-bottom: 16px;
}
.annotation-form {
  padding: 0 8px;
}
.action-buttons {
  display: flex;
  gap: 8px;
}
.batch-actions {
  margin-top: 8px;
}
.person-select-btns {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}
.image-timestamp {
  position: absolute;
  left: 10px;
  bottom: 10px;
  z-index: 3;
  padding: 4px 8px;
  border-radius: 4px;
  color: #fff;
  background: rgba(0, 0, 0, 0.72);
  font: 600 12px/1.2 ui-monospace, SFMono-Regular, Consolas, monospace;
  pointer-events: none;
}
.frame-timestamp {
  color: #606266;
  font-variant-numeric: tabular-nums;
}
.frame-person-records {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.person-layer-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-width: 180px;
  padding: 4px 7px;
  border: 1px solid #ebeef5;
  border-radius: 5px;
  background: #fafafa;
}
.point-size-label,
.point-size-value {
  font-size: 12px;
  color: #606266;
  white-space: nowrap;
}
.point-size-slider {
  width: 92px;
  margin: 0 5px;
}
.assist-panel {
  margin-top: 12px;
  width: 100%;
}
.assist-detail {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  margin: 6px 0;
  font-size: 12px;
}
.assist-reasons {
  margin-bottom: 8px;
  color: #606266;
  font-size: 12px;
}
</style>
