# omnishot

AI 幻影影棚 DEMO

这个仓库把本地 DEMO 拆成了三层：

1. `ComfyUI/`：官方源码，负责 GPU 推理与工作流执行。
2. `app/`：FastAPI 中间层，负责上传图片、改写工作流 JSON、调用 ComfyUI API、返回生成图。
3. `demo.html`：极简网页，方便本地演示。

当前工程已经准备好了：

- 独立 Python 虚拟环境：`/home/cheng/workspace/ai-phantom-studio-demo/.venv`
- 官方 `ComfyUI` 源码：`/home/cheng/workspace/ai-phantom-studio-demo/ComfyUI`
- FastAPI 服务与前端页面
- 工作流模板和绑定配置
- 一键启动和检查脚本
- mock 回退模式，便于在模型还没放好前先打通接口

当前仓库使用：

- 主仓库：业务代码、FastAPI、脚本、工作流
- `ComfyUI`：Git submodule

首次 clone 后建议执行：

```bash
git submodule update --init --recursive
```

## 当前推荐流程

截至 `2026-03-17`，这个仓库已经明确拆成两条链路：

1. `Scene` 静物场景图
   - `BiRefNet-HR-matting` 抠图
   - `FLUX + Depth ControlNet`
   - 最后把原商品前景重新贴回生成图，避免商品主体被模型改形
2. `Try-On` 模特上身图
   - `CatVTON`
   - 使用内置模特模板或自定义模特图

这样做的原因很简单：同一个通用生图工作流不可能同时把“商品主体不变”和“模特上身自然”两件事都做好。

## 新接口

- `POST /generate` 或 `POST /generate/scene`
  - 生成静物场景图
- `POST /generate/tryon`
  - 生成模特上身图
- `GET /api/presets/scenes`
  - 返回内置场景预设
- `GET /api/presets/tryon-templates`
  - 返回内置模特模板

## 目录

```text
ai-phantom-studio-demo/
├── ComfyUI/
├── app/
├── data/
├── demo.html
├── scripts/
└── workflows/
```

## 先装运行时

后端依赖已经装在 `.venv` 里。ComfyUI 的 `torch` 和官方依赖还需要执行一次：

```bash
cd /home/cheng/workspace/ai-phantom-studio-demo
./scripts/install_comfyui_runtime.sh
```

这一步会先安装 PyTorch，再安装“足够跑本地 API/工作流”的最小运行依赖，不会默认把 `workflow templates` 等可选大包全部拉下来。

注意：截至本次搭建当天 `2026-03-17`，官方 `ComfyUI` 仓库最新提交（`7a16e8aa`，提交时间 `2026-03-16`）对 NVIDIA 的 README 默认推荐 `cu130`。但这台机器当前驱动是 `545.29.06`，我本地实测 `torch 2.10.0+cu130` 会报驱动过旧，`torch.cuda.is_available()` 返回 `False`。

所以这个 DEMO 的安装脚本默认改成了更稳妥的本机组合：

- `torch==2.5.1`
- `torchvision==0.20.1`
- `torchaudio==2.5.1`
- `--index-url https://download.pytorch.org/whl/cu121`
- 最小运行集：`aiohttp`、`requests`、`tqdm`、`einops`、`transformers`、`tokenizers`、`safetensors`、`alembic`、`SQLAlchemy` 等

如果你之后想把官方所有可选依赖也补齐，再执行：

```bash
cd /home/cheng/workspace/ai-phantom-studio-demo
INSTALL_COMFYUI_FULL_REQUIREMENTS=true ./scripts/install_comfyui_runtime.sh
```

如果你后面把 NVIDIA 驱动升级到支持 CUDA 13 的版本，再把安装脚本切回更高版本的 wheel 即可。

## 安装自定义节点依赖

要跑 `RMBG + FLUX + ControlNet Depth`，除了上面的基础运行时，还需要安装自定义节点依赖：

```bash
cd /home/cheng/workspace/ai-phantom-studio-demo
./scripts/install_custom_nodes.sh
```

说明：

- 这个脚本会按顺序安装 `ComfyUI-GGUF`、`comfyui_controlnet_aux`、`ComfyUI-RMBG` 的 `requirements.txt`
- 每个节点单独写日志到 `logs/install-<node>.log`
- 如果你只想装某一个节点，可传目录名参数，例如：

```bash
cd /home/cheng/workspace/ai-phantom-studio-demo
./scripts/install_custom_nodes.sh ComfyUI-RMBG
```

如果你要优先“快速打通链路”（先能看到节点、再慢慢补全），可启用 fast 模式：

```bash
cd /home/cheng/workspace/ai-phantom-studio-demo
INSTALL_CUSTOM_NODES_FAST=true ./scripts/install_custom_nodes.sh
```

`fast` 模式会对重依赖节点安装最小依赖集合（例如 `opencv-python-headless`、`onnxruntime`、`transparent-background`），适合先跑通 DEMO；后续再执行 full 模式补齐全部依赖。

大包（例如 `opencv`、`mediapipe`）下载可能较慢，属于正常现象。

## 启动顺序

1. 启动 ComfyUI：

```bash
cd /home/cheng/workspace/ai-phantom-studio-demo
./scripts/start_comfyui.sh
```

2. 启动 FastAPI：

```bash
cd /home/cheng/workspace/ai-phantom-studio-demo
./scripts/start_api.sh
```

3. 打开 DEMO 页面：

```text
http://127.0.0.1:8000
```

4. 检查环境：

```bash
cd /home/cheng/workspace/ai-phantom-studio-demo
.venv/bin/python scripts/check_demo_env.py
```

5. 检查 FLUX 节点/模型就绪度：

```bash
cd /home/cheng/workspace/ai-phantom-studio-demo
.venv/bin/python scripts/check_flux_readiness.py
```

若想在 CI 或脚本里作为硬性检查，使用严格模式（缺项返回非 0）：

```bash
cd /home/cheng/workspace/ai-phantom-studio-demo
.venv/bin/python scripts/check_flux_readiness.py --strict
```

6. 先创建 FLUX 模型目录（会生成目录和放置说明文件）：

```bash
cd /home/cheng/workspace/ai-phantom-studio-demo
./scripts/prepare_flux_model_dirs.sh
```

7. 一键下载 DEMO 必需模型（默认走 `hf-mirror.com`，支持断点续传）：

```bash
cd /home/cheng/workspace/ai-phantom-studio-demo
./scripts/install_required_models.sh
```

可选：指定 GGUF 量化版本（默认 `flux1-dev-Q4_K_S.gguf`）：

```bash
cd /home/cheng/workspace/ai-phantom-studio-demo
FLUX_GGUF_FILE=flux1-dev-Q5_0.gguf ./scripts/install_required_models.sh
```

这个脚本会同时准备：

- FLUX UNet GGUF
- T5/CLIP 文本编码器
- VAE
- FLUX Depth ControlNet
- RMBG-2.0 本地模型文件
- DepthAnything 预处理模型缓存（避免运行时在线下载）

8. 运行一次端到端冒烟测试（调用 `/generate` 并落地结果图）：

```bash
cd /home/cheng/workspace/ai-phantom-studio-demo
.venv/bin/python scripts/smoke_generate.py
```

9. 一键看当前状态（服务健康 + FLUX 就绪度）：

```bash
cd /home/cheng/workspace/ai-phantom-studio-demo
./scripts/status_report.sh
```

## 持续批量出图（目录监听）

如果你要“源源不断上传睡裙图并一键出多场景”，直接用这个脚本：

[`scripts/batch_generate.py`](/home/cheng/workspace/ai-phantom-studio-demo/scripts/batch_generate.py)

它会：

- 扫描输入目录中的商品图
- 按场景提示词批量调用 `/generate`
- 自动把结果图保存到输出目录
- 记录任务清单到 `manifest.jsonl`
- 支持 watch 模式持续监听新文件
- 去重键默认包含“工作流版本”（模板/绑定文件签名），工作流改动后会自动重新生成

默认内置 3 个场景：

- `sunset_bedroom`
- `morning_terrace`
- `neon_storefront`

### 单次批量运行

```bash
cd /home/cheng/workspace/ai-phantom-studio-demo
.venv/bin/python scripts/batch_generate.py \
  --once \
  --input-dir data/incoming-products \
  --output-dir data/batch-output
```

### 持续监听模式

```bash
cd /home/cheng/workspace/ai-phantom-studio-demo
.venv/bin/python scripts/batch_generate.py \
  --input-dir data/incoming-products \
  --output-dir data/batch-output \
  --poll-seconds 5
```

你可以把新睡裙图不断放入 `data/incoming-products/`，脚本会自动处理并生成多场景成图。

## 一次性生成场景图 + 模特图

如果你要直接从一个目录里同时批量出 `scene` 和 `try-on` 两类结果，用这个新脚本：

[`scripts/catalog_generate.py`](/home/cheng/workspace/ai-phantom-studio-demo/scripts/catalog_generate.py)

示例：

```bash
cd /home/cheng/workspace/ai-phantom-studio-demo
.venv/bin/python scripts/catalog_generate.py \
  --once \
  --input-dir data/incoming-products \
  --output-dir data/catalog-output \
  --product-brief "premium silk slip dress product photo" \
  --scene-count 4 \
  --tryon-templates woman_1,woman_2,woman_3
```

输出会分成：

- `data/catalog-output/scenes/`
- `data/catalog-output/tryon/`
- `data/catalog-output/manifest.jsonl`

### 自定义场景提示词

创建一个 JSON 文件（例如 `workflows/incoming/scenes.json`）：

```json
[
  {
    "name": "sunset_room",
    "prompt": "luxury silk nightdress product photo on a bed, warm sunset light, realistic textile detail",
    "negative_prompt": "blurry, low quality, deformed shape"
  },
  {
    "name": "city_neon",
    "prompt": "luxury silk nightdress product photo near a storefront window, cinematic neon reflections",
    "negative_prompt": "blurry, low quality, artifacts"
  }
]
```

然后执行：

```bash
cd /home/cheng/workspace/ai-phantom-studio-demo
.venv/bin/python scripts/batch_generate.py \
  --once \
  --input-dir data/incoming-products \
  --output-dir data/batch-output \
  --scenes-file workflows/incoming/scenes.json
```

## 当前工作流文件怎么用

`workflows/flux_product_demo.template.json` 当前已经是“真实生成”工作流，不再是透传模板。默认链路是：

- `LoadImage`
- `RMBG`
- `DepthAnythingPreprocessor`
- `UnetLoaderGGUF + ModelSamplingFlux`
- `DualCLIPLoaderGGUF + CLIPTextEncodeFlux`
- `ControlNetLoader + ControlNetApplyAdvanced`
- `SamplerCustomAdvanced + VAEDecode`
- `ImageCompositeMasked`（把 RMBG 前景强制回贴到生成背景）
- `SaveImage`

也就是说，默认模板会实际运行 FLUX 生成，并输出 1024x1024 场景图。
在当前模板里，商品主体是通过“前景回贴”锁定的，主要变化集中在场景和光线。

补充说明：

- 当前 `ComfyUI` 已经可以正常启动并响应 `/queue`
- 当前 `FastAPI -> ComfyUI -> FastAPI` 的真实 FLUX 生成链路已经验证通过
- `comfyui-workflow-templates` 和 `comfyui-embedded-docs` 没有默认安装，所以启动日志里会看到相关提示，但这不影响 API 调用和 DEMO 跑通

你真正需要做的是：

1. 在 ComfyUI UI 里把 `RMBG + FLUX + ControlNet Depth` 工作流手动调通。
2. 用 `Save (API Format)` 导出 JSON。
3. 用你的导出文件覆盖：

```text
/home/cheng/workspace/ai-phantom-studio-demo/workflows/flux_product_demo.template.json
```

4. 编辑绑定文件：

[`workflows/flux_product_demo.bindings.json`](/home/cheng/workspace/ai-phantom-studio-demo/workflows/flux_product_demo.bindings.json)

把这些节点 ID 改成你实际工作流里的节点：

- `image`：加载产品图的节点
- `positive_prompt`：正向提示词节点
- `negative_prompt`：反向提示词节点
- `seed`：采样 seed 节点
- `preferred_output_nodes`：保存图片的节点

如果你不想手动改节点 ID，可以直接用自动识别脚本从导出 JSON 生成 bindings 草稿：

```bash
cd /home/cheng/workspace/ai-phantom-studio-demo
.venv/bin/python scripts/generate_bindings_from_api_json.py \
  --workflow /path/to/your/exported_api_workflow.json \
  --write-template workflows/flux_product_demo.template.json \
  --write-bindings workflows/flux_product_demo.bindings.json \
  --print-nodes
```

说明：

- 这个命令会覆盖模板文件并重写 bindings
- `--print-nodes` 会打印节点总览，方便你核对自动识别结果
- 如果你只想更新 bindings、不覆盖模板，可加 `--skip-template-copy`

也可以走更快的默认流程：

1. 把导出的 API JSON 放到：`workflows/incoming/exported_api_workflow.json`
2. 执行：

```bash
cd /home/cheng/workspace/ai-phantom-studio-demo
./scripts/apply_exported_workflow.sh
```

## 模型和节点建议落点

基于当前官方目录结构，常见模型目录如下：

- UNet / GGUF：`ComfyUI/models/unet/`
- Text Encoders：`ComfyUI/models/text_encoders/`
- CLIP：`ComfyUI/models/clip/`
- VAE：`ComfyUI/models/vae/`
- ControlNet：`ComfyUI/models/controlnet/`

建议先按下面“示例文件名”准备最小可跑集合（文件名可不同，但类型要对应）：

- `ComfyUI/models/unet/`：`flux1-dev-Q4_K_S.gguf`
- `ComfyUI/models/text_encoders/`：`t5xxl_fp8.safetensors`（或 `t5xxl_fp16.safetensors`）
- `ComfyUI/models/clip/`：`clip_l.safetensors`
- `ComfyUI/models/vae/`：`ae.sft`
- `ComfyUI/models/controlnet/`：`flux-depth-controlnet.safetensors`

你还需要把对应自定义节点安装到：

```text
ComfyUI/custom_nodes/
```

你这个 DEMO 至少要有：

- RMBG 节点
- FLUX 所需加载节点
- FLUX Depth ControlNet 相关节点

## API 说明

### `POST /generate`

支持两种请求方式：

1. `multipart/form-data`
2. `application/json`，字段为：

```json
{
  "prompt": "a silk nightdress on a wooden table",
  "negative_prompt": "blurry, deformed",
  "image_base64": "<base64>",
  "seed": 1234,
  "filename": "product.png"
}
```

返回结果：

```json
{
  "prompt_id": "uuid",
  "generator_mode": "comfyui",
  "filename": "comfy-xxx.png",
  "output_url": "/outputs/comfy-xxx.png",
  "mime_type": "image/png",
  "image_base64": "<base64>",
  "comfyui_prompt_id": "uuid",
  "local_input_path": "/abs/path/to/input.png"
}
```

如果 ComfyUI 当前不可用，且 `MOCK_FALLBACK_ENABLED=true`，服务会返回 `generator_mode=mock` 的占位结果，用来先验证整条调用链。

## 关键文件

- 后端入口：[app/main.py](/home/cheng/workspace/ai-phantom-studio-demo/app/main.py)
- ComfyUI API 客户端：[app/comfy_client.py](/home/cheng/workspace/ai-phantom-studio-demo/app/comfy_client.py)
- 工作流绑定逻辑：[app/workflow.py](/home/cheng/workspace/ai-phantom-studio-demo/app/workflow.py)
- 页面：[demo.html](/home/cheng/workspace/ai-phantom-studio-demo/demo.html)
- ComfyUI 启动脚本：[scripts/start_comfyui.sh](/home/cheng/workspace/ai-phantom-studio-demo/scripts/start_comfyui.sh)
- API 启动脚本：[scripts/start_api.sh](/home/cheng/workspace/ai-phantom-studio-demo/scripts/start_api.sh)
