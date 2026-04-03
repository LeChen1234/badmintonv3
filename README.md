# 羽毛球训练动作数据集标注系统

基于 Label Studio 的羽毛球训练动作数据集标注平台，支持大模型自动化初标、学生协作标注、三级核对校验。

## 系统架构

| 组件 | 技术栈 | 端口 | 说明 |
|------|--------|------|------|
| Label Studio | Label Studio OSS | 8080 | 标注编辑平台 |
| ML Backend | label-studio-ml-backend | 9090 | 自动标注服务（姿态估计 + 动作识别） |
| 管理后端 | FastAPI + SQLAlchemy | 8000 | RBAC / 任务分配 / 审核流程 / 数据导出 |
| 管理前端 | Vue 3 + Element Plus | 3000 | 管理仪表盘 |
| 数据库 | SQLite | - | 本地单文件数据库（`data/badminton.db`） |
| 缓存 | Redis 7 | 6379 | 任务队列 / 缓存 |

## 快速开始

### 安装 Docker

参考 [Docker 官方文档](https://docs.docker.com/engine/install/) 安装 Docker。

对于 Debian/Ubuntu：

```bash
sudo apt remove $(dpkg --get-selections docker.io docker-compose docker-doc podman-docker containerd runc | cut -f1)
# Add Docker's official GPG key:
sudo apt update
sudo apt install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/debian
Suites: $(. /etc/os-release && echo "$VERSION_CODENAME")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt update

sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

对于 Windows，应该下载并安装 [Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/)。


### 克隆仓库

```bash
git clone https://github.com/LeChen1234/badmintonv3.git
```

### 启动服务

```bash
cd badmintonv3
docker-compose up -d
```

你应该可以访问 [http://localhost:8080](http://localhost:8080) 来使用平台，默认管理员账号是 `admin` / `admin123`。

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