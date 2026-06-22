# ClawFans — $0 试用部署（Cloudflare 快速隧道）

把跑在你本机（RTX 5090）上的 ClawFans 暴露给外部用户试用，**零基础设施成本**：
不用买服务器、不用公网 IP、不用开路由器端口、不用 Cloudflare 账号。

```
外部用户 → https://<随机>.trycloudflare.com   (Cloudflare 免费临时隧道, 自带 HTTPS)
              ↓
          本机 Next.js (:3000)        ← 唯一对外暴露的端口
              ↓ 服务端代理 /api/* 和 /uploads/*  (next.config.ts)
          本机 FastAPI (:8000) + Ollama(无审查模型) + ComfyUI(可选)
```

只暴露前端一个端口；API 和图片/语音都由 Next.js 服务端**同源代理**到后端，所以
外部用户的浏览器不需要直连你的 localhost（这点之前是 bug，已修）。

---

## 0. 一次性准备

1. **Ollama + 无审查模型**（NSFW 必须，主流 API 会封号）：
   ```
   ollama pull huihui_ai/qwen2.5-abliterate:14b
   ```
   在 `backend/.env` 里设 `OLLAMA_MODEL=huihui_ai/qwen2.5-abliterate:14b`
   （没下完前可暂用已装的 `huihui_ai/qwen3-coder-abliterated:30b`）。

2. **cloudflared**（隧道工具，免费）：
   ```
   winget install --id Cloudflare.cloudflared
   ```
   或从 https://github.com/cloudflare/cloudflared/releases 下载 `cloudflared-windows-amd64.exe`，
   重命名为 `cloudflared.exe` 放进 PATH。

3. **前端环境** `frontend/.env.local`：
   ```
   NEXT_PUBLIC_API_URL=            # 留空 → 浏览器用相对路径，走同源代理
   BACKEND_URL=http://localhost:8000
   NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...   # Clerk 测试 key 在任意域名可用
   CLERK_SECRET_KEY=sk_test_...
   ```

4. **构建前端**（生产模式比 dev 稳）：
   ```
   cd frontend && npm run build
   ```

---

## 1. 一键启动

```
powershell -ExecutionPolicy Bypass -File deploy\start_trial.ps1
```

脚本会：启动后端(:8000) → 启动前端生产服务(:3000) → 起 Cloudflared 快速隧道，
并在窗口里打印形如 `https://xxxx-yyyy.trycloudflare.com` 的公网地址。**把这个地址发给试用用户即可。**

手动等价命令（三个终端）：
```
# 1 后端
cd backend && .\venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
# 2 前端
cd frontend && npm start
# 3 隧道
cloudflared tunnel --url http://localhost:3000
```

---

## 2. 注意事项

- **临时地址会变**：`trycloudflare.com` 的 URL 每次重启都不同。要**固定域名**，用命名隧道
  （需免费 Cloudflare 账号 + 一个域名）：`cloudflared tunnel login` → `cloudflared tunnel create clawfans` → 路由到你的域名。
- **机器要开着**：关机/断网 = 服务下线。适合小流量试用；家庭带宽并发有限。
- **Clerk**：测试 key（`pk_test_`）在任意域名可用，试用足够；正式上线再换生产 key 并把隧道域名加入 Clerk 允许列表。
- **成人内容**：只发给成年用户；公开宣发前再核一遍各依赖的 ToS。
- **数据**：聊天/角色都存在本机 `backend/clawfans.db`（SQLite，落真实磁盘，不会丢）。
- **CORS**：同源代理下不会触发；若你改成让浏览器直连后端，需在 `backend/.env` 的
  `ALLOWED_ORIGINS` 里加上隧道域名。

---

## 3. 想要更稳/规模化时
见 `deploy/`（VPS + systemd + nginx 模板）、以及成本对比：本机 5090 = $0；
托管无审查 LLM（Infermatic ~$9/月 / Featherless ~$10/月）；GPU 租赁（TensorDock 3090 ~$0.15/hr，AUP 干净）。
**切勿**用 RunPod/Modal/Vercel/Fly 跑 NSFW（ToS 禁、封号）。
