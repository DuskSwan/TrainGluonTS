# TrainGluonTS

TrainGluonTS 是一个用于 **训练和推理** GluonTS 时间序列预测模型的 Python 模块。当前版本已经实现训练和推理能力：接收结构化训练参数，完成数据转换、模型训练、评估和本地保存；也可以加载本地 predictor，对新的时间序列执行预测。

推理接口会输出每条序列的预测开始时间、均值预测和分位数预测结果。

训练和推理接口的 `dataset` 支持两种输入方式：直接传入 `series`，或传入 CSV 文件路径。长时间序列推荐使用 CSV。

当前仓库提供三种集成方式：

- **Python API**：核心集成方式，外部 Python 项目可以直接调用 `train_model()` 和 `predict()`。
- **HTTP/FastAPI API**：面向前端或本机服务调用方的包装层，复用同一套训练、推理和模型加载逻辑。
- **CLI/二进制入口**：面向边端或非 Python 调用方，通过 JSON 请求文件和 CSV 数据文件执行训练、推理和版本检查。

三种入口共享同一套 schema、数据转换、训练、推理和错误处理逻辑。Python API 是核心业务实现，HTTP API 和 CLI 是适配层。

完整接口文档见：

```text
docs/api.md
docs/http_api.md
```

二进制 CLI 和打包说明见：

```text
docs/binary_packaging_design.md
docs/binary_packaging_usage.md
```

## 当前能力检查

现有工具已经可以满足第一版训练和推理需求：

- [x] 支持直接 Python 函数调用。
- [x] 支持 HTTP/FastAPI 包装入口。
- [x] 支持同步训练、异步训练任务、推理和模型加载检查接口。
- [x] 支持结构化训练请求校验。
- [x] 支持结构化推理请求校验。
- [x] 支持合成测试数据生成。
- [x] 支持 GluonTS `ListDataset` 数据转换。
- [x] 支持从 CSV 文件读取训练和推理数据。
- [x] 支持 `deepar` 和 `simple_feedforward` 两种模型。
- [x] 支持两种模型各自独立的超参数。
- [x] 支持训练集/测试集拆分和 holdout 评估。
- [x] 支持配置评估指标计算的 `num_workers`，默认单进程运行。
- [x] 支持保存 predictor、训练请求、评估指标和 metadata。
- [x] 支持通过 `model_id + artifact_root` 推理。
- [x] 支持通过 `model_path` 推理。
- [x] 支持推理均值和分位数输出。
- [x] 支持二进制 CLI 包装入口 `version/train/predict`。
- [x] 支持 PyInstaller 打包包装脚本。
- [x] 支持 `traingluonts-api` 服务启动脚本。
- [x] 支持最小训练流程测试。
- [x] 支持训练后加载并推理的端到端测试。

当前验证命令：

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests
```

## Python 训练使用方式

大仓向本模块传入一个训练请求，模块完成训练并返回结构化结果。

预期调用方式：

```python
from traingluonts import train_model

result = train_model(
    {
        "model_name": "daily_sales_deepar",
        "algorithm": "deepar",
        "freq": "D",
        "prediction_length": 14,
        "dataset": {
            "series": [
                {
                    "item_id": "store_001",
                    "start": "2024-01-01",
                    "target": [12.0, 15.5, 14.2, 18.1],
                }
            ]
        },
        "training": {
            "max_epochs": 10,
            "batch_size": 32,
            "num_batches_per_epoch": 50,
            "accelerator": "cpu",
        },
        "hyperparameters": {
            "context_length": 28,
            "num_layers": 2,
            "hidden_size": 40,
            "dropout_rate": 0.1,
        },
        "evaluation": {
            "enabled": True,
            "test_length": 14,
            "num_workers": 0,
        },
    }
)

print(result.model_id)
print(result.model_path)
print(result.metrics)
```

Python 训练入口是同步函数。如果调用方需要后台任务、任务状态轮询或队列调度，可以使用 HTTP API 已提供的异步训练任务，也可以由外部系统自己的 worker 调用同一个 `train_model()` 入口。

## HTTP API 使用方式

HTTP API 是现有 Python 接口的 FastAPI 包装层，适合前端或本机服务通过 HTTP 调用训练和推理能力。

开发期启动：

```powershell
$env:PYTHONPATH="src"
.\.venv\Scripts\python.exe -m traingluonts.api.server
```

如果项目已安装到当前环境，也可以使用脚本入口：

```powershell
traingluonts-api
```

默认监听：

```text
http://127.0.0.1:8000
```

主要接口：

- `GET /api/v1/health`
- `GET /api/v1/version`
- `POST /api/v1/train`
- `POST /api/v1/train/jobs`
- `GET /api/v1/train/jobs/{job_id}`
- `POST /api/v1/predict`
- `POST /api/v1/predict-with-model`
- `POST /api/v1/models/load-check`
- `GET /api/v1/models/{model_id}/load-check`

HTTP 请求结构和响应格式见 `docs/http_api.md`。

## 建议项目结构

```text
TrainGluonTS/
  src/
    traingluonts/
      __init__.py
      schemas.py          # 训练请求/训练结果的数据结构与校验
      dataset.py          # 前端或大仓传入的数据 -> GluonTS ListDataset
      estimators.py       # 根据算法名和参数创建 GluonTS estimator
      trainer.py          # 训练、评估、保存的核心流程
      inference.py        # 加载模型并执行推理
      registry.py         # 本地模型路径、metadata 管理
      errors.py           # 模块内专用异常
      testing.py          # 测试和示例使用的合成数据生成工具
      api/                # FastAPI HTTP 包装层
      cli/                # 二进制和命令行入口
      packaging/          # PyInstaller 构建包装
  examples/
    basic_gluonts_usage.py
    train_via_module.py
    predict_via_module.py
    binary_cli_job/
  artifacts/
    models/
      {model_id}/
        predictor/        # predictor.serialize 的输出目录
        request.json      # 归一化后的训练请求
        metrics.json      # 评估指标，启用评估时生成
        metadata.json     # 模型 id、状态、时间、路径等元信息
```

`artifacts/` 是运行产物目录，不应该进入版本控制。

## 对外模块接口

### 训练接口，已实现

当前核心公共函数：

```python
def train_model(request: TrainingRequest | dict) -> TrainingResult:
    ...
```

该函数负责：

1. 校验并归一化训练请求。
2. 将输入序列转换为 GluonTS 数据集。
3. 根据参数创建指定 estimator。
4. 执行模型训练。
5. 按需进行评估。
6. 将训练好的 predictor 保存到本地。
7. 写入模型元信息。
8. 返回结构化训练结果。

当前已提供模型加载辅助函数，后续可以继续补充模型列表和删除能力：

```python
def load_model(model_id: str) -> Predictor:
    ...

def list_models() -> list[ModelMetadata]:
    ...

def delete_model(model_id: str) -> None:
    ...
```

这些辅助函数不是第一版训练流程的必要条件，可以等大仓接入需求明确后再继续扩展。

### 推理接口，已实现

当前推理入口：

```python
def predict(request: PredictionRequest | dict) -> PredictionResult:
    ...
```

该函数负责：

1. 校验并归一化推理请求。
2. 根据 `model_id` 或 `model_path` 加载本地 predictor。
3. 将待预测序列转换为 GluonTS 推理数据集。
4. 执行预测。
5. 输出每条序列的预测开始时间、均值预测和分位数预测。

当前辅助函数：

```python
def load_predictor(model_id: str, artifact_root: str | Path) -> Predictor:
    ...

def predict_with_model(model_path: str | Path, dataset: DatasetSpec) -> PredictionResult:
    ...
```

## 训练请求格式

第一版推荐请求结构：

```json
{
  "model_name": "daily_sales_deepar",
  "algorithm": "deepar",
  "freq": "D",
  "prediction_length": 14,
  "dataset": {
    "series": [
      {
        "item_id": "store_001",
        "start": "2024-01-01",
        "target": [12.0, 15.5, 14.2, 18.1]
      }
    ]
  },
  "training": {
    "max_epochs": 10,
    "batch_size": 32,
    "num_batches_per_epoch": 50,
    "accelerator": "cpu"
  },
  "hyperparameters": {
    "context_length": 28,
    "num_layers": 2,
    "hidden_size": 40,
    "dropout_rate": 0.1
  },
  "evaluation": {
    "enabled": true,
    "test_length": 14,
    "num_workers": 0
  }
}
```

长时间序列也可以使用 CSV 数据源：

```json
{
  "model_name": "daily_sales_deepar",
  "algorithm": "deepar",
  "freq": "D",
  "prediction_length": 14,
  "dataset": {
    "type": "csv",
    "path": "data/train_series.csv",
    "format": "long",
    "item_id_column": "item_id",
    "timestamp_column": "timestamp",
    "target_column": "target"
  }
}
```

## 当前支持的模型

第一版提供两种可创建模型，每种模型拥有独立超参数。

### DeepAR

`algorithm` 使用：

```json
"deepar"
```

支持的 `hyperparameters`：

```json
{
  "context_length": 28,
  "num_layers": 2,
  "hidden_size": 40,
  "dropout_rate": 0.1,
  "lr": 0.001,
  "weight_decay": 0.00000001,
  "num_parallel_samples": 100,
  "nonnegative_pred_samples": false
}
```

### SimpleFeedForward

`algorithm` 使用：

```json
"simple_feedforward"
```

支持的 `hyperparameters`：

```json
{
  "context_length": 28,
  "hidden_dimensions": [40, 40],
  "lr": 0.001,
  "weight_decay": 0.00000001,
  "batch_norm": false
}
```

## 初始约束

- `algorithm` 第一版支持 `deepar` 和 `simple_feedforward`。
- `freq` 使用 GluonTS/Pandas 兼容频率，例如 `D`、`H`、`15min`。
- 每条序列必须包含 `start` 和数值型 `target`。
- `prediction_length` 必须大于 0。
- 如果开启评估，每条序列的 `target` 长度必须大于 `test_length`。
- 所有运行产物必须写入配置的本地模型根目录下。

## 训练结果格式

推荐返回结构：

```json
{
  "model_id": "model_20260603_172500_ab12cd",
  "model_name": "daily_sales_deepar",
  "algorithm": "deepar",
  "status": "completed",
  "model_path": "artifacts/models/model_20260603_172500_ab12cd/predictor",
  "metadata_path": "artifacts/models/model_20260603_172500_ab12cd/metadata.json",
  "metrics": {
    "MASE": 1.23,
    "MAPE": 0.08,
    "RMSE": 5.67,
    "mean_wQuantileLoss": 0.12
  }
}
```

如果训练失败，模块应该抛出专用异常，并携带足够上下文，方便大仓记录日志和向上层展示错误。

## 推理请求格式

推荐推理请求结构：

```json
{
  "model_id": "model_20260603_172500_ab12cd",
  "artifact_root": "artifacts/models",
  "dataset": {
    "series": [
      {
        "item_id": "store_001",
        "start": "2024-01-01",
        "target": [12.0, 15.5, 14.2, 18.1]
      }
    ]
  },
  "prediction": {
    "num_samples": 100,
    "quantiles": [0.1, 0.5, 0.9]
  }
}
```

也可以直接传入 `model_path`。如果 predictor 目录旁边存在训练时保存的 `request.json`，模块会自动读取其中的 `freq`；否则需要在请求中显式传入 `freq`：

```json
{
  "model_path": "artifacts/models/model_20260603_172500_ab12cd/predictor",
  "freq": "D",
  "dataset": {
    "series": [
      {
        "item_id": "store_001",
        "start": "2024-01-01",
        "target": [12.0, 15.5, 14.2, 18.1]
      }
    ]
  }
}
```

## 推理结果格式

推理返回结构：

```json
{
  "model_id": "model_20260603_172500_ab12cd",
  "model_path": "artifacts/models/model_20260603_172500_ab12cd/predictor",
  "forecasts": [
    {
      "item_id": "store_001",
      "start_date": "2024-01-05",
      "mean": [16.2, 17.1, 18.0],
      "quantiles": {
        "0.1": [12.3, 13.0, 13.8],
        "0.5": [16.0, 17.0, 18.1],
        "0.9": [20.5, 21.7, 22.4]
      }
    }
  ]
}
```

## 训练实现自查清单

后续开发时用这份清单检查实现是否完整。

- [x] 创建 `src/traingluonts/` 包。
- [x] 添加公共入口 `train_model()`。
- [x] 定义类型化的训练请求和训练结果结构。
- [x] 支持接收大仓传入的普通 `dict`，并完成归一化。
- [x] 将请求中的序列转换为 GluonTS `ListDataset`。
- [x] 开启评估时，正确拆分 train/test 数据。
- [x] 第一版支持 `deepar` 和 `simple_feedforward` 算法。
- [x] 将 estimator 创建逻辑隔离在 `estimators.py`。
- [x] 使用 `predictor.serialize(...)` 保存模型。
- [x] 保存 `request.json`、`metrics.json` 和 `metadata.json`。
- [x] 返回相对稳定的模型路径。
- [x] 防止运行产物写到配置的 artifact 根目录之外。
- [x] 添加一个通过模块入口训练的示例脚本。
- [x] 添加参数校验、数据集转换、最小训练流程的测试。
- [x] 提供 HTTP/FastAPI 适配层，并保持训练、推理核心逻辑复用 Python API。

## 推理实现自查清单

- [x] 创建 `src/traingluonts/inference.py`。
- [x] 定义 `PredictionRequest`、`PredictionSettings` 和 `PredictionResult`。
- [x] 支持通过 `model_id + artifact_root` 定位 predictor。
- [x] 支持通过 `model_path` 直接加载 predictor。
- [x] 复用 `dataset.py` 中的数据转换逻辑。
- [x] 支持设置 `num_samples` 和 `quantiles`。
- [x] 输出每条序列的 `item_id`、`start_date`、`mean` 和分位数。
- [x] 对不存在的模型路径抛出模块专用异常。
- [x] 添加 `examples/predict_via_module.py`。
- [x] 添加推理请求校验测试。
- [x] 添加“训练后立即加载并推理”的端到端测试。
- [x] 在 README 中把推理状态从规划更新为已实现。

## 当前示例

当前已有一个最小 GluonTS 示例：

```text
examples/basic_gluonts_usage.py
```

在仓库根目录运行：

```powershell
.\.venv\Scripts\python.exe examples\basic_gluonts_usage.py
```

该示例会用合成数据训练一个小型 DeepAR 模型，生成预测、计算评估指标，并将 predictor 保存到 `artifacts/gluonts_demo/`。

通过模块入口训练的示例：

```text
examples/train_via_module.py
```

运行方式：

```powershell
.\.venv\Scripts\python.exe examples\train_via_module.py
```

通过模块入口训练并推理的示例：

```text
examples/predict_via_module.py
```

运行方式：

```powershell
.\.venv\Scripts\python.exe examples\predict_via_module.py
```

测试和示例共用的合成数据生成逻辑位于：

```text
src/traingluonts/testing.py
```

二进制 CLI 开发期验证：

```powershell
.\.venv\Scripts\python.exe -m traingluonts.cli.main version --pretty
```

PyInstaller 打包入口：

```powershell
.\.venv\Scripts\python.exe -m traingluonts.packaging.build --mode onedir --clean
```
