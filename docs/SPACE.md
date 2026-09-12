# 部署到 Hugging Face Space

`app.py` 是把 `web/` 的 React 前端复刻成 Gradio 的单文件应用，专为
**Gradio SDK + ZeroGPU** 的 Space 准备。本文只讲部署；界面/推理的设计取舍见 `app.py` 顶部注释。

## 1. 建 Space

1. <https://huggingface.co/new-space> → 选 **Gradio** SDK，硬件选 **ZeroGPU**。
   （免费个人号可建 2 个 ZeroGPU Space，账号需满 30 天且邮箱已验证。）
2. Space 的 `README.md` 顶部 front-matter 至少要写：

   ```yaml
   ---
   title: ReID Trajectory Search System
   emoji: 🛰️
   colorFrom: blue
   colorTo: purple
   sdk: gradio
   sdk_version: 6.29.0
   app_file: app.py
   pinned: false
   ---
   ```

   通过网页建 Space 并选了 Gradio SDK 的话，这段 HF 会自己写好，不用手抄。
   正文建议直接引用 `README.md` 的内容，并保留「前期可行性验证」声明。

## 2. 传文件

仓库根目录就是 Space 仓库根目录，`app_file` 指向根下的 `app.py`。
只需要传下面这些（其余本地文件一律不要传）：

| 路径 | 说明 |
| --- | --- |
| `app.py` | Gradio 应用本体 |
| `requirements.txt` | Space 依赖（`torch` 交给 ZeroGPU 镜像） |
| `reid_sys/` | 库本体 + `reid_sys/locales/*.json`（界面文案） |
| `third_part/fast-reid/fastreid/`、`third_part/fast-reid/configs/` | 模型定义与配置（submodule，必须**按文件**传，不能传 submodule 指针） |
| `data/datasets.json`、`data/data1.zip`、`data/data2.zip` | demo 数据集（约 41 MB） |
| `models/yolo26n.pt` | 检测权重（5.3 MB） |

308 MB 的 `models/msmt_sbs_R50-ibn.pth` **不用传**：`app.py` 启动时发现缺了会按
`reid_sys/backbone.py` 里记的官方地址拉一次（写进容器的临时盘，不进仓库）。

```bash
pip install -U "huggingface_hub[cli]"
hf auth login

hf upload <用户名>/<space名> . . --repo-type space \
  --include "app.py" "requirements.txt" \
  --include "reid_sys/*.py" "reid_sys/locales/*.json" \
  --include "third_part/fast-reid/fastreid/*" "third_part/fast-reid/configs/*" \
  --include "data/datasets.json" "data/data1.zip" "data/data2.zip" \
  --include "models/yolo26n.pt"
```

> 老版本 CLI 里命令名是 `huggingface-cli upload`，参数一致。
> `--include` 里的 `*` 只匹配一层目录，`third_part/fast-reid/fastreid/*` 是够的
> （fast-reid 内部不再有更深一层需要单独列出的资源目录）；不确定时可以不加
> `--include`，改成传整个 `third_part/fast-reid`（约 8 MB）。

## 3. 环境变量（可选）

| 变量 | 默认 | 作用 |
| --- | --- | --- |
| `REID_LOCALE` | `ja-JP` | 首屏语言，取值 `zh-TW` / `en-US` / `ja-JP`（与 `web/src/i18n/index.js` 的兜底一致）。访问 `?locale=en-US` 可临时覆盖。 |
| `REID_DEVICE` | 自动 | 强制推理设备。ZeroGPU 下不要设，让它自己挑 `cuda`。 |

## 4. 首次访问会发生什么

1. 启动阶段：解压 `data/*.zip` → 下载 308 MB 权重 → 载入 backbone（放显存/模拟显存）。
2. 页面直接出来就是成品（首屏由 Python 预渲染），不需要等事件。
3. **第一次检索**会顺带建向量索引（约 10~30 秒，只在 GPU 窗口内跑一次，
   整个容器生命周期内只建一次）。「系统与评估」页的「重新录入」也能手动触发。

## 5. 与本地版（`serve.py` + `web/dist`）的差异

| 项 | 本地版 | Space 版 |
| --- | --- | --- |
| 前端 | React + MUI（`web/`） | Gradio（`app.py`），同一套文案与配色 |
| 推理设备 | GTX 1050 Ti，torch 2.7.0+cu126 | ZeroGPU 动态分配，torch 由镜像提供 |
| 向量库 | milvus-lite 文件库 | 同左（容器内文件库，重启重建） |
| 点位地图 | 腾讯地图 GL JS 真实底图 | **不加载底图**：合规底图需要后端代理密钥，Space 上只保留合规说明与点位台账占位 |
| 摄像头 / 边缘节点 / K8s 页 | 占位页 | 占位页（同样标「未接入」） |
| HTTP 接口 | FastAPI（`reid_sys/api.py`，`/docs`） | 没有 HTTP 接口，只有 Gradio 事件 |

## 6. 排障

- **`Open local milvus failed`**：milvus-lite 同一时刻只允许一个进程独占库文件。
  Space 上只有一个进程，正常不会遇到；本地同时跑 `serve.py` 和 `app.py` 才会。
- **启动日志里没有输出**：确认用的是 `python -u app.py`（或 `PYTHONUNBUFFERED=1`）。
- **`No module named 'torch'`**：在 `requirements.txt` 里加 `torch>=2.8.0`。
- **改界面文案**：改 `web/src/i18n/locales/*.js`，然后
  `node scripts/export_locales.mjs` 重新生成 `reid_sys/locales/*.json`，两个前端一起变。
