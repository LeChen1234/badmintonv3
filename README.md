# 羽毛球训练动作数据集标注系统

基于 Label Studio 的羽毛球训练动作数据集标注平台，支持大模型自动化初标、学生协作标注、三级核对校验。

## 系统架构

| 组件 | 技术栈 | 端口 | 说明 |
|------|--------|------|------|
| Label Studio | Label Studio OSS | 8080 | 标注编辑平台 |
| ML Backend | label-studio-ml-backend | 9090 | 自动标注服务（姿态估计 + 动作识别） |
| 管理后端 | FastAPI + SQLAlchemy | 8000 | RBAC / 任务分配 / 审核流程 / 数据导出 |
| 管理前端 | Vue 3 + Element Plus | 3000 | 管理仪表盘 |
| 数据库 | PostgreSQL 16 | 5432 | 标注数据 + 业务数据 |
| 对象存储 | MinIO | 9000/9001 | 视频帧 / 骨架图 |
| 缓存 | Redis 7 | 6379 | 任务队列 / 缓存 |

## 快速开始

```bash
# 1. 复制环境变量文件并修改（也可用 examples/env.minimal.sample）
cp .env.example .env
# 编辑 .env，至少设置 LABEL_STUDIO_API_KEY（见下方说明）

# 2. 启动全部服务
docker-compose up -d

# 3. 数据库迁移（首次必做）
cd backend && alembic upgrade head && cd ..

# 4. 初始化平台（创建 LS 项目、用户等；需先在 http://localhost:8080 创建 API Token 并填入 .env）
python scripts/init_platform.py

# 5. 导入测试数据
python scripts/generate_mock_data.py
```

- **样例配置与 API 示例**：见 [examples/](examples/) 目录（含 `env.minimal.sample`、`api-examples.http`）。
- **完整使用演示**：见 [docs/使用说明.md](docs/使用说明.md)。

## 标注流程

```
任务创建 → 大模型自动初标 → 学生标注/修正 → 学生自核 → 组长互核 → 专家终审 → 标注锁定 → 数据导出
```

## 用户角色

| 角色 | 说明 |
|------|------|
| 系统管理员 | 平台配置、用户管理、全局项目管理 |
| 标注专家 | 任务创建、大模型初标、终审确认、标注锁定 |
| 标注组长 | 任务分配、进度监控、抽取核对、互核打回 |
| 学生标注员 | 标注/修正、自核、提交 |

## 目录结构

```
├── docker-compose.yml          # 服务编排
├── label-studio/configs/       # Label Studio 标注模板
├── ml-backend/                 # ML Backend 自动标注服务
├── backend/                    # FastAPI 管理后端
├── frontend/                   # Vue 3 管理前端
├── scripts/                    # 工具脚本
├── data/                       # 数据目录
└── docs/                       # 文档
```

## 导出格式

- **LabelStudio JSON** — 完整标注日志，支持溯源
- **COCO JSON** — 对接 MMPose / MMDetection 训练
- **CSV** — 数据清洗与统计分析
- **VLM JSON** — 对接视觉语言模型训练

## 仓库与克隆

```bash
git clone https://github.com/LeChen1234/badminton.git
cd badminton
# 然后按「快速开始」执行
```
