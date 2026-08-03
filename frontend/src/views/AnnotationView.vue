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
      <el-alert
        v-if="mediaProcessStatus === 'completed' && sourceFrameCount > 0"
        type="info"
        :closable="false"
        :title="`原视频检查：${sourceFrameCount} 帧 / ${sourceFps} FPS / ${sourceDurationText}${sourceResolutionText}；最终抽取 ${totalFrames} 帧`"
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

        <el-collapse v-if="isVideoSelected" v-model="uploadAdvancedPanels" class="optional-settings-collapse">
          <el-collapse-item name="sampling">
            <template #title>
              <span class="optional-settings-title">抽帧设置（可选）</span>
              <el-tag size="small" type="info" effect="plain">默认均匀抽帧</el-tag>
            </template>
            <div class="yolo-settings-card">
              <div class="yolo-settings-head">
                <span class="yolo-settings-title">仅在需要减少相似帧时开启</span>
                <el-switch v-model="useYoloFilter" active-text="启用动作筛选" inactive-text="均匀抽帧" />
              </div>
              <p class="yolo-settings-desc">筛选帧不会删除：系统保留时间戳，进入标注后可随时预览并加回。</p>

              <div v-if="useYoloFilter" class="threshold-controls">
                <span class="threshold-label">动作保留阈值（百分位）</span>
                <el-input-number
                  v-model="motionPercentile"
                  :min="0"
                  :max="100"
                  :step="1"
                  :precision="0"
                  style="width: 160px"
                />
                <div class="threshold-preset-group">
                  <el-button size="small" plain @click="motionPercentile = 60">多保留</el-button>
                  <el-button size="small" plain @click="motionPercentile = 70">平衡</el-button>
                  <el-button size="small" plain @click="motionPercentile = 80">少保留</el-button>
                </div>
              </div>
            </div>
          </el-collapse-item>
        </el-collapse>

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
          {{ metadataProtocolDescription }}
        </p>

        <el-form label-position="top" class="metadata-form">
          <el-form-item label="数据采集场景（必填）">
            <el-radio-group v-model="metadataForm.capture_mode" @change="onCaptureModeChange">
              <el-radio-button value="competition">比赛/远景视频</el-radio-button>
              <el-radio-button value="controlled_training">受控抵近训练</el-radio-button>
            </el-radio-group>
          </el-form-item>

          <div class="metadata-auto-goal">
            <span>标注目标</span>
            <el-tag :type="qualityAnnotationEnabled ? 'warning' : 'info'">
              {{ qualityAnnotationEnabled ? '精细动作质量' : '动作时序 / 战术' }}
            </el-tag>
            <span class="metadata-auto-goal-hint">已根据采集场景自动设置</span>
          </div>

          <el-alert
            :type="metadataForm.annotation_goal === 'technique_quality' ? 'warning' : 'info'"
            :closable="false"
            :title="metadataGoalGuidance"
            show-icon
            style="margin-bottom: 16px;"
          />

          <div class="metadata-advanced-toggle">
            <el-button text type="primary" @click="metadataAdvancedOpen = !metadataAdvancedOpen">
              {{ metadataAdvancedOpen ? '收起高级采集字段' : '展开高级采集字段（可选）' }}
            </el-button>
            <span>普通任务只需填写下方必填项；研究编号、设备与实验说明按需补充。</span>
          </div>

          <el-row :gutter="10">
            <el-col :xs="24" :sm="12">
              <el-form-item label="拍摄视角（必填）">
                <el-select v-model="metadataForm.camera_view" placeholder="选择相对受试者的机位" style="width: 100%">
                  <el-option label="正面" value="front" />
                  <el-option label="背面" value="rear" />
                  <el-option label="左侧" value="left" />
                  <el-option label="右侧" value="right" />
                  <el-option label="左前斜侧" value="front_left" />
                  <el-option label="右前斜侧" value="front_right" />
                  <el-option label="左后斜侧" value="rear_left" />
                  <el-option label="右后斜侧" value="rear_right" />
                  <el-option label="其他" value="other" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col v-show="metadataAdvancedOpen" :xs="24" :sm="12">
              <el-form-item label="机位高度">
                <el-select v-model="metadataForm.camera_height" style="width: 100%">
                  <el-option label="低机位（仰拍）" value="low" />
                  <el-option label="平视机位" value="eye_level" />
                  <el-option label="高机位（俯拍）" value="high" />
                  <el-option label="未知" value="unknown" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="10">
            <el-col v-show="metadataAdvancedOpen" :xs="24" :sm="12">
              <el-form-item label="同次采集会话编号">
                <el-input v-model="metadataForm.capture_session_id" maxlength="64" placeholder="同一动作多视角填写相同编号" />
              </el-form-item>
            </el-col>
            <el-col :xs="24" :sm="12">
              <el-form-item :label="metadataForm.annotation_goal === 'technique_quality' ? '目标动作（必填）' : '目标动作（可选）'">
                <el-input v-model="metadataForm.target_action" maxlength="128" placeholder="例如：正手杀球" />
              </el-form-item>
            </el-col>
          </el-row>

          <el-form-item v-show="metadataAdvancedOpen" label="关键点采集方案">
            <el-radio-group v-model="metadataForm.marker_protocol">
              <el-radio value="video_landmarks">普通视频关键点</el-radio>
              <el-radio value="physical_markers" :disabled="metadataForm.capture_mode !== 'controlled_training' || metadataForm.annotation_goal !== 'technique_quality'">
                实体/反光标记点实验
              </el-radio>
            </el-radio-group>
            <div class="keypoint-hint">实体标记点仅用于实际布点的抵近实验；系统不会从模糊比赛画面虚构这些点。</div>
          </el-form-item>

          <el-form-item v-if="metadataForm.capture_mode === 'competition'" label="比赛类型（必填）">
            <el-radio-group v-model="metadataForm.match_format" @change="onMatchFormatChange">
              <el-radio-button value="singles">单打（2 人）</el-radio-button>
              <el-radio-button value="doubles">双打（4 人）</el-radio-button>
            </el-radio-group>
          </el-form-item>

          <template v-if="metadataForm.capture_mode === 'competition'">
            <el-row :gutter="10">
              <el-col :xs="24" :sm="12">
                <el-form-item label="视频来源链接或编号（必填）">
                  <el-input v-model="metadataForm.source_reference" maxlength="512" placeholder="原视频 URL、赛事官方编号或馆藏编号" />
                </el-form-item>
              </el-col>
              <el-col v-show="metadataAdvancedOpen" :xs="24" :sm="12">
                <el-form-item label="来源平台">
                  <el-input v-model="metadataForm.source_platform" maxlength="64" placeholder="例如：BWF 官方频道" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-alert type="info" :closable="false" title="比赛数据重点记录局面、动作时序和击球后果；球拍或接触不可见时必须标为不可见。" style="margin-bottom: 16px" />
          </template>

          <template v-else>
            <el-row :gutter="10">
              <el-col :xs="24" :sm="12">
                <el-form-item label="训练采集方式（必填）">
                  <el-select v-model="metadataForm.recording_design" placeholder="请选择" style="width: 100%">
                    <el-option label="自然训练" value="natural_training" />
                    <el-option label="指定标准动作" value="prescribed_standard" />
                    <el-option label="指定条件变化" value="prescribed_variation" />
                    <el-option label="混合采集" value="mixed" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="实际拍摄帧率（必填）">
                  <el-input-number v-model="metadataForm.recording_fps" :min="1" :max="1000" :step="1" style="width: 100%" />
                  <div class="keypoint-hint" v-if="sourceFps > 0">系统从原视频检测：{{ sourceFps }} FPS</div>
                </el-form-item>
              </el-col>
              <el-col v-show="metadataAdvancedOpen" :xs="24" :sm="12">
                <el-form-item label="手机型号">
                  <el-input v-model="metadataForm.device_model" maxlength="128" placeholder="例如：iPhone 15 / Mate 70" />
                </el-form-item>
              </el-col>
              <el-col v-show="metadataAdvancedOpen" :xs="24" :sm="12">
                <el-form-item label="喂球方式">
                  <el-select v-model="metadataForm.feed_method" clearable placeholder="请选择" style="width: 100%">
                    <el-option label="教练喂球" value="coach" />
                    <el-option label="发球机" value="machine" />
                    <el-option label="自行启动" value="self" />
                    <el-option label="连续对练" value="rally" />
                    <el-option label="未知" value="unknown" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col v-show="metadataAdvancedOpen" :xs="24" :sm="12">
                <el-form-item label="重复动作组编号">
                  <el-input v-model="metadataForm.repetition_group_id" maxlength="64" placeholder="同一条件重复动作填写相同编号" />
                </el-form-item>
              </el-col>
              <el-col v-show="metadataAdvancedOpen" :xs="24" :sm="12">
                <el-form-item label="桥接视角编号">
                  <el-input v-model="metadataForm.bridge_view_id" maxlength="64" placeholder="同一动作的后方/侧方拍摄填写相同编号" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-alert
              v-if="recordingFpsMismatch"
              type="warning"
              :closable="false"
              :title="`填写帧率 ${metadataForm.recording_fps} 与原视频检测值 ${sourceFps} 不一致，请核对拍摄设置。`"
              style="margin-bottom: 12px"
            />
            <el-form-item v-show="metadataAdvancedOpen" label="指定变化或训练要求">
              <el-input v-model="metadataForm.intended_variation" maxlength="256" placeholder="例如：相同喂球下对比正常到位、稍晚到位、被动击球" />
            </el-form-item>
          </template>

          <el-form-item :label="metadataForm.capture_mode === 'competition' ? '比赛日期（必填）' : '拍摄日期（必填）'">
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
          <el-form-item :label="metadataForm.capture_mode === 'competition' ? '比赛名称（必填）' : '采集任务名称（必填）'">
            <el-input
              v-model="metadataForm.match_name"
              maxlength="256"
              show-word-limit
              :placeholder="metadataForm.capture_mode === 'competition' ? '例如：2026 校际羽毛球联赛' : '例如：正手杀球抵近采集第 1 轮'"
            />
          </el-form-item>

          <div class="metadata-player-head">
            <span>{{ metadataForm.capture_mode === 'competition' ? '选手信息' : '受试者信息' }} · {{ playerCountGuidance }}</span>
            <el-button size="small" type="primary" plain :disabled="metadataForm.players.length >= maxPlayerCount" @click="addPlayer">
              + 添加{{ metadataForm.capture_mode === 'competition' ? '选手' : '受试者' }}
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
                <el-col v-show="metadataAdvancedOpen" :xs="24" :sm="12">
                  <el-form-item label="匿名受试者编码">
                    <el-input v-model="player.subject_code" maxlength="64" placeholder="ATHLETE_001（跨比赛保持一致）" />
                  </el-form-item>
                </el-col>
                <el-col v-show="metadataAdvancedOpen" :xs="24" :sm="12">
                  <el-form-item label="性别（可选）">
                    <el-select v-model="player.gender" clearable placeholder="请选择">
                      <el-option label="男" value="male" />
                      <el-option label="女" value="female" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col v-show="metadataAdvancedOpen" :xs="24" :sm="12">
                  <el-form-item label="年龄（可选）">
                    <el-input-number v-model="player.age" :min="1" :max="99" controls-position="right" style="width: 100%" />
                  </el-form-item>
                </el-col>
                <el-col v-show="metadataAdvancedOpen" :xs="24" :sm="12">
                  <el-form-item label="身高 cm（可选）">
                    <el-input-number v-model="player.height_cm" :min="80" :max="260" controls-position="right" style="width: 100%" />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="12">
                  <el-form-item label="持拍手（建议填写）">
                    <el-select v-model="player.racket_hand" clearable placeholder="请选择拿拍手">
                      <el-option label="右手持拍" value="right" />
                      <el-option label="左手持拍" value="left" />
                    </el-select>
                  </el-form-item>
                </el-col>
              </el-row>
            </div>
          </div>

          <el-form-item v-show="metadataAdvancedOpen" label="拍摄与数据说明">
            <el-input
              v-model="metadataForm.recording_notes"
              type="textarea"
              :rows="3"
              maxlength="512"
              show-word-limit
              placeholder="记录距离、镜头变化、遮挡、动作质量层级或采集异常；不要填写无关个人隐私。"
            />
          </el-form-item>
        </el-form>

        <div class="metadata-actions">
          <el-button type="primary" :loading="metadataConfirming" @click="confirmBatchMetadata">
            保存并开始标注
          </el-button>
          <el-button text :loading="metadataSaving" @click="saveBatchMetadata">暂存，稍后继续</el-button>
        </div>
      </div>

      <template v-else-if="canAnnotate">
        <el-alert
          :type="qualityAnnotationEnabled ? 'warning' : 'info'"
          :closable="false"
          :title="captureProtocolTitle"
          :description="captureProtocolMessage"
          show-icon
          style="margin-bottom: 16px;"
        />
        <el-row :gutter="20">
          <el-col :span="16">
            <div class="frame-area">
              <div class="frame-zoom-toolbar" v-if="frameImageUrl">
                <el-button size="small" @click="zoomOutFrame" :disabled="frameZoom <= MIN_FRAME_ZOOM">-</el-button>
                <el-button size="small" @click="resetFrameZoom" :disabled="frameZoom === 1">重置</el-button>
                <el-button size="small" @click="zoomInFrame" :disabled="frameZoom >= MAX_FRAME_ZOOM">+</el-button>
                <span class="frame-zoom-text">缩放 {{ Math.round(frameZoom * 100) }}%</span>
                <span class="frame-zoom-hint">滚轮缩放；空格/中键拖动</span>
                <span class="point-size-label">人体点</span>
                <el-slider
                  v-model="keypointSizePx"
                  class="point-size-slider"
                  :min="1"
                  :max="4"
                  :step="1"
                  :show-tooltip="true"
                  :format-tooltip="(value: number) => `${value}px`"
                  aria-label="关键点显示尺寸"
                />
                <span class="point-size-value">{{ keypointSizePx }} px</span>
                <span class="point-size-label">框/接触点</span>
                <el-slider
                  v-model="geometryPointSizePx"
                  class="point-size-slider"
                  :min="4"
                  :max="14"
                  :step="1"
                  :show-tooltip="true"
                  :format-tooltip="(value: number) => `${value}px`"
                  aria-label="人物框与接触几何点显示尺寸"
                />
                <span class="point-size-value">{{ geometryPointSizePx }} px</span>
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

            <div class="temporal-context" v-if="previousFrameImageUrl || nextFrameImageUrl">
              <div class="context-caption">时序参考（辅助判断动作与接触，点击可切换）</div>
              <button v-if="previousFrameImageUrl" class="context-frame" type="button" @click="moveToFrame(currentFrame - 1)">
                <img :src="previousFrameImageUrl" alt="上一帧" />
                <span>上一帧 · {{ formatTimestamp(frameTimestamps[currentFrame - 1] || 0) }}</span>
              </button>
              <button v-if="nextFrameImageUrl" class="context-frame" type="button" @click="moveToFrame(currentFrame + 1)">
                <img :src="nextFrameImageUrl" alt="下一帧" />
                <span>下一帧 · {{ formatTimestamp(frameTimestamps[currentFrame + 1] || 0) }}</span>
              </button>
            </div>

            <div class="segment-card">
              <div class="segment-card-head">
                <div>
                  <strong>连续动作片段</strong>
                  <span class="segment-help">用起止帧记录完整动作，不再把同一动作重复复制到每一帧。</span>
                </div>
                <div class="segment-actions">
                  <el-button size="small" :type="segmentStartFrame === null ? 'primary' : 'warning'" @click="markSegmentStart">
                    {{ segmentStartFrame === null ? '设当前帧为起点' : `重新设起点（当前 ${segmentStartFrame}）` }}
                  </el-button>
                  <el-button
                    size="small"
                    type="success"
                    :loading="segmentSaving"
                    :disabled="!canSaveTemporalSegment"
                    @click="saveTemporalSegment"
                  >
                    保存至当前帧
                  </el-button>
                  <el-button v-if="segmentStartFrame !== null" size="small" @click="segmentStartFrame = null">取消</el-button>
                </div>
              </div>
              <div class="segment-guidance">
                ① 右侧选人物和动作　② 动作开始时设起点　③ 移到结束帧并保存。时间戳自动写入。
              </div>
              <div class="segment-quick-fields">
                <span class="segment-quick-label">快速事件（可选）</span>
                <el-select v-model="strokeEvent.context.pressure_state" clearable placeholder="局面压力">
                  <el-option label="主动" value="attacking"/><el-option label="均势" value="neutral"/><el-option label="被迫" value="forced"/><el-option label="未知" value="unknown"/>
                </el-select>
                <el-select v-model="strokeEvent.execution.arrival_state" clearable placeholder="到位状态">
                  <el-option label="提前到位" value="early"/><el-option label="正常到位" value="on_time"/><el-option label="到位偏晚" value="late"/><el-option label="未知" value="unknown"/>
                </el-select>
                <el-select v-model="strokeEvent.outcome.rally_effect" clearable placeholder="回合效果">
                  <el-option label="形成优势" value="advantage"/><el-option label="维持均势" value="neutral"/><el-option label="陷入被动" value="disadvantage"/><el-option label="直接得分" value="winner"/><el-option label="直接失误" value="error"/><el-option label="未知" value="unknown"/>
                </el-select>
              </div>
              <el-collapse class="stroke-event-fields">
                <el-collapse-item title="补充四层事件细节（可选）" name="event-layers">
                  <el-alert
                    :type="qualityAnnotationEnabled ? 'warning' : 'info'"
                    :closable="false"
                    :title="qualityAnnotationEnabled
                      ? '手机训练重点填写动作执行和可见的接触证据；指定动作不等于实际完成质量。'
                      : '比赛远景重点填写来球情境与击球后果；看不清接触时请选择“不可见”。'"
                    style="margin-bottom: 12px"
                  />
                  <div class="event-layer-title">1. 来球情境</div>
                  <el-row :gutter="8">
                    <el-col :xs="24" :sm="8"><el-select v-model="strokeEvent.context.incoming_height" clearable placeholder="来球高度" style="width:100%"><el-option label="低" value="low"/><el-option label="中" value="mid"/><el-option label="高" value="high"/><el-option label="未知" value="unknown"/></el-select></el-col>
                    <el-col :xs="24" :sm="8"><el-select v-model="strokeEvent.context.incoming_depth" clearable placeholder="来球深度" style="width:100%"><el-option label="前场" value="front"/><el-option label="中场" value="mid"/><el-option label="后场" value="rear"/><el-option label="未知" value="unknown"/></el-select></el-col>
                    <el-col :xs="24" :sm="8"><el-select v-model="strokeEvent.context.pressure_state" clearable placeholder="局面压力" style="width:100%"><el-option label="主动" value="attacking"/><el-option label="均势" value="neutral"/><el-option label="被迫" value="forced"/><el-option label="未知" value="unknown"/></el-select></el-col>
                  </el-row>
                  <el-row :gutter="8" class="event-layer-row">
                    <el-col :xs="24" :sm="8"><el-select v-model="strokeEvent.context.incoming_direction" clearable placeholder="来球相对方向" style="width:100%"><el-option label="正手侧" value="forehand"/><el-option label="追身" value="body"/><el-option label="反手侧" value="backhand"/><el-option label="未知" value="unknown"/></el-select></el-col>
                    <el-col :xs="24" :sm="8"><el-select v-model="strokeEvent.context.preparation_time" clearable placeholder="准备时间" style="width:100%"><el-option label="充分" value="sufficient"/><el-option label="受限" value="limited"/><el-option label="明显偏晚" value="very_late"/><el-option label="未知" value="unknown"/></el-select></el-col>
                    <el-col :xs="24" :sm="8"><el-select v-model="strokeEvent.context.balance_before" clearable placeholder="击球前平衡" style="width:100%"><el-option label="稳定" value="stable"/><el-option label="移动中" value="moving"/><el-option label="失衡" value="off_balance"/><el-option label="未知" value="unknown"/></el-select></el-col>
                  </el-row>
                  <div class="event-layer-title">2. 动作执行</div>
                  <el-row :gutter="8">
                    <el-col :xs="24" :sm="8"><el-select v-model="strokeEvent.execution.arrival_state" clearable placeholder="到位状态" style="width:100%"><el-option label="提前到位" value="early"/><el-option label="正常到位" value="on_time"/><el-option label="到位偏晚" value="late"/><el-option label="未知" value="unknown"/></el-select></el-col>
                    <el-col :xs="24" :sm="8"><el-select v-model="strokeEvent.execution.contact_relative_position" clearable placeholder="接触相对身体" style="width:100%"><el-option label="身体前方" value="front"/><el-option label="身体侧方" value="side"/><el-option label="身体后方" value="behind"/><el-option label="未知" value="unknown"/></el-select></el-col>
                    <el-col :xs="24" :sm="8"><el-select v-model="strokeEvent.execution.recovery_quality" clearable placeholder="回位质量" style="width:100%"><el-option label="良好" value="good"/><el-option label="部分完成" value="partial"/><el-option label="较差" value="poor"/><el-option label="未知" value="unknown"/></el-select></el-col>
                  </el-row>
                  <el-row :gutter="8" class="event-layer-row">
                    <el-col :xs="24" :sm="12"><el-input v-model="strokeEvent.execution.movement_pattern" maxlength="64" placeholder="步法/移动模式，例如：并步接交叉步" /></el-col>
                    <el-col :xs="24" :sm="12"><el-select v-model="strokeEvent.execution.landing_stability" clearable placeholder="落地稳定性" style="width:100%"><el-option label="稳定" value="stable"/><el-option label="可恢复" value="recoverable"/><el-option label="不稳定" value="unstable"/><el-option label="未知" value="unknown"/></el-select></el-col>
                  </el-row>
                  <el-select v-model="strokeEvent.execution.error_mechanisms" multiple clearable collapse-tags placeholder="可观察的错误机制（没有证据则不选）" style="width:100%; margin-top:8px">
                    <el-option label="判断/启动偏晚" value="late_start"/><el-option label="移动不到位" value="poor_arrival"/><el-option label="接触点靠后" value="contact_behind"/><el-option label="身体失衡" value="off_balance"/><el-option label="躯干带动不足" value="limited_trunk_rotation"/><el-option label="手臂协同不足" value="arm_coordination"/><el-option label="落地不稳定" value="unstable_landing"/><el-option label="回位偏慢" value="slow_recovery"/>
                  </el-select>
                  <div class="event-layer-title">3. 击球后果</div>
                  <el-row :gutter="8">
                    <el-col :xs="24" :sm="6"><el-select v-model="strokeEvent.outcome.outgoing_height" clearable placeholder="出球高度" style="width:100%"><el-option label="低" value="low"/><el-option label="中" value="mid"/><el-option label="高" value="high"/><el-option label="未知" value="unknown"/></el-select></el-col>
                    <el-col :xs="24" :sm="6"><el-select v-model="strokeEvent.outcome.landing_depth" clearable placeholder="落点深度" style="width:100%"><el-option label="前场" value="front"/><el-option label="中场" value="mid"/><el-option label="后场" value="rear"/><el-option label="出界" value="out"/><el-option label="下网" value="net"/><el-option label="未知" value="unknown"/></el-select></el-col>
                    <el-col :xs="24" :sm="6"><el-select v-model="strokeEvent.outcome.opponent_response" clearable placeholder="对手响应" style="width:100%"><el-option label="对手主动" value="attacking"/><el-option label="均势回球" value="neutral"/><el-option label="对手被迫" value="forced"/><el-option label="未能回球" value="no_return"/><el-option label="未知" value="unknown"/></el-select></el-col>
                    <el-col :xs="24" :sm="6"><el-select v-model="strokeEvent.outcome.rally_effect" clearable placeholder="回合效果" style="width:100%"><el-option label="形成优势" value="advantage"/><el-option label="维持均势" value="neutral"/><el-option label="陷入被动" value="disadvantage"/><el-option label="直接得分" value="winner"/><el-option label="直接失误" value="error"/><el-option label="未知" value="unknown"/></el-select></el-col>
                  </el-row>
                  <div class="event-layer-title">4. 证据与可见性</div>
                  <el-row :gutter="8">
                    <el-col :xs="24" :sm="6"><el-select v-model="strokeEvent.evidence.context_visibility" style="width:100%"><el-option label="情境清晰" value="clear"/><el-option label="情境部分可见" value="partial"/><el-option label="情境未知" value="unknown"/></el-select></el-col>
                    <el-col :xs="24" :sm="6"><el-select v-model="strokeEvent.evidence.contact_visibility" style="width:100%"><el-option label="接触清晰可见" value="clear"/><el-option label="由相邻帧推断" value="inferred"/><el-option label="接触不可见" value="not_visible"/></el-select></el-col>
                    <el-col :xs="24" :sm="6"><el-select v-model="strokeEvent.evidence.outcome_visibility" style="width:100%"><el-option label="后果清晰" value="clear"/><el-option label="后果部分可见" value="partial"/><el-option label="后果未知" value="unknown"/></el-select></el-col>
                    <el-col :xs="24" :sm="6"><el-select v-model="strokeEvent.evidence.basis" style="width:100%"><el-option label="视频直接观察" value="direct_video"/><el-option label="上下帧判断" value="adjacent_frames"/><el-option label="受控训练指令" value="controlled_instruction" :disabled="metadataForm.capture_mode === 'competition'"/><el-option label="专家推断" value="expert_inference"/></el-select></el-col>
                  </el-row>
                  <div class="event-layer-footer">
                    <el-rate v-model="strokeEvent.evidence.confidence" show-text :texts="['很低','较低','一般','较高','很高']"/>
                    <el-checkbox v-model="carryStrokeEventFields">保存后保留本组条件（仅用于同条件重复动作）</el-checkbox>
                    <el-button size="small" plain @click="resetStrokeEvent">清空四层字段</el-button>
                  </div>
                </el-collapse-item>
              </el-collapse>
              <div v-if="currentTemporalSegments.length" class="active-segments">
                <span>当前帧所在片段：</span>
                <el-tag
                  v-for="segment in currentTemporalSegments"
                  :key="segment.id"
                  size="small"
                  :type="segment.status === 'confirmed' ? 'success' : segment.status === 'submitted' ? 'warning' : 'info'"
                >
                  {{ playerName(segment.selected_player_id) }} · {{ actionTypeLabel(segment.action_type) }}
                  · {{ segment.start_frame }}–{{ segment.end_frame }}
                </el-tag>
              </div>
              <el-collapse v-if="temporalSegments.length" class="segment-list">
                <el-collapse-item :title="`已保存片段（${temporalSegments.length}）`" name="segments">
                  <el-table :data="temporalSegments" size="small" max-height="220">
                    <el-table-column label="人物" width="150">
                      <template #default="{ row }">{{ playerName(row.selected_player_id) }}</template>
                    </el-table-column>
                    <el-table-column label="范围" width="150">
                      <template #default="{ row }">
                        {{ row.start_frame }}–{{ row.end_frame }}
                        <div class="segment-time">{{ formatTimestamp(row.start_timestamp_ms) }}–{{ formatTimestamp(row.end_timestamp_ms) }}</div>
                      </template>
                    </el-table-column>
                    <el-table-column label="动作">
                      <template #default="{ row }">
                        {{ actionTypeLabel(row.action_type) }}
                        <span v-if="row.action_phase"> / {{ actionPhaseLabel(row.action_phase) }}</span>
                        <div class="segment-time">{{ temporalSegmentSummary(row) }}</div>
                      </template>
                    </el-table-column>
                    <el-table-column label="状态" width="90">
                      <template #default="{ row }">{{ segmentStatusLabel(row.status) }}</template>
                    </el-table-column>
                    <el-table-column label="操作" width="180">
                      <template #default="{ row }">
                        <el-button link type="primary" @click="moveToFrame(row.start_frame)">起点</el-button>
                        <el-button link type="primary" @click="moveToFrame(row.end_frame)">终点</el-button>
                        <el-button v-if="row.status !== 'confirmed'" link type="danger" @click="deleteTemporalSegment(row)">删除</el-button>
                      </template>
                    </el-table-column>
                  </el-table>
                  <div class="segment-submit-actions">
                    <el-button size="small" type="primary" plain :disabled="!hasDraftSegments" @click="submitTemporalSegments">
                      提交我的片段
                    </el-button>
                    <el-button
                      v-if="isSegmentReviewer"
                      size="small"
                      type="success"
                      plain
                      :disabled="!submittedSegmentIds.length"
                      @click="confirmTemporalSegments"
                    >
                      确认已提交片段
                    </el-button>
                  </div>
                </el-collapse-item>
              </el-collapse>
            </div>

            <div v-if="currentFramePriority || dataValueReport" class="research-assist-toggle">
              <el-button text type="info" @click="researchAssistOpen = !researchAssistOpen">
                {{ researchAssistOpen ? '收起研究辅助' : '研究辅助（可选）' }}
              </el-button>
              <span>不影响正常标注和保存。</span>
            </div>

            <div v-show="researchAssistOpen" class="influence-card" v-if="currentFramePriority">
              <div class="influence-main">
                <span class="influence-title">样本价值建议</span>
                <el-tag :type="priorityTagType">{{ priorityLabel }}</el-tag>
                <span>价值 {{ percent(currentFramePriority.priority) }}</span>
                <span>预计标注 {{ Math.round(currentFramePriority.estimated_cost_seconds) }} 秒</span>
                <el-tag size="small" effect="plain">{{ currentFramePriority.mode === 'gradient_blend' ? '梯度影响融合' : '代理影响' }}</el-tag>
              </div>
              <div class="influence-reasons">推荐依据：{{ currentFramePriority.reasons.join('；') }}</div>
              <div class="influence-components">
                时序新颖 {{ percent(currentFramePriority.components.temporal_novelty) }} ·
                不确定度 {{ percent(currentFramePriority.components.uncertainty) }} ·
                类别稀缺 {{ percent(currentFramePriority.components.class_rarity) }} ·
                修正信号 {{ percent(currentFramePriority.components.correction_signal) }}
              </div>
            </div>

            <div v-show="researchAssistOpen" class="teacher-surrogate-card" v-if="dataValueReport">
              <div class="teacher-surrogate-head">
                <span class="influence-title">数据价值分层评价</span>
                <el-tag :type="dataValueReport.evidence_status === 'validated_observations' ? 'success' : 'warning'">
                  {{ dataValueEvidenceLabel }}
                </el-tag>
                <span>覆盖 {{ percent(dataValueReport.summary.coverage || 0) }}</span>
                <span>待复核 {{ dataValueReport.summary.decision_counts?.review || 0 }}</span>
                <span>优先训练验证 {{ dataValueReport.summary.decision_counts?.prioritize || 0 }}</span>
              </div>
              <div class="teacher-surrogate-note">{{ dataValueReport.interpretation }}</div>
              <div v-if="currentDataValue" class="teacher-surrogate-frame">
                本帧价值假设/成本 {{ percent(currentDataValue.proxy_value_per_cost) }} ·
                质量风险 {{ percent(currentDataValue.quality_risk) }} ·
                信息潜力 {{ percent(currentDataValue.information_potential) }} ·
                新颖度 {{ percent(currentDataValue.novelty) }} ·
                预计成本 {{ Math.round(currentDataValue.estimated_cost_seconds) }} 秒
                <br />
                建议：{{ currentDataValue.decision_reason }} ·
                证据：{{ dataValueItemEvidenceLabel(currentDataValue.evidence_level) }}
              </div>
            </div>

            <div class="frame-nav">
              <el-button :disabled="currentFrame <= 1" @click="prevFrame">上一帧</el-button>
              <el-input-number
                v-model="frameJumpValue"
                :min="1"
                :max="totalFrames"
                size="small"
                style="width: 120px; margin: 0 12px;"
                @change="jumpToFrame"
              />
              <el-button :disabled="currentFrame >= totalFrames" @click="nextFrame">下一帧</el-button>
              <el-button v-if="researchAssistOpen && currentFramePriority" type="primary" plain @click="jumpToHighestPriorityFrame">下一优先帧</el-button>
              <el-button v-if="filteredFrameCandidates.length" type="info" plain @click="openFilteredFrameDialog">
                筛选帧（{{ filteredFrameCandidates.length }}）
              </el-button>
              <el-button :type="currentFrameRejected ? 'success' : 'warning'" plain @click="toggleCurrentFrameRejected">
                {{ currentFrameRejected ? '恢复此帧' : '标记垃圾/重复帧' }}
              </el-button>
              <el-tag v-if="currentFrameRejected" type="danger">此帧已跳过：{{ currentFrameRejectionReason }}</el-tag>
              <span style="margin-left: 16px; color: #909399; font-size: 13px;">
                已标注 {{ annotatedCount }}/{{ totalFrames }} 帧 · 已跳过 {{ rejectedFrameIndices.size }} 帧
              </span>
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
                  <el-button size="small" plain :loading="saving" @click="startNewPersonAnnotation">新增人物</el-button>
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

              <template v-if="!isStudentAnnotator">
                <el-collapse class="expert-fields-collapse">
                  <el-collapse-item title="专家判定字段" name="expert-fields">
                    <el-form-item label="动作阶段">
                      <el-select v-model="form.action_phase" placeholder="由体育专家判定" clearable style="width: 100%;">
                        <el-option v-for="opt in taxonomy.phases" :key="opt.value" :label="opt.label" :value="opt.value" />
                      </el-select>
                    </el-form-item>

                    <el-form-item label="动作质量">
                      <el-select
                        v-model="form.quality_rating"
                        :placeholder="qualityAnnotationEnabled ? '由体育专家判定' : '当前任务不做精细质量结论'"
                        clearable
                        style="width: 100%;"
                        :disabled="!qualityAnnotationEnabled"
                      >
                        <el-option v-for="opt in taxonomy.qualities" :key="opt.value" :label="opt.label" :value="opt.value" />
                      </el-select>
                    </el-form-item>

                    <el-form-item label="受迫性动作">
                      <el-radio-group v-model="form.is_forced_action">
                        <el-radio :label="false">否</el-radio>
                        <el-radio :label="true">是</el-radio>
                      </el-radio-group>
                    </el-form-item>
                  </el-collapse-item>
                </el-collapse>
              </template>

              <el-divider content-position="left">击球接触标注</el-divider>
              <el-alert
                v-if="!qualityAnnotationEnabled"
                type="info"
                :closable="false"
                title="比赛/时序轨只在球拍和球清晰可见时标接触几何；不可见时保留空值，不凭经验猜点。"
                style="margin-bottom: 12px;"
              />
              <el-form-item label="本帧为击球接触事件">
                <el-switch v-model="form.is_contact_event" @change="onContactEventToggle" />
              </el-form-item>
              <template v-if="form.is_contact_event">
                <div class="contact-details-toggle">
                  <el-button text type="primary" @click="contactDetailsOpen = !contactDetailsOpen">
                    {{ contactDetailsOpen ? '收起接触几何' : '展开接触几何（画面清晰时填写）' }}
                  </el-button>
                </div>
                <div v-show="contactDetailsOpen">
                <el-form-item label="接触帧容差（±1 帧）">
                  <el-switch v-model="contactForm.tolerance_flag" />
                </el-form-item>
                <template v-if="!isStudentAnnotator">
                  <el-form-item label="拍面击球区">
                    <el-select v-model="contactForm.contact_zone" clearable placeholder="由体育专家判定" style="width: 100%;">
                      <el-option v-for="z in CONTACT_ZONES" :key="z.value" :label="z.label" :value="z.value" />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="拍面姿态">
                    <el-select v-model="contactForm.face_attitude" clearable placeholder="由体育专家判定" style="width: 100%;">
                      <el-option v-for="a in FACE_ATTITUDES" :key="a.value" :label="a.label" :value="a.value" />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="支撑脚">
                    <el-select v-model="contactForm.support_foot" clearable placeholder="由体育专家判定" style="width: 100%;">
                      <el-option v-for="f in SUPPORT_FEET" :key="f.value" :label="f.label" :value="f.value" />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="技术偏差属性">
                    <el-select v-model="contactForm.error_attributes" multiple clearable placeholder="由体育专家判定" style="width: 100%;">
                      <el-option v-for="e in ERROR_ATTRIBUTES" :key="e.value" :label="e.label" :value="e.value" />
                    </el-select>
                  </el-form-item>
                </template>
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
                </div>
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
              <el-form-item label="人体关键点标注（23 点）" v-if="annotationLayerMode === 'skeleton'">
                <div class="keypoint-hint">预标注仅生成人体点；拍柄/拍头不再作为人体关键点。持拍手在任务元信息中填写，球拍与击球位置使用“接触几何标注”。</div>
                <div class="keypoint-buttons">
                  <el-button
                    v-for="item in visibleBodyKeypointButtons"
                    :key="item.kp.name"
                    size="small"
                    :type="selectedKeypointIndex === item.idx ? 'primary' : undefined"
                    :class="{ 'keypoint-btn-set': item.kp.visibility > 0 }"
                    @click="selectedKeypointIndex = item.idx"
                  >
                    <span class="keypoint-btn-dot" :style="{ background: KEYPOINT_COLORS[item.idx] }" />
                    {{ KEYPOINT_LABELS[item.kp.name] || item.kp.name }}
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
                    YOLO 人体检测 {{ percent(currentAssist.detection_confidence) }} · 动作阶段判断 {{ percent(currentAssist.confidence) }} · 人工复核优先级 {{ percent(currentAssist.review_priority) }}
                  </template>
                  <div class="assist-detail">
                    <span>建议阶段：{{ currentAssist.suggested_phase ? actionPhaseLabel(currentAssist.suggested_phase) : '不自动判断' }}</span>
                    <span>关键点完整度：{{ Number(currentAssist.features?.completeness || 0).toFixed(2) }}</span>
                    <span>预测不确定度：{{ Number(currentAssist.uncertainty || 0).toFixed(2) }}</span>
                  </div>
                  <div class="assist-reasons">说明：YOLO 人体检测衡量人物定位；动作阶段判断衡量单帧阶段分类，两者不是同一个置信度。</div>
                  <div class="assist-reasons">{{ (currentAssist.reasons || []).join('；') }}</div>
                  <el-button v-if="currentAssist.suggested_phase || currentAssist.suggested_quality"
                    size="small" type="primary" plain @click="acceptAssistSuggestion">采用建议</el-button>
                </el-alert>
              </el-form-item>

              <el-divider />

              <div class="action-buttons">
                <el-button type="primary" @click="saveAndNext" :loading="saving">
                  保存并下一帧
                </el-button>
                <el-button @click="saveAnnotation" :loading="saving">
                  {{ currentAnnotation ? '仅更新当前帧' : '仅保存当前帧' }}
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

    <el-dialog v-model="showFilteredFrames" title="按时间戳加回筛选帧" width="860px" @closed="releaseFilteredPreviewUrls">
      <el-alert
        type="info"
        :closable="false"
        title="这些帧只是初始筛选时被隐藏，并未删除。按时间排序预览，点击“加回标注序列”即可恢复。"
        style="margin-bottom: 12px"
      />
      <div class="filtered-frame-grid" v-loading="loadingFilteredPreviews">
        <div v-for="frame in filteredFramePageRows" :key="frame.frame_index" class="filtered-frame-card">
          <img v-if="filteredPreviewUrls[frame.frame_index]" :src="filteredPreviewUrls[frame.frame_index]" />
          <div v-else class="filtered-frame-placeholder">加载预览中</div>
          <div class="filtered-frame-meta">
            <strong>{{ formatTimestamp(frame.timestamp_ms) }}</strong>
            <span>原序号 {{ frame.frame_index }}</span>
          </div>
          <el-button size="small" type="primary" plain @click="restoreFilteredFrame(frame)">加回标注序列</el-button>
        </div>
      </div>
      <el-pagination
        v-if="filteredFrameCandidates.length > filteredPageSize"
        v-model:current-page="filteredPage"
        :page-size="filteredPageSize"
        :total="filteredFrameCandidates.length"
        layout="prev, pager, next"
        style="margin-top: 14px; justify-content: center"
        @current-change="loadFilteredPreviewPage"
      />
      <template #footer><el-button @click="showFilteredFrames = false">关闭</el-button></template>
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
import { annotationApi, segmentApi, taskApi } from '@/api'
import request from '@/api/request'
import { useAuthStore } from '@/stores/auth'
import { ElMessage, ElMessageBox } from 'element-plus'
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
const frameJumpValue = ref(1)
const annotatedCount = ref(0)
const currentAnnotation = ref<any>(null)
const frameAnnotations = ref<any[]>([])
const hiddenAnnotationIds = ref<Set<number>>(new Set())
const frameTimestamps = ref<Record<number, number>>({})
const rejectedFrameIndices = ref(new Set<number>())
const frameRejectionReasons = ref<Record<number, string>>({})
const sourceFrameCount = ref(0)
const sourceFps = ref(0)
const sourceWidth = ref(0)
const sourceHeight = ref(0)
const sourceDurationText = computed(() => formatTimestamp(Number(sourceFrameCount.value / Math.max(sourceFps.value, 0.001) * 1000)))
const sourceResolutionText = computed(() =>
  sourceWidth.value > 0 && sourceHeight.value > 0 ? ` / ${sourceWidth.value}×${sourceHeight.value}` : '',
)
const recordingFpsMismatch = computed(() =>
  metadataForm.capture_mode === 'controlled_training'
  && sourceFps.value > 0
  && !!metadataForm.recording_fps
  && Math.abs(Number(metadataForm.recording_fps) - sourceFps.value) > Math.max(1, sourceFps.value * 0.03),
)
const currentFrameRejected = computed(() => rejectedFrameIndices.value.has(currentFrame.value))
const currentFrameRejectionReason = computed(() => frameRejectionReasons.value[currentFrame.value] || '无标注价值')
type FramePriority = {
  frame_index: number
  priority: number
  influence: number
  estimated_cost_seconds: number
  is_annotated: boolean
  is_rejected: boolean
  phase: string
  mode: 'proxy' | 'gradient_blend'
  reasons: string[]
  components: { temporal_novelty: number; uncertainty: number; class_rarity: number; correction_signal: number; gradient_influence?: number | null }
}
const framePriorities = ref<Record<number, FramePriority>>({})
type DataValueItem = {
  frame_index: number
  selected_player_id?: number | null
  proxy_value_per_cost: number
  quality_risk: number
  information_potential: number
  novelty: number
  estimated_cost_seconds: number
  evidence_level: 'observed_gain' | 'teacher_observed' | 'calibrated_proxy' | 'exploratory_proxy'
  decision: 'review' | 'defer' | 'prioritize' | 'calibrate' | 'regular'
  decision_reason: string
}
type DataValueReport = {
  evidence_status: 'validated_observations' | 'calibrated_proxy' | 'exploratory_proxy'
  interpretation: string
  summary: { coverage?: number; decision_counts?: Record<string, number> }
  items: DataValueItem[]
}
const dataValueReport = ref<DataValueReport | null>(null)
const dataValueByFrame = ref<Record<number, DataValueItem[]>>({})
const currentDataValue = computed(() => {
  const items = dataValueByFrame.value[currentFrame.value] || []
  return items.length ? items.reduce((best, item) => item.proxy_value_per_cost > best.proxy_value_per_cost ? item : best) : null
})
const dataValueEvidenceLabel = computed(() => {
  if (dataValueReport.value?.evidence_status === 'validated_observations') return '已有真实增量训练证据'
  if (dataValueReport.value?.evidence_status === 'calibrated_proxy') return '目标模型已校准代理'
  return '实验性价值假设'
})
function dataValueItemEvidenceLabel(value: DataValueItem['evidence_level']) {
  return {
    observed_gain: '真实增量训练',
    teacher_observed: '目标模型实测 loss',
    calibrated_proxy: '已校准目标模型代理',
    exploratory_proxy: '未校准低成本代理',
  }[value]
}
const currentFramePriority = computed(() => framePriorities.value[currentFrame.value] || null)
const priorityLabel = computed(() => {
  const value = currentFramePriority.value?.priority || 0
  return value >= 0.7 ? '高优先' : value >= 0.4 ? '中优先' : '低优先'
})
const priorityTagType = computed(() => {
  const value = currentFramePriority.value?.priority || 0
  return value >= 0.7 ? 'danger' : value >= 0.4 ? 'warning' : 'info'
})
const currentTimestampMs = computed(() => frameTimestamps.value[currentFrame.value] ?? null)
type TemporalSegment = {
  id: number
  selected_player_id: number
  annotator_id: number
  annotator_name: string
  start_frame: number
  end_frame: number
  start_timestamp_ms: number
  end_timestamp_ms: number
  action_type: string
  action_phase?: string | null
  context?: Record<string, unknown> | null
  execution?: Record<string, unknown> | null
  outcome?: Record<string, unknown> | null
  evidence?: Record<string, unknown> | null
  notes?: string | null
  status: 'draft' | 'submitted' | 'confirmed'
}
const temporalSegments = ref<TemporalSegment[]>([])
const segmentStartFrame = ref<number | null>(null)
const segmentSaving = ref(false)
function emptyStrokeEvent() {
  return {
    context: {
      incoming_height: '', incoming_depth: '', incoming_direction: '', pressure_state: '',
      preparation_time: '', balance_before: '',
    },
    execution: {
      arrival_state: '', movement_pattern: '', contact_relative_position: '', landing_stability: '',
      recovery_quality: '', error_mechanisms: [] as string[],
    },
    outcome: { outgoing_height: '', landing_depth: '', opponent_response: '', rally_effect: '' },
    evidence: {
      context_visibility: 'unknown', contact_visibility: 'not_visible', outcome_visibility: 'unknown',
      confidence: 3, basis: 'direct_video',
    },
  }
}
const strokeEvent = reactive(emptyStrokeEvent())
const carryStrokeEventFields = ref(false)
function resetStrokeEvent() {
  Object.assign(strokeEvent, emptyStrokeEvent())
}
const isSegmentReviewer = computed(() => authStore.hasRole('super_admin', 'admin', 'leader', 'expert'))
const currentTemporalSegments = computed(() =>
  temporalSegments.value.filter(
    (segment) => segment.start_frame <= currentFrame.value && segment.end_frame >= currentFrame.value,
  ),
)
const hasDraftSegments = computed(() =>
  temporalSegments.value.some(
    (segment) => segment.status === 'draft' && segment.annotator_id === authStore.user?.id,
  ),
)
const submittedSegmentIds = computed(() =>
  temporalSegments.value.filter((segment) => segment.status === 'submitted').map((segment) => segment.id),
)
const saving = ref(false)
const submitting = ref(false)
const confirming = ref(false)
const uploading = ref(false)
const loadingImage = ref(false)
const uploadAdvancedPanels = ref<string[]>([])
const metadataAdvancedOpen = ref(false)
const contactDetailsOpen = ref(false)
const researchAssistOpen = ref(false)

const frameImageUrl = ref<string | null>(null)
const previousFrameImageUrl = ref<string | null>(null)
const nextFrameImageUrl = ref<string | null>(null)
const pendingFiles = ref<UploadFile[]>([])
const uploadRef = ref<UploadInstance>()
const VIDEO_CHUNK_SIZE = 8 * 1024 * 1024
const chunkUploadActive = ref(false)
const chunkUploadedCount = ref(0)
const chunkTotalCount = ref(0)
const chunkUploadPercent = ref(0)
const chunkUploadETA = ref('')

const useYoloFilter = ref(false)
const motionPercentile = ref(70)
type FilteredFrameCandidate = { frame_index: number; timestamp_ms: number }
const filteredFrameCandidates = ref<FilteredFrameCandidate[]>([])
const showFilteredFrames = ref(false)
const filteredPage = ref(1)
const filteredPageSize = 12
const filteredPreviewUrls = ref<Record<number, string>>({})
const loadingFilteredPreviews = ref(false)
const filteredFramePageRows = computed(() => {
  const start = (filteredPage.value - 1) * filteredPageSize
  return filteredFrameCandidates.value.slice(start, start + filteredPageSize)
})

type PlayerMeta = {
  id?: number
  uuid?: string
  name: string
  subject_code: string
  gender: 'male' | 'female' | ''
  age: number | null
  height_cm: number | null
  racket_hand: 'left' | 'right' | ''
}

function createEmptyPlayer(): PlayerMeta {
  return { name: '', subject_code: '', gender: '', age: null, height_cm: null, racket_hand: '' }
}

const metadataForm = reactive({
  capture_mode: 'competition' as 'competition' | 'controlled_training',
  annotation_goal: 'action_sequence' as 'action_sequence' | 'technique_quality',
  camera_view: '' as '' | 'front' | 'rear' | 'left' | 'right' | 'front_left' | 'front_right' | 'rear_left' | 'rear_right' | 'other',
  camera_height: 'unknown' as 'low' | 'eye_level' | 'high' | 'unknown',
  capture_session_id: '',
  target_action: '',
  marker_protocol: 'video_landmarks' as 'video_landmarks' | 'physical_markers',
  recording_notes: '',
  source_reference: '',
  source_platform: '',
  device_model: '',
  recording_fps: null as number | null,
  recording_design: '' as '' | 'natural_training' | 'prescribed_standard' | 'prescribed_variation' | 'mixed',
  feed_method: '' as '' | 'coach' | 'machine' | 'self' | 'rally' | 'unknown',
  repetition_group_id: '',
  bridge_view_id: '',
  intended_variation: '',
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
const qualityAnnotationEnabled = computed(() => metadataForm.annotation_goal === 'technique_quality')
const expectedPlayerCount = computed(() => metadataForm.match_format === 'doubles' ? 4 : 2)
const maxPlayerCount = computed(() => metadataForm.capture_mode === 'competition' ? expectedPlayerCount.value : 4)
const playerCountGuidance = computed(() =>
  metadataForm.capture_mode === 'competition'
    ? `${metadataForm.match_format === 'doubles' ? '双打固定 4 人' : '单打固定 2 人'}`
    : '至少 1 人，最多 4 人',
)
const metadataReady = computed(() => {
  const baseReady = !!metadataForm.match_date
    && !!metadataForm.match_name.trim()
    && !!metadataForm.camera_view
    && metadataForm.players.every((p) => !!p.name.trim())
  if (!baseReady) return false
  if (metadataForm.annotation_goal === 'technique_quality' && !metadataForm.target_action.trim()) return false
  if (metadataForm.capture_mode === 'competition') {
    return !!metadataForm.match_format
      && !!metadataForm.source_reference.trim()
      && metadataForm.players.length === expectedPlayerCount.value
  }
  return metadataForm.players.length >= 1
    && metadataForm.players.length <= 4
    && !!metadataForm.recording_design
    && !!metadataForm.recording_fps
})
const metadataProtocolDescription = computed(() =>
  metadataForm.capture_mode === 'competition'
    ? '比赛/远景视频用于动作类别、时序、移动与战术。请填写单打或双打、全部参赛运动员和拍摄视角。'
    : '受控抵近训练用于动作质量与运动学分析。请保留完整动作序列，填写受试者、目标动作、机位和同次采集会话编号。',
)
const metadataGoalGuidance = computed(() =>
  metadataForm.annotation_goal === 'technique_quality'
    ? '精细动作质量必须使用抵近、清晰、连续的视频；远景或遮挡数据只能标“不可见”，不能推测关节、拍面或击球位置。'
    : '动作时序轨关注动作类别、阶段、受迫性、移动与战术，不输出精细生物力学质量结论。',
)
const captureProtocolTitle = computed(() =>
  qualityAnnotationEnabled.value ? '抵近训练质量轨' : '比赛/动作时序轨',
)
const captureProtocolMessage = computed(() =>
  qualityAnnotationEnabled.value
    ? '用于动作阶段、技术质量和可见的球拍接触细节；必须保留完整动作序列，遮挡或模糊处不得猜测。'
    : '用于动作类别、时序、受迫性、移动与战术；不把远景画面用于精细生物力学质量结论。',
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
const canSaveTemporalSegment = computed(() =>
  segmentStartFrame.value !== null
  && !!form.selected_player_id
  && !!form.action_type
  && canAnnotate.value,
)
const playerName = (playerId: number | null) => annotationPlayerOptions.value.find((p) => p.id === playerId)?.label || '未指定人员'
const formatTimestamp = (milliseconds: number) => {
  const total = Math.max(0, Math.round(milliseconds))
  const minutes = Math.floor(total / 60000)
  const seconds = Math.floor((total % 60000) / 1000)
  const millis = total % 1000
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}.${String(millis).padStart(3, '0')}`
}
const segmentStatusLabel = (status: TemporalSegment['status']) => ({
  draft: '草稿',
  submitted: '待确认',
  confirmed: '已确认',
}[status] || status)
function temporalSegmentSummary(segment: TemporalSegment) {
  const context = segment.context || {}
  const execution = segment.execution || {}
  const outcome = segment.outcome || {}
  const evidence = segment.evidence || {}
  const pressureLabels: Record<string, string> = { attacking: '主动', neutral: '均势', forced: '被迫', unknown: '局面未知' }
  const arrivalLabels: Record<string, string> = { early: '提前到位', on_time: '正常到位', late: '到位偏晚', unknown: '到位未知' }
  const effectLabels: Record<string, string> = { advantage: '形成优势', neutral: '维持均势', disadvantage: '陷入被动', winner: '直接得分', error: '直接失误', unknown: '效果未知' }
  const parts = [
    pressureLabels[String(context.pressure_state || '')],
    arrivalLabels[String(execution.arrival_state || '')],
    effectLabels[String(outcome.rally_effect || '')],
    evidence.confidence ? `置信度 ${evidence.confidence}/5` : '',
  ].filter(Boolean)
  return parts.length ? parts.join(' · ') : '四层信息未填写'
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
const visibleBodyKeypointButtons = computed(() => keypointsList.value
  .map((kp, idx) => ({ kp, idx }))
  .filter(({ kp }) => !kp.name.startsWith('racket_')))
const selectedKeypointIndex = ref(0)
const frameImgRef = ref<HTMLImageElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const frameWrapRef = ref<HTMLDivElement | null>(null)
const MIN_FRAME_ZOOM = 0.5
const MAX_FRAME_ZOOM = 4
const FRAME_ZOOM_STEP = 0.1
const storedKeypointSize = Number(window.localStorage.getItem('annotation-keypoint-size-px'))
const keypointSizePx = ref(Number.isFinite(storedKeypointSize) && storedKeypointSize >= 1 && storedKeypointSize <= 4 ? storedKeypointSize : 3)
const storedGeometryPointSize = Number(window.localStorage.getItem('annotation-geometry-point-size-px'))
const geometryPointSizePx = ref(Number.isFinite(storedGeometryPointSize) && storedGeometryPointSize >= 4 && storedGeometryPointSize <= 14 ? storedGeometryPointSize : 7)
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
  detection_confidence?: number
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
const percent = (value?: number) => `${Math.round(Math.max(0, Math.min(1, value || 0)) * 100)}%`
const showPersonSelect = ref(false)

const optionLabel = (options: TaxonomyOption[], value: string) => options.find((item) => item.value === value)?.label || value
const actionTypeLabel = (v: string) => optionLabel(taxonomy.actions, v)
const actionPhaseLabel = (v: string) => optionLabel(taxonomy.phases, v)
const qualityLabel = (v: string) => optionLabel(taxonomy.qualities, v)
const contactZoneLabel = (v: string) => CONTACT_ZONES.find((z) => z.value === v)?.label || v

function onContactEventToggle(val: string | number | boolean) {
  if (val) {
    contactDetailsOpen.value = false
    if (!form.action_phase || form.action_phase === 'impact') {
      form.action_phase = 'contact'
    }
  } else if (annotationLayerMode.value.startsWith('contact')) {
    contactDetailsOpen.value = false
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
  const capture = data?.capture_metadata && typeof data.capture_metadata === 'object' ? data.capture_metadata : {}
  metadataForm.capture_mode = capture.capture_mode === 'controlled_training' ? 'controlled_training' : 'competition'
  metadataForm.annotation_goal = capture.annotation_goal === 'technique_quality' ? 'technique_quality' : 'action_sequence'
  metadataForm.camera_view = ['front', 'rear', 'left', 'right', 'front_left', 'front_right', 'rear_left', 'rear_right', 'other'].includes(capture.camera_view)
    ? capture.camera_view
    : ''
  metadataForm.camera_height = ['low', 'eye_level', 'high', 'unknown'].includes(capture.camera_height)
    ? capture.camera_height
    : 'unknown'
  metadataForm.capture_session_id = typeof capture.capture_session_id === 'string' ? capture.capture_session_id : ''
  metadataForm.target_action = typeof capture.target_action === 'string' ? capture.target_action : ''
  metadataForm.marker_protocol = capture.marker_protocol === 'physical_markers' ? 'physical_markers' : 'video_landmarks'
  metadataForm.recording_notes = typeof capture.recording_notes === 'string' ? capture.recording_notes : ''
  metadataForm.source_reference = typeof capture.source_reference === 'string' ? capture.source_reference : ''
  metadataForm.source_platform = typeof capture.source_platform === 'string' ? capture.source_platform : ''
  metadataForm.device_model = typeof capture.device_model === 'string' ? capture.device_model : ''
  metadataForm.recording_fps = Number.isFinite(Number(capture.recording_fps)) && Number(capture.recording_fps) > 0
    ? Number(capture.recording_fps)
    : null
  metadataForm.recording_design = ['natural_training', 'prescribed_standard', 'prescribed_variation', 'mixed'].includes(capture.recording_design)
    ? capture.recording_design
    : ''
  metadataForm.feed_method = ['coach', 'machine', 'self', 'rally', 'unknown'].includes(capture.feed_method)
    ? capture.feed_method
    : ''
  metadataForm.repetition_group_id = typeof capture.repetition_group_id === 'string' ? capture.repetition_group_id : ''
  metadataForm.bridge_view_id = typeof capture.bridge_view_id === 'string' ? capture.bridge_view_id : ''
  metadataForm.intended_variation = typeof capture.intended_variation === 'string' ? capture.intended_variation : ''
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
      racket_hand: p?.racket_hand === 'left' || p?.racket_hand === 'right' ? p.racket_hand : '',
    }))
  metadataForm.players = normalized.length ? normalized : [createEmptyPlayer()]
  metadataConfirmed.value = !!data?.metadata_confirmed
}

function addPlayer() {
  if (metadataForm.players.length >= maxPlayerCount.value) return
  metadataForm.players.push(createEmptyPlayer())
}

function onCaptureModeChange() {
  if (metadataForm.capture_mode === 'competition') {
    metadataForm.annotation_goal = 'action_sequence'
    metadataForm.marker_protocol = 'video_landmarks'
    if (!metadataForm.match_format) metadataForm.match_format = 'singles'
    metadataForm.source_reference = metadataForm.source_reference || ''
    metadataForm.device_model = ''
    metadataForm.recording_fps = null
    metadataForm.recording_design = ''
    metadataForm.feed_method = ''
    metadataForm.repetition_group_id = ''
    metadataForm.bridge_view_id = ''
    metadataForm.intended_variation = ''
    onMatchFormatChange()
    return
  }
  metadataForm.annotation_goal = 'technique_quality'
  metadataForm.match_format = ''
  metadataForm.source_reference = ''
  metadataForm.source_platform = ''
  if (!metadataForm.recording_fps && sourceFps.value > 0) metadataForm.recording_fps = sourceFps.value
  if (metadataForm.players.length < 1) metadataForm.players.push(createEmptyPlayer())
}

function onMatchFormatChange() {
  if (metadataForm.capture_mode !== 'competition') return
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
      racket_hand: p.racket_hand || undefined,
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
    sourceFrameCount.value = Number(res.data?.selection_metadata?.source_frame_count || 0)
    sourceFps.value = Number(res.data?.selection_metadata?.source_fps || 0)
    sourceWidth.value = Number(res.data?.selection_metadata?.source_width || 0)
    sourceHeight.value = Number(res.data?.selection_metadata?.source_height || 0)
    if (
      metadataForm.capture_mode === 'controlled_training'
      && !metadataForm.recording_fps
      && sourceFps.value > 0
    ) {
      metadataForm.recording_fps = sourceFps.value
    }
    const framesRes = await taskApi.getFrames(batchId)
    const frames = (framesRes.data || []) as { frame_index: number; file_path: string; timestamp_ms: number; is_rejected?: boolean; rejection_reason?: string }[]
    frameTimestamps.value = Object.fromEntries(frames.map((frame) => [frame.frame_index, Number(frame.timestamp_ms || 0)]))
    rejectedFrameIndices.value = new Set(frames.filter((frame) => frame.is_rejected).map((frame) => frame.frame_index))
    frameRejectionReasons.value = Object.fromEntries(frames.filter((frame) => frame.is_rejected).map((frame) => [frame.frame_index, frame.rejection_reason || '无标注价值']))
    filteredFrameCandidates.value = frames
      .filter((frame) => frame.is_rejected && frame.rejection_reason === 'filter_excluded')
      .map((frame) => ({ frame_index: frame.frame_index, timestamp_ms: Number(frame.timestamp_ms || 0) }))
      .sort((left, right) => left.timestamp_ms - right.timestamp_ms)
    if (frames.length === 0) {
      totalFrames.value = 0
    } else {
      totalFrames.value = res.data.total_frames ?? frames.length
    }
    await loadFramePriorities()
    await loadDataValueReport()
    await loadTemporalSegments()
  } catch { /* handled */ }
}

async function loadTemporalSegments() {
  try {
    const response = await segmentApi.list(batchId)
    temporalSegments.value = Array.isArray(response.data) ? response.data as TemporalSegment[] : []
  } catch {
    temporalSegments.value = []
  }
}

function markSegmentStart() {
  if (!form.selected_player_id) {
    ElMessage.warning('请先在右侧选择人物')
    return
  }
  if (!form.action_type) {
    ElMessage.warning('请先选择动作类型')
    return
  }
  segmentStartFrame.value = currentFrame.value
  ElMessage.success(`已记录起点：第 ${currentFrame.value} 帧`)
}

async function saveTemporalSegment() {
  if (!canSaveTemporalSegment.value || segmentStartFrame.value === null || !form.selected_player_id) return
  segmentSaving.value = true
  try {
    const start = Math.min(segmentStartFrame.value, currentFrame.value)
    const end = Math.max(segmentStartFrame.value, currentFrame.value)
    const compactEventLayer = (value: Record<string, unknown>) => Object.fromEntries(
      Object.entries(value).filter(([, item]) => item !== '' && item !== null && item !== undefined),
    )
    await segmentApi.create({
      task_batch_id: batchId,
      selected_player_id: form.selected_player_id,
      start_frame: start,
      end_frame: end,
      action_type: form.action_type,
      action_phase: isStudentAnnotator.value ? undefined : form.action_phase || undefined,
      context: compactEventLayer(strokeEvent.context),
      execution: compactEventLayer(strokeEvent.execution),
      outcome: compactEventLayer(strokeEvent.outcome),
      evidence: { ...strokeEvent.evidence },
    })
    segmentStartFrame.value = null
    if (!carryStrokeEventFields.value) resetStrokeEvent()
    await loadTemporalSegments()
    ElMessage.success(`动作片段 ${start}–${end} 已保存`)
  } catch { /* request interceptor displays the server validation message */ }
  finally {
    segmentSaving.value = false
  }
}

async function submitTemporalSegments() {
  try {
    await segmentApi.submit(batchId)
    await loadTemporalSegments()
    ElMessage.success('我的片段已提交，等待专家确认')
  } catch { /* handled */ }
}

async function confirmTemporalSegments() {
  if (!submittedSegmentIds.value.length) return
  try {
    await segmentApi.confirm(submittedSegmentIds.value)
    await loadTemporalSegments()
    ElMessage.success('已确认提交的连续动作片段')
  } catch { /* handled */ }
}

async function deleteTemporalSegment(segment: TemporalSegment) {
  try {
    await ElMessageBox.confirm(
      `确认删除第 ${segment.start_frame}–${segment.end_frame} 帧的动作片段？`,
      '删除连续动作片段',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
    await segmentApi.delete(segment.id)
    await loadTemporalSegments()
    ElMessage.success('片段已删除')
  } catch {
    // Cancel and request errors require no additional message here.
  }
}

async function loadFramePriorities() {
  if (totalFrames.value < 1) {
    framePriorities.value = {}
    return
  }
  try {
    const res = await taskApi.getFramePriorities(batchId)
    const items = Array.isArray(res.data?.items) ? res.data.items as FramePriority[] : []
    framePriorities.value = Object.fromEntries(items.map((item) => [item.frame_index, item]))
  } catch {
    framePriorities.value = {}
  }
}

async function loadDataValueReport() {
  try {
    const res = await taskApi.getDataValueReport(batchId)
    dataValueReport.value = res.data as DataValueReport
    const grouped: Record<number, DataValueItem[]> = {}
    for (const item of dataValueReport.value?.items || []) {
      ;(grouped[item.frame_index] ||= []).push(item)
    }
    dataValueByFrame.value = grouped
  } catch {
    dataValueReport.value = null
    dataValueByFrame.value = {}
  }
}

function revokeFrameImageUrl() {
  if (frameImageUrl.value) {
    URL.revokeObjectURL(frameImageUrl.value)
    frameImageUrl.value = null
  }
  if (previousFrameImageUrl.value) URL.revokeObjectURL(previousFrameImageUrl.value)
  if (nextFrameImageUrl.value) URL.revokeObjectURL(nextFrameImageUrl.value)
  previousFrameImageUrl.value = null
  nextFrameImageUrl.value = null
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
    const loadContextFrame = async (frameIndex: number) => {
      if (frameIndex < 1 || frameIndex > totalFrames.value) return null
      const response = await request.get(taskApi.getFrameImageUrl(batchId, frameIndex), { responseType: 'blob' })
      return URL.createObjectURL(response.data)
    }
    const [previousUrl, nextUrl] = await Promise.all([
      loadContextFrame(currentFrame.value - 1),
      loadContextFrame(currentFrame.value + 1),
    ])
    previousFrameImageUrl.value = previousUrl
    nextFrameImageUrl.value = nextUrl
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
  markDraftPersisted()
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
  markDraftPersisted()
}

async function selectFrameAnnotation(annotation: any) {
  if (currentAnnotation.value?.id !== annotation.id && hasUnsavedChanges()) {
    const saved = await saveAnnotation(false, true)
    if (!saved) return
    ElMessage.success('当前人物已自动保存')
  }
  const latest = frameAnnotations.value.find((item) => item.id === annotation.id) || annotation
  applyFrameAnnotation(latest)
  showOnlyFrameAnnotation(latest.id)
  drawKeypointsCanvas()
}

function showOnlyFrameAnnotation(annotationId: number | null = null) {
  hiddenAnnotationIds.value = new Set(
    frameAnnotations.value
      .filter((item) => item.id !== annotationId)
      .map((item) => item.id),
  )
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

async function startNewPersonAnnotation() {
  if (hasUnsavedChanges()) {
    const savedPlayerName = playerName(form.selected_player_id)
    const saved = await saveAnnotation(false, true)
    if (!saved) return
    ElMessage.success(`${savedPlayerName}已自动保存`)
  }
  clearPersonAnnotationForm()
  showOnlyFrameAnnotation()
  annotationLayerMode.value = 'box'
  const remainingPlayers = annotationPlayerOptions.value.filter(
    (player) => !frameAnnotations.value.some((item) => item.selected_player_id === player.id),
  )
  if (remainingPlayers.length === 1) {
    form.selected_player_id = remainingPlayers[0].id
    ElMessage.info(`已自动选择${remainingPlayers[0].label}，请绘制该人物的边界框`)
  } else if (remainingPlayers.length === 0) {
    ElMessage.info('本帧所有选手均已有记录，可点击“编辑”继续修改')
  } else {
    ElMessage.info('请选择人员身份，再绘制该人物的边界框')
  }
  markDraftPersisted()
  drawKeypointsCanvas()
}

function onPlayerSelectionChange(playerId: number) {
  const existing = frameAnnotations.value.find((item) => item.selected_player_id === playerId)
  if (existing) {
    applyFrameAnnotation(existing)
    showOnlyFrameAnnotation(existing.id)
  } else if (currentAnnotation.value?.selected_player_id !== playerId) {
    clearPersonAnnotationForm(true)
    form.selected_player_id = playerId
    showOnlyFrameAnnotation()
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
      showOnlyFrameAnnotation(chosen.id)
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
    if (!annotatedFrames.has(i) && !rejectedFrameIndices.value.has(i)) {
      targetFrame = i
      break
    }
  }
  currentFrame.value = targetFrame
}

function getKeypointsPayload() {
  return keypointsList.value.filter((kp) => kp.visibility > 0).map((kp) => ({ name: kp.name, x: kp.x, y: kp.y, visibility: kp.visibility }))
}

const persistedDraftSignature = ref('')

function draftSignature() {
  return JSON.stringify({
    selected_player_id: form.selected_player_id,
    action_type: form.action_type,
    action_phase: form.action_phase,
    quality_rating: form.quality_rating,
    is_forced_action: form.is_forced_action,
    notes: form.notes,
    box: [form.box_x, form.box_y, form.box_w, form.box_h],
    is_contact_event: form.is_contact_event,
    contact: form.is_contact_event ? contactForm : null,
    keypoints: getKeypointsPayload(),
  })
}

function markDraftPersisted() {
  persistedDraftSignature.value = draftSignature()
}

function hasUnsavedChanges() {
  return draftSignature() !== persistedDraftSignature.value
}

async function saveAnnotation(showSuccess = true, reloadCurrent = true): Promise<boolean> {
  if (!form.selected_player_id) {
    ElMessage.warning('请选择选手')
    return false
  }
  if (!form.action_type) {
    ElMessage.warning('请选择动作类型')
    return false
  }
  if (!hasBBox.value) {
    ElMessage.warning('请先绘制当前人员的边界框')
    return false
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
      if (showSuccess) ElMessage.success('标注已更新')
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
      if (showSuccess) ElMessage.success('标注已保存')
    }
    markDraftPersisted()
    if (reloadCurrent) await loadAnnotation(form.selected_player_id)
    await loadAnnotatedCount()
    await loadFramePriorities()
    await loadDataValueReport()
    return true
  } catch {
    ElMessage.error('保存失败，已停留在当前帧，请重试')
    return false
  }
  finally { saving.value = false }
}

async function saveAndNext() {
  await moveToFrame(currentFrame.value + 1, true)
}

async function persistBeforeFrameChange(forceSave = false) {
  if (!canAnnotate.value || (!forceSave && !hasUnsavedChanges())) return true
  const saved = await saveAnnotation(false, false)
  if (saved) ElMessage.success('当前帧已自动保存')
  return saved
}

async function moveToFrame(target: number, forceSave = false) {
  const boundedTarget = Math.max(1, Math.min(totalFrames.value, Math.round(target)))
  if (boundedTarget === currentFrame.value) return
  if (!(await persistBeforeFrameChange(forceSave))) {
    frameJumpValue.value = currentFrame.value
    return
  }
  currentFrame.value = boundedTarget
}

async function prevFrame() {
  let target = currentFrame.value - 1
  while (target > 1 && rejectedFrameIndices.value.has(target)) target--
  await moveToFrame(target)
}

async function nextFrame() {
  let target = currentFrame.value + 1
  while (target < totalFrames.value && rejectedFrameIndices.value.has(target)) target++
  await moveToFrame(target)
}

async function toggleCurrentFrameRejected() {
  if (!currentFrameRejected.value && hasUnsavedChanges()) {
    ElMessage.warning('当前人物有未保存修改，请先保存后再跳过此帧')
    return
  }
  const nextRejected = !currentFrameRejected.value
  try {
    await taskApi.reviewFrame(batchId, currentFrame.value, {
      is_rejected: nextRejected,
      reason: nextRejected ? '重复、模糊或无标注价值' : undefined,
    })
    const nextSet = new Set(rejectedFrameIndices.value)
    if (nextRejected) {
      nextSet.add(currentFrame.value)
      frameRejectionReasons.value = { ...frameRejectionReasons.value, [currentFrame.value]: '重复、模糊或无标注价值' }
      ElMessage.success('已标记为垃圾/重复帧，原图仍保留，可随时恢复')
      if (currentFrame.value < totalFrames.value) await nextFrame()
    } else {
      nextSet.delete(currentFrame.value)
      const reasons = { ...frameRejectionReasons.value }
      delete reasons[currentFrame.value]
      frameRejectionReasons.value = reasons
      ElMessage.success('已恢复此帧')
    }
    rejectedFrameIndices.value = nextSet
    await loadFramePriorities()
  } catch { /* handled */ }
}

function releaseFilteredPreviewUrls() {
  for (const url of Object.values(filteredPreviewUrls.value)) URL.revokeObjectURL(url)
  filteredPreviewUrls.value = {}
}

async function loadFilteredPreviewPage() {
  releaseFilteredPreviewUrls()
  loadingFilteredPreviews.value = true
  try {
    const pairs = await Promise.all(filteredFramePageRows.value.map(async (frame) => {
      const response = await taskApi.getFrameImageBlob(batchId, frame.frame_index)
      return [frame.frame_index, URL.createObjectURL(response.data)] as const
    }))
    filteredPreviewUrls.value = Object.fromEntries(pairs)
  } finally {
    loadingFilteredPreviews.value = false
  }
}

async function openFilteredFrameDialog() {
  filteredPage.value = 1
  showFilteredFrames.value = true
  await loadFilteredPreviewPage()
}

async function restoreFilteredFrame(frame: FilteredFrameCandidate) {
  await taskApi.reviewFrame(batchId, frame.frame_index, { is_rejected: false })
  const nextRejected = new Set(rejectedFrameIndices.value)
  nextRejected.delete(frame.frame_index)
  rejectedFrameIndices.value = nextRejected
  const nextReasons = { ...frameRejectionReasons.value }
  delete nextReasons[frame.frame_index]
  frameRejectionReasons.value = nextReasons
  const previewUrl = filteredPreviewUrls.value[frame.frame_index]
  if (previewUrl) URL.revokeObjectURL(previewUrl)
  const nextPreviews = { ...filteredPreviewUrls.value }
  delete nextPreviews[frame.frame_index]
  filteredPreviewUrls.value = nextPreviews
  filteredFrameCandidates.value = filteredFrameCandidates.value.filter((item) => item.frame_index !== frame.frame_index)
  ElMessage.success(`已加回 ${formatTimestamp(frame.timestamp_ms)} 的帧`)
  await loadFramePriorities()
  if (!filteredFramePageRows.value.length && filteredPage.value > 1) filteredPage.value--
  if (filteredFrameCandidates.value.length) await loadFilteredPreviewPage()
  else showFilteredFrames.value = false
}

async function jumpToHighestPriorityFrame() {
  const candidates = Object.values(framePriorities.value)
    .filter((item) => !item.is_annotated && !item.is_rejected && item.frame_index !== currentFrame.value)
    .sort((left, right) => right.priority - left.priority || left.frame_index - right.frame_index)
  if (!candidates.length) {
    ElMessage.info('没有剩余的未标注推荐帧')
    return
  }
  await moveToFrame(candidates[0].frame_index)
}

async function jumpToFrame(value: number | undefined) {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    frameJumpValue.value = currentFrame.value
    return
  }
  await moveToFrame(value)
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
      match_format: metadataForm.capture_mode === 'competition' ? (metadataForm.match_format || undefined) : null,
      match_date: metadataForm.match_date || undefined,
      match_name: metadataForm.match_name.trim(),
      capture_metadata: {
        capture_mode: metadataForm.capture_mode,
        annotation_goal: metadataForm.annotation_goal,
        camera_view: metadataForm.camera_view || undefined,
        camera_height: metadataForm.camera_height,
        capture_session_id: metadataForm.capture_session_id.trim() || undefined,
        target_action: metadataForm.target_action.trim() || undefined,
        marker_protocol: metadataForm.marker_protocol,
        recording_notes: metadataForm.recording_notes.trim() || undefined,
        source_reference: metadataForm.source_reference.trim() || undefined,
        source_platform: metadataForm.source_platform.trim() || undefined,
        device_model: metadataForm.device_model.trim() || undefined,
        recording_fps: metadataForm.recording_fps || undefined,
        recording_design: metadataForm.recording_design || undefined,
        feed_method: metadataForm.feed_method || undefined,
        repetition_group_id: metadataForm.repetition_group_id.trim() || undefined,
        bridge_view_id: metadataForm.bridge_view_id.trim() || undefined,
        intended_variation: metadataForm.intended_variation.trim() || undefined,
      },
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
    ElMessage.warning(
      metadataForm.capture_mode === 'competition'
        ? `请填写采集协议、比赛信息及全部 ${expectedPlayerCount.value} 名运动员`
        : '请填写采集协议、拍摄信息、目标动作及至少 1 名受试者',
    )
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

    const radiusForPerson = (boxHeightPercent: unknown) => {
      const boxHeight = Number(boxHeightPercent)
      if (!Number.isFinite(boxHeight) || boxHeight <= 0) return keypointSizePx.value * inverseZoom
      const personHeightPx = boxHeight / 100 * h
      return Math.min(keypointSizePx.value, Math.max(1, personHeightPx / 34)) * inverseZoom
    }

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
      const pointRadius = radiusForPerson(record.box_h)
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
        ctx.globalAlpha = point.visibility === 1 ? 0.42 : 0.9
        ctx.arc(point.x / 100 * w, point.y / 100 * h, pointRadius * (point.visibility === 1 ? 0.7 : 1), 0, Math.PI * 2)
        ctx.fill()
        ctx.globalAlpha = 1
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

        const anchorR = geometryPointSizePx.value * inverseZoom
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
    const currentPointRadius = radiusForPerson(form.box_h)
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
      ctx.globalAlpha = kp.visibility === 1 ? 0.42 : 0.9
      const confidenceScale = kp.visibility === 1 ? 0.7 : 1
      const radius = currentPointRadius * confidenceScale + (i === selectedKeypointIndex.value ? 1.5 * inverseZoom : 0)
      ctx.arc(x, y, radius, 0, Math.PI * 2)
      ctx.fill()
      ctx.stroke()
      ctx.globalAlpha = 1
    }

    if (form.is_contact_event && currentLayerVisible) {
      drawContactOverlay(ctx, w, h)
    }
  })
}

function drawContactOverlay(ctx: CanvasRenderingContext2D, w: number, h: number) {
  const inverseZoom = 1 / Math.max(frameZoom.value, 0.01)
  const pointRadius = geometryPointSizePx.value * inverseZoom
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
      currentAssist.value = persons[0].assist ? { ...persons[0].assist, detection_confidence: persons[0].detection_confidence } : null
      drawKeypointsCanvas()
      ElMessage.success('已应用人体骨架，可继续微调关键点')
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
    currentAssist.value = persons[personIndex].assist ? { ...persons[personIndex].assist, detection_confidence: persons[personIndex].detection_confidence } : null
    drawKeypointsCanvas()
    ElMessage.success('已应用第 ' + (personIndex + 1) + ' 人体骨架，可继续微调关键点')
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

watch(currentFrame, (value) => {
  frameJumpValue.value = value
  loadAnnotation()
})
watch(keypointsList, () => drawKeypointsCanvas(), { deep: true })
watch(keypointSizePx, (value) => {
  window.localStorage.setItem('annotation-keypoint-size-px', String(value))
  drawKeypointsCanvas()
})
watch(geometryPointSizePx, (value) => {
  window.localStorage.setItem('annotation-geometry-point-size-px', String(value))
  drawKeypointsCanvas()
})
watch(
  () => [metadataForm.capture_mode, metadataForm.annotation_goal],
  () => {
    if (metadataForm.capture_mode !== 'controlled_training' || metadataForm.annotation_goal !== 'technique_quality') {
      metadataForm.marker_protocol = 'video_landmarks'
    }
    if (!qualityAnnotationEnabled.value) {
      form.quality_rating = ''
    }
  },
)
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
  releaseFilteredPreviewUrls()
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
.optional-settings-collapse {
  margin-top: 14px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 0 14px;
}
.optional-settings-title {
  margin-right: 10px;
  font-weight: 600;
  color: #303133;
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
.metadata-auto-goal {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  font-size: 13px;
  color: #303133;
}
.metadata-auto-goal-hint,
.metadata-advanced-toggle span,
.research-assist-toggle span {
  color: #909399;
  font-size: 12px;
}
.metadata-advanced-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: -4px 0 12px;
  flex-wrap: wrap;
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
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}
.temporal-context {
  display: flex;
  gap: 10px;
  align-items: stretch;
  margin: 12px 0;
  padding: 10px;
  border: 1px solid #d9ecff;
  border-radius: 8px;
  background: #f5faff;
}
.context-caption {
  width: 130px;
  color: #606266;
  font-size: 12px;
  align-self: center;
}
.context-frame {
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  background: #fff;
  padding: 5px 8px;
  cursor: pointer;
  color: #606266;
}
.context-frame img {
  width: 150px;
  height: 84px;
  object-fit: cover;
  border-radius: 4px;
}
.segment-card {
  margin: 10px 0 12px;
  padding: 12px;
  border: 1px solid #b3d8ff;
  border-radius: 8px;
  background: #f7fbff;
  color: #606266;
  font-size: 12px;
}
.segment-card-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}
.segment-help {
  margin-left: 10px;
  color: #909399;
  font-weight: 400;
}
.segment-actions,
.active-segments,
.segment-submit-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.segment-guidance {
  margin-top: 8px;
  color: #64748b;
}
.segment-quick-fields {
  display: grid;
  grid-template-columns: auto repeat(3, minmax(110px, 1fr));
  gap: 8px;
  align-items: center;
  margin-top: 10px;
}
.segment-quick-label {
  color: #303133;
  font-weight: 600;
}
.stroke-event-fields {
  margin-top: 10px;
}
.event-layer-title {
  margin: 10px 0 7px;
  color: #303133;
  font-weight: 600;
}
.event-layer-row {
  margin-top: 8px;
}
.event-layer-footer {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed #dcdfe6;
}
.active-segments {
  margin-top: 10px;
}
.segment-list {
  margin-top: 8px;
}
.segment-time {
  color: #909399;
  font-size: 11px;
}
.segment-submit-actions {
  justify-content: flex-end;
  padding-top: 10px;
}
.research-assist-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 4px 0 8px;
}
.influence-card {
  margin: 10px 0 12px;
  padding: 10px 12px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fafafa;
  color: #606266;
  font-size: 12px;
}
.influence-main {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}
.influence-title {
  color: #303133;
  font-weight: 600;
}
.influence-reasons {
  margin-top: 7px;
  color: #303133;
}
.influence-components {
  margin-top: 5px;
  color: #909399;
}

.teacher-surrogate-card {
  margin-top: 10px;
  padding: 10px 12px;
  border: 1px solid #f0c36a;
  border-radius: 8px;
  background: #fffaf0;
  font-size: 12px;
  color: #606266;
}
.teacher-surrogate-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.teacher-surrogate-note {
  margin-top: 6px;
  color: #8a6508;
}
.teacher-surrogate-frame {
  margin-top: 6px;
  color: #303133;
}
.filtered-frame-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  min-height: 180px;
}
.filtered-frame-card {
  padding: 8px;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  background: #fafafa;
}
.filtered-frame-card img,
.filtered-frame-placeholder {
  width: 100%;
  height: 125px;
  object-fit: cover;
  border-radius: 5px;
  background: #ebeef5;
}
.filtered-frame-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #909399;
  font-size: 12px;
}
.filtered-frame-meta {
  display: flex;
  justify-content: space-between;
  margin: 7px 0;
  color: #606266;
  font-size: 12px;
}
.annotation-form {
  padding: 0 8px;
}
.expert-fields-collapse {
  margin-bottom: 10px;
}
.contact-details-toggle {
  margin: -8px 0 8px;
}
.action-buttons {
  display: flex;
  gap: 8px;
}
.action-buttons .el-button:first-child {
  flex: 1;
}
@media (max-width: 900px) {
  .segment-quick-fields {
    grid-template-columns: 1fr;
  }
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
