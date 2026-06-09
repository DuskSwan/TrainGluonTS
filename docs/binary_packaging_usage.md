# Linux 二进制打包与使用手册

本文档说明如何在 Linux/Ubuntu 系统上将 TrainGluonTS 打包成可执行程序，以及打包产物如何在边端或外部进程中调用。

本项目目前支持两类二进制入口：

1. 通用 CLI 二进制，用于离线训练、离线推理和查看版本，内部复用现有 Python 接口：

- 训练：`traingluonts train`
- 推理：`traingluonts predict`
- 查看版本：`traingluonts version`

2. 数据分析工作流节点二进制，只用于工作流中的模型推理：

- 程序名：`traingluonts-workflow-node`
- 通信方式：ZeroMQ 非 Multipart，平台使用 REQ，节点使用 REP
- 能力范围：只做推理，不提供训练接口
- 输出格式：返回 `code/message/data`，`data` 中只包含预测结果

二进制程序不提供 HTTP 服务，也不把训练好的模型打进程序本体。CLI 训练产生的模型仍保存在请求参数指定的本地 `artifact_root` 目录下；工作流节点运行时通过平台注入的 `--model-path` 加载已发布模型。

如果已经拿到二进制包，只需要了解如何调用 `version/train/predict`，请看面向前端和外部进程的运行时说明：

```text
docs/binary_cli_usage.md
```

## 构建前准备

进入仓库根目录：

```bash
cd /path/to/TrainGluonTS
```

确认当前虚拟环境可用。本项目要求 Python 3.12 或更高版本：

```bash
.venv/bin/python --version
.venv/bin/python -m pip list
```

打包至少需要 PyInstaller。工作流节点还需要 `pyzmq`，项目依赖中已经包含；推荐同时安装 `orjson`，这样可以避免 GluonTS 启动时输出 JSON 处理相关 warning。

```bash
.venv/bin/python -m pip install pyinstaller pyzmq orjson
```

如果按项目可选依赖安装，也可以使用：

```bash
.venv/bin/python -m pip install -e ".[packaging]"
```

说明：本项目使用 `src layout`，源码包位于 `src/traingluonts`。不强制把本项目安装成库后再打包，但直接调用 PyInstaller 时必须通过 `--paths src` 告诉 PyInstaller 源码根目录。

## 推荐打包方式

推荐优先使用项目内置的打包包装模块：

```bash
PYTHONPATH=src .venv/bin/python -m traingluonts.packaging.build --mode onedir --clean
```

上面命令默认打包通用 CLI 二进制，等价于：

```bash
PYTHONPATH=src .venv/bin/python -m traingluonts.packaging.build \
  --target cli \
  --mode onedir \
  --clean
```

如果要打包工作流节点二进制，使用：

```bash
PYTHONPATH=src .venv/bin/python -m traingluonts.packaging.build \
  --target workflow-node \
  --mode onedir \
  --clean
```

参数说明：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--target` | `cli` | 打包目标，可选 `cli` 或 `workflow-node` |
| `--mode` | `onedir` | 打包模式，可选 `onedir` 或 `onefile` |
| `--name` | 按目标决定 | 输出程序名称；`cli` 默认 `traingluonts`，`workflow-node` 默认 `traingluonts-workflow-node` |
| `--clean` | `false` | 构建前清理 PyInstaller 缓存 |
| `--output-dir` | `dist` | 构建产物目录 |
| `--build-dir` | `build/pyinstaller` | PyInstaller 中间文件目录 |

推荐优先使用 `onedir`。PyTorch、GluonTS、Lightning 依赖较大，目录模式启动更快，也更容易排查动态库或 hidden import 问题。

成功后 Linux `onedir` 产物位于：

```text
dist/
  traingluonts/
    traingluonts
    _internal/
      ...
```

部署到 Ubuntu 机器时，需要整体复制 `dist/traingluonts/` 目录，而不是只复制里面的 `traingluonts` 文件。

工作流节点 `onedir` 产物位于：

```text
dist/
  traingluonts-workflow-node/
    traingluonts-workflow-node
    _internal/
      ...
```

部署工作流节点时，同样需要整体复制 `dist/traingluonts-workflow-node/` 目录。

## 单文件模式

如果确实需要单个可执行文件，可以使用 `onefile`：

```bash
PYTHONPATH=src .venv/bin/python -m traingluonts.packaging.build --mode onefile --clean
```

工作流节点 `onefile`：

```bash
PYTHONPATH=src .venv/bin/python -m traingluonts.packaging.build \
  --target workflow-node \
  --mode onefile \
  --clean
```

成功后 Linux `onefile` 产物通常位于：

```text
dist/
  traingluonts
```

工作流节点 `onefile` 产物通常位于：

```text
dist/
  traingluonts-workflow-node
```

注意：`onefile` 会把 Python 运行时和 Python 包依赖打进一个可执行文件，但运行时仍依赖目标 Linux 系统的基础系统库和 CPU 架构兼容性，例如 `glibc`。同时 `onefile` 启动时需要解压临时运行目录，启动速度通常比 `onedir` 慢。

## 直接使用 PyInstaller 打包

如果不想通过项目内置构建模块，也可以直接运行 PyInstaller。

`onedir`：

```bash
.venv/bin/python -m PyInstaller \
  --noconfirm \
  --clean \
  --onedir \
  --name traingluonts \
  --distpath dist \
  --workpath build/pyinstaller \
  --specpath build/pyinstaller \
  --paths src \
  --collect-data gluonts \
  --collect-submodules gluonts \
  --collect-submodules lightning \
  --collect-submodules pytorch_lightning \
  --collect-submodules torchmetrics \
  src/traingluonts/cli/main.py
```

`onefile`：

```bash
.venv/bin/python -m PyInstaller \
  --noconfirm \
  --clean \
  --onefile \
  --name traingluonts \
  --distpath dist \
  --workpath build/pyinstaller \
  --specpath build/pyinstaller \
  --paths src \
  --collect-data gluonts \
  --collect-submodules gluonts \
  --collect-submodules lightning \
  --collect-submodules pytorch_lightning \
  --collect-submodules torchmetrics \
  src/traingluonts/cli/main.py
```

工作流节点 `onedir`：

```bash
.venv/bin/python -m PyInstaller \
  --noconfirm \
  --clean \
  --onedir \
  --name traingluonts-workflow-node \
  --distpath dist \
  --workpath build/pyinstaller \
  --specpath build/pyinstaller \
  --paths src \
  --collect-data gluonts \
  --collect-submodules gluonts \
  --collect-submodules lightning \
  --collect-submodules pytorch_lightning \
  --collect-submodules torchmetrics \
  src/traingluonts/workflow_node/main.py
```

工作流节点 `onefile`：

```bash
.venv/bin/python -m PyInstaller \
  --noconfirm \
  --clean \
  --onefile \
  --name traingluonts-workflow-node \
  --distpath dist \
  --workpath build/pyinstaller \
  --specpath build/pyinstaller \
  --paths src \
  --collect-data gluonts \
  --collect-submodules gluonts \
  --collect-submodules lightning \
  --collect-submodules pytorch_lightning \
  --collect-submodules torchmetrics \
  src/traingluonts/workflow_node/main.py
```

其中最关键的是：

```bash
--paths src
```

否则在未安装本项目的情况下，PyInstaller 可能找不到 `traingluonts` 包。

## 验证打包产物

构建完成后，先验证版本命令。

`onedir`：

```bash
./dist/traingluonts/traingluonts version --pretty
```

`onefile`：

```bash
./dist/traingluonts version --pretty
```

预期输出：

```json
{
  "ok": true,
  "version": "0.1.0"
}
```

如果看到类似下面的 warning：

```text
gluonts/json.py:102: UserWarning: Using `json`-module for json-handling.
```

说明打包环境里缺少 `orjson` 或 `ujson`。安装 `orjson` 后重新打包即可：

```bash
.venv/bin/python -m pip install orjson
```

如果看到类似下面的 warning：

```text
torch/cuda/__init__.py:1074: UserWarning: Can't initialize NVML
```

通常表示当前机器没有可用的 NVIDIA/NVML 环境。CPU 训练和推理一般不受影响。

工作流节点可以先验证命令行参数是否正常：

`onedir`：

```bash
./dist/traingluonts-workflow-node/traingluonts-workflow-node --help
```

`onefile`：

```bash
./dist/traingluonts-workflow-node --help
```

预期能看到 `--zmq-endpoint`、`--zmq-protocol`、`--model-path`、`--target_name`、`--freq` 等参数。

## 工作流节点二进制使用方式

工作流节点二进制面向平台“AI数据分析二进制”自定义节点使用。它不是一次性命令行推理工具，而是被平台启动后常驻运行，通过 ZeroMQ 接收上游数据并返回预测结果。

平台节点建议配置：

| 配置项 | 建议值 |
| --- | --- |
| 可执行文件路径 | `dist/traingluonts-workflow-node/traingluonts-workflow-node` 或部署后的绝对路径 |
| 进程运行目录 | 部署目录或包含模型/配置文件的工作目录 |
| Multipart 模式 | 关闭 |
| 是否需要模型 | 开启 |
| 启动等待秒数 | 视模型加载耗时设置，例如 `2` 到 `10` |

平台会自动追加以下托管参数，不要手动写到“启动参数”里：

```bash
--zmq-endpoint tcp://127.0.0.1:<port>
--zmq-protocol REQ
--model-path <已发布模型路径>
```

开发者需要在“启动参数”里填写字段映射和推理参数，例如：

```bash
--target_name RF_FWD_PWR \
--timestamp_name time \
--freq 30ms \
--num_samples 50 \
--output_name predict_value
```

如果输入数据没有时间字段，可以不传 `--timestamp_name`，节点会使用虚拟起点：

```bash
--target_name RF_FWD_PWR \
--start_time "1970-01-01 00:00:00" \
--freq 50ms
```

如果一次请求中包含多条序列，可以通过 `--item_id_name` 指定分组字段：

```bash
--target_name RF_FWD_PWR \
--item_id_name sensor_id \
--timestamp_name time \
--freq 30ms
```

启动参数说明：

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `--target_name` | 是 | 输入 `data` 行中作为时间序列目标值的字段 |
| `--timestamp_name` | 否 | 输入 `data` 行中的时间字段；不传时使用 `--start_time` |
| `--start_time` | 否 | 无时间字段时的虚拟起点，默认 `1970-01-01 00:00:00` |
| `--item_id_name` | 否 | 分组字段；不传时整批数据视为单条序列 `series_0` |
| `--freq` | 否 | 时间频率；不传时尝试读取模型目录旁的 `request.json` |
| `--num_samples` | 否 | 预测采样数，默认 `100`；数值越大均值越稳定但越慢 |
| `--output_name` | 否 | 输出预测字段名，默认 `predict_value` |

`freq` 必须与训练时保持一致。毫秒级频率可以使用 Pandas/GluonTS 支持的字符串，例如：

```text
30ms
50ms
1s
5min
D
```

平台发送的请求格式：

```json
{
  "data": [
    {
      "time": "2026-05-25T08:24:00",
      "sensor_id": "A",
      "RF_FWD_PWR": 448.47
    },
    {
      "time": "2026-05-25T08:24:00.030",
      "sensor_id": "A",
      "RF_FWD_PWR": 447.52
    }
  ]
}
```

成功响应格式：

```json
{
  "code": 200,
  "message": "success",
  "data": [
    {
      "item_id": "A",
      "step": 1,
      "predict_value": 451.2
    },
    {
      "item_id": "A",
      "step": 2,
      "predict_value": 452.7
    }
  ]
}
```

错误响应格式：

```json
{
  "code": 500,
  "message": "missing target field: RF_FWD_PWR",
  "data": {}
}
```

工作流节点只返回预测均值，不返回 `quantiles`、`model_path` 或完整 `forecasts` 结构。

本地手工调试时，可以先启动节点：

```bash
./dist/traingluonts-workflow-node/traingluonts-workflow-node \
  --zmq-endpoint tcp://127.0.0.1:55555 \
  --zmq-protocol REQ \
  --model-path /opt/traingluonts/models/model_20260605_100000_ab12cd/predictor \
  --target_name RF_FWD_PWR \
  --timestamp_name time \
  --freq 30ms
```

然后用简单的 ZeroMQ REQ 客户端发送 JSON 验证链路。平台正式接入时，`--zmq-endpoint`、`--zmq-protocol` 和 `--model-path` 由平台注入，不需要手动填写。

## 请求文件组织方式

CLI 使用 JSON 文件传入参数，使用 CSV 文件传入长时间序列数据。

推荐目录结构：

```text
edge_job/
  train_request.json
  predict_request.json
  data/
    train_series.csv
    predict_series.csv
  models/
    ...
  results/
    ...
```

仓库内已经提供一个可以直接测试二进制包的示例目录：

```text
examples/binary_cli_job/
```

示例目录中包含：

- `train_request.json`：训练请求。
- `predict_request.json`：推理请求，示例中固定读取 `models/latest/predictor`。
- `data/train_series.csv`：训练 CSV。
- `data/predict_series.csv`：推理 CSV。
- `models/`：训练模型输出目录。
- `results/`：训练和推理结果输出目录。

路径解析规则：

- `--input` 指向请求 JSON 文件。
- 请求 JSON 里的 `dataset.path`、`artifact_root` 和 `model_path` 如果是相对路径，会按请求 JSON 所在目录解析。
- 因此 `train_request.json` 中写 `"path": "data/train_series.csv"` 时，实际读取的是 `train_request.json` 同级目录下的 `data/train_series.csv`。

Linux 下也可以直接使用绝对路径，例如：

```json
{
  "dataset": {
    "type": "csv",
    "path": "/opt/traingluonts/jobs/job_001/data/train_series.csv",
    "timestamp_column": "timestamp",
    "target_column": "target"
  }
}
```

## 训练调用

`onedir` 训练命令：

```bash
./dist/traingluonts/traingluonts train \
  --input edge_job/train_request.json \
  --output edge_job/results/train_result.json \
  --pretty
```

`onefile` 训练命令：

```bash
./dist/traingluonts train \
  --input edge_job/train_request.json \
  --output edge_job/results/train_result.json \
  --pretty
```

训练请求示例：

```json
{
  "model_name": "daily_sales_simple_feedforward",
  "algorithm": "simple_feedforward",
  "freq": "D",
  "prediction_length": 7,
  "artifact_root": "models",
  "dataset": {
    "type": "csv",
    "path": "data/train_series.csv",
    "format": "long",
    "item_id_column": "item_id",
    "timestamp_column": "timestamp",
    "target_column": "target"
  },
  "training": {
    "max_epochs": 1,
    "checkpoint_every_n_epochs": 100,
    "batch_size": 3,
    "num_batches_per_epoch": 1,
    "accelerator": "cpu"
  },
  "evaluation": {
    "enabled": true,
    "test_length": 7,
    "num_samples": 20,
    "num_workers": 0,
    "quantiles": [0.1, 0.5, 0.9]
  },
  "hyperparameters": {
    "context_length": 14,
    "hidden_dimensions": [40, 40]
  }
}
```

`evaluation.num_workers` 默认是 `0`，表示评估指标计算使用单进程。Ubuntu 边端或容器环境中建议保持 `0`，避免 multiprocessing/IPC 受限导致 `Operation not permitted`。

CSV 示例：

```csv
item_id,timestamp,target
store_001,2024-01-01,12.0
store_001,2024-01-02,15.5
store_001,2024-01-03,14.2
store_002,2024-01-01,9.0
store_002,2024-01-02,10.1
store_002,2024-01-03,11.3
```

训练成功后，`train_result.json` 的结构如下：

```json
{
  "ok": true,
  "result": {
    "model_id": "model_20260605_100000_ab12cd",
    "model_name": "daily_sales_simple_feedforward",
    "algorithm": "simple_feedforward",
    "status": "completed",
    "model_path": "/opt/traingluonts/edge_job/models/model_20260605_100000_ab12cd/predictor",
    "metadata_path": "/opt/traingluonts/edge_job/models/model_20260605_100000_ab12cd/metadata.json",
    "metrics": {
      "MASE": 1.23,
      "MAPE": 0.08,
      "RMSE": 5.67,
      "mean_wQuantileLoss": 0.12
    }
  }
}
```

模型文件会保存到：

```text
edge_job/
  models/
    {model_id}/
      predictor/
      request.json
      metrics.json
      metadata.json
```

## 推理调用

`onedir` 推理命令：

```bash
./dist/traingluonts/traingluonts predict \
  --input edge_job/predict_request.json \
  --output edge_job/results/predict_result.json \
  --pretty
```

`onefile` 推理命令：

```bash
./dist/traingluonts predict \
  --input edge_job/predict_request.json \
  --output edge_job/results/predict_result.json \
  --pretty
```

推理请求示例：

```json
{
  "model_id": "model_20260605_100000_ab12cd",
  "artifact_root": "models",
  "dataset": {
    "type": "csv",
    "path": "data/predict_series.csv",
    "format": "long",
    "item_id_column": "item_id",
    "timestamp_column": "timestamp",
    "target_column": "target"
  },
  "prediction": {
    "num_samples": 100,
    "quantiles": [0.1, 0.5, 0.9]
  }
}
```

如果使用 `model_path`，请求可以写成：

```json
{
  "model_path": "models/model_20260605_100000_ab12cd/predictor",
  "dataset": {
    "type": "csv",
    "path": "data/predict_series.csv",
    "timestamp_column": "timestamp",
    "target_column": "target"
  },
  "prediction": {
    "num_samples": 100,
    "quantiles": [0.5]
  }
}
```

如果 predictor 目录旁边存在训练时保存的 `request.json`，推理请求可以不传 `freq`。如果只有孤立的 predictor 目录，没有同级 `request.json`，需要显式传入：

```json
{
  "model_path": "/opt/models/my_predictor",
  "freq": "D",
  "dataset": {
    "type": "csv",
    "path": "data/predict_series.csv",
    "timestamp_column": "timestamp",
    "target_column": "target"
  }
}
```

推理成功后，`predict_result.json` 的结构如下：

```json
{
  "ok": true,
  "result": {
    "model_id": "model_20260605_100000_ab12cd",
    "model_path": "/opt/traingluonts/edge_job/models/model_20260605_100000_ab12cd/predictor",
    "forecasts": [
      {
        "item_id": "store_001",
        "start_date": "2024-01-08",
        "mean": [16.2, 17.1, 18.0],
        "quantiles": {
          "0.1": [12.3, 13.0, 13.8],
          "0.5": [16.0, 17.0, 18.1],
          "0.9": [20.5, 21.7, 22.4]
        }
      }
    ]
  }
}
```

## 示例目录完整验证

仓库内的示例可以直接用来验证 Linux 打包产物。

训练：

```bash
./dist/traingluonts/traingluonts train \
  --input examples/binary_cli_job/train_request.json \
  --output examples/binary_cli_job/results/train_result.json \
  --pretty
```

训练完成后，可以直接从 `train_result.json` 读取 `result.model_path` 做推理。也可以手动把最新模型复制到 `models/latest`，让示例 `predict_request.json` 保持固定路径：

```bash
latest_model_dir="$(.venv/bin/python - <<'PY'
import json
from pathlib import Path

result = json.loads(Path("examples/binary_cli_job/results/train_result.json").read_text())
print(Path(result["result"]["model_path"]).parent)
PY
)"

rm -rf examples/binary_cli_job/models/latest
cp -a "$latest_model_dir" examples/binary_cli_job/models/latest
```

推理：

```bash
./dist/traingluonts/traingluonts predict \
  --input examples/binary_cli_job/predict_request.json \
  --output examples/binary_cli_job/results/predict_result.json \
  --pretty
```

成功后查看：

```text
examples/binary_cli_job/results/train_result.json
examples/binary_cli_job/results/predict_result.json
```

## 错误输出与退出码

失败时，CLI 会输出统一 JSON。输出位置取决于是否传入 `--output`：

- 传入 `--output`：写入指定 JSON 文件。
- 未传 `--output`：写入 stdout。

错误示例：

```json
{
  "ok": false,
  "error": {
    "type": "TrainingRequestError",
    "message": "CSV file is missing required columns: target"
  }
}
```

退出码：

| 退出码 | 场景 |
| --- | --- |
| `0` | 成功 |
| `1` | 未分类运行错误 |
| `2` | 输入参数或 JSON 格式错误 |
| `3` | 训练请求错误 |
| `4` | 推理请求错误 |
| `5` | 模型路径或 registry 错误 |

外部调用方推荐按以下顺序处理：

1. 执行二进制命令。
2. 检查进程退出码。
3. 读取输出 JSON。
4. 判断 `ok`。
5. 成功读取 `result`，失败读取 `error.type` 和 `error.message`。

## 分发注意事项

- `onedir` 模式需要整体复制 `dist/traingluonts/` 目录。
- `onedir` 模式不要只复制 `dist/traingluonts/traingluonts` 文件，否则会缺少 `_internal` 下的依赖文件。
- 工作流节点 `onedir` 模式需要整体复制 `dist/traingluonts-workflow-node/` 目录。
- 工作流节点 `onedir` 模式不要只复制 `dist/traingluonts-workflow-node/traingluonts-workflow-node` 文件。
- `onefile` 模式可以复制单个 `dist/traingluonts` 文件，但启动更慢，排查依赖问题也更困难。
- 工作流节点 `onefile` 模式可以复制单个 `dist/traingluonts-workflow-node` 文件。
- 构建产物不能跨平台通用；需要在 Linux x86_64 上构建 Linux x86_64 程序，在 ARM 设备或兼容环境中构建 ARM 程序。
- 第一版建议只承诺 CPU 运行，GPU 依赖和驱动不包含在二进制包承诺范围内。
- 模型产物不在二进制包内，训练和推理时由请求 JSON 中的 `artifact_root` 或 `model_path` 指定。
- 如果部署目录中没有可执行权限，需要执行 `chmod +x dist/traingluonts/traingluonts`、`chmod +x dist/traingluonts`、`chmod +x dist/traingluonts-workflow-node/traingluonts-workflow-node` 或 `chmod +x dist/traingluonts-workflow-node`。

## 常见问题

### 是否必须先安装本项目再打包？

不必须。可以直接把 `src/traingluonts/cli/main.py` 当作入口脚本打包。

如果不安装本项目，直接运行 PyInstaller 时必须加：

```bash
--paths src
```

项目内置的 `traingluonts.packaging.build` 已经自动加了这个参数。

### 为什么会生成 `src/traingluonts.egg-info`？

执行 `pip install -e .` 或 `pip install -e ".[packaging]"` 后，setuptools 会生成包元数据目录。它不是业务代码，不需要提交，`.gitignore` 中应忽略：

```gitignore
*.egg-info/
```

### 为什么优先推荐 `onedir`？

PyTorch 和科学计算依赖较大。`onedir` 启动更快，排查缺失依赖更容易。`onefile` 需要运行时解压，启动慢，也更容易遇到动态库问题。

### 构建产物能跨平台使用吗？

不能保证。Windows、Linux、ARM 架构需要分别在对应平台或兼容构建环境中构建。Ubuntu x86_64 上构建的产物通常只能部署到兼容的 Linux x86_64 环境。
