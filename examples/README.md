# 样例与示例

本目录提供开箱即用的配置和 API 示例，便于快速体验项目。

## 文件说明

| 文件 | 说明 |
|------|------|
| `env.minimal.sample` | 最小可用环境变量样例。复制到**项目根目录**并重命名为 `.env`，按注释修改（尤其 `LABEL_STUDIO_API_KEY`）后即可配合 Docker / 本地启动使用。 |
| `api-examples.http` | REST API 调用示例。可用 VS Code [REST Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client) 直接运行，或参照改为 curl 命令。 |

## 快速使用

1. **配置环境**
   ```bash
   # 在项目根目录 d:\badminton
   copy examples\env.minimal.sample .env
   # 编辑 .env，至少设置 LABEL_STUDIO_API_KEY（首次启动 Label Studio 后在其设置中创建）
   ```

2. **启动并初始化**
   ```bash
   docker-compose up -d
   cd backend && alembic upgrade head && cd ..
   python scripts/init_platform.py
   python scripts/generate_mock_data.py
   ```

3. **调用 API**
   - 用 VS Code 打开 `api-examples.http`，先执行「登录」请求，再执行其他需要 Token 的请求。
   - 或使用 curl：
     ```bash
     curl -X POST http://localhost:8000/api/auth/login -H "Content-Type: application/json" -d "{\"username\":\"expert1\",\"password\":\"expert123\"}"
     ```

更多完整步骤见项目根目录 [README.md](../README.md) 与 [docs/使用说明.md](../docs/使用说明.md)。
