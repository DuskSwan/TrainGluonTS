# TrainGluonTS 接口文档

本文档面向外部 Python 项目调用方，说明 TrainGluonTS 当前公开接口的使用方式、输入输出结构、字段是否必填，以及常见异常。

本模块不提供 HTTP/FastAPI 服务。外部项目应直接通过 Python 函数调用。

## 导入方式

```python
from traingluonts import (
    load_model,
    load_predictor,
    predict,
    predict_with_model,
    train_model,
)
```

如果外部项目安装本模块，直接按上面导入即可。如果在本仓库内运行示例脚本，需要确保 `src` 在 Python import 路径中。

## 公共接口总览

| 接口 | 状态 | 用途 |
| --- | --- | --- |
| `train_model(request)` | 已实现 | 训练模型，评估并保存 predictor |
| `predict(request)` | 已实现 | 加载已保存 predictor 并执行推理 |
| `load_model(model_path_or_id, artifact_root=None)` | 已实现 | 加载 GluonTS predictor |
| `load_predictor(model_id, artifact_root="artifacts/models")` | 已实现 | 通过模型 id 加载 predictor |
| `predict_with_model(model_path, dataset, ...)` | 已实现 | 通过 predictor 路径直接推理 |

## 通用数据结构

训练和推理的 `dataset` 字段支持两种形式：

- `DatasetSpec`：直接在请求中传入 `series`。
- `DatasetCsvSpec`：传入 CSV 文件路径，由模块读取并转换成 `series`。

当时间序列较长时，推荐使用 `DatasetCsvSpec`，避免把大数组直接放进请求参数。

### DatasetSpec

直接传入时间序列数据。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `series` | `list[TimeSeriesItem]` | 是 | 无 | 时间序列列表，至少 1 条 |

### TimeSeriesItem

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `item_id` | `str \| None` | 否 | `None` | 序列 id；未传时模块按顺序生成 |
| `start` | `str` | 是 | 无 | 序列起始时间，例如 `"2024-01-01"` |
| `target` | `list[float]` | 是 | 无 | 数值序列，不能为空 |

示例：

```python
dataset = {
    "series": [
        {
            "item_id": "store_001",
            "start": "2024-01-01",
            "target": [12.0, 15.5, 14.2, 18.1],
        }
    ]
}
```

### DatasetCsvSpec

通过 CSV 文件路径传入时间序列数据。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `type` | `"csv"` | 是 | 无 | 固定为 `"csv"` |
| `path` | `str \| Path` | 是 | 无 | CSV 文件路径 |
| `format` | `"long"` | 否 | `"long"` | CSV 格式；当前只支持 long format |
| `item_id_column` | `str` | 否 | `"item_id"` | 序列 id 列名；CSV 没有该列时按单序列处理 |
| `timestamp_column` | `str` | 是 | 无 | 时间戳列名 |
| `target_column` | `str` | 是 | 无 | 目标值列名 |

CSV long format 示例：

```csv
item_id,timestamp,target
store_001,2024-01-01,12.0
store_001,2024-01-02,15.5
store_001,2024-01-03,14.2
store_002,2024-01-01,9.0
store_002,2024-01-02,10.1
store_002,2024-01-03,11.3
```

对应请求中的 `dataset`：

```python
dataset = {
    "type": "csv",
    "path": "data/train_series.csv",
    "format": "long",
    "item_id_column": "item_id",
    "timestamp_column": "timestamp",
    "target_column": "target",
}
```

CSV 转换规则：

1. 按 `item_id_column` 分组；如果 CSV 没有该列，则整个 CSV 作为一条序列。
2. 每组按 `timestamp_column` 升序排序。
3. 每组第一条时间作为 GluonTS `start`。
4. 每组 `target_column` 转为 `target` 数组。
5. 频率仍由请求中的 `freq` 字段提供。

当前约束：

- CSV 必须包含 `timestamp_column` 和 `target_column`。
- `target_column` 必须能转换为 float。
- 当前不自动补齐缺失时间点。
- 当前不处理动态特征列或静态特征列。

## train_model

训练模型，并将 predictor、训练请求、评估指标和 metadata 保存到本地。

### 函数签名

```python
def train_model(request: TrainingRequest | dict) -> TrainingResult:
    ...
```

### 输入字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `model_name` | `str` | 是 | 无 | 模型名称，用于标识业务含义 |
| `algorithm` | `"deepar" \| "simple_feedforward"` | 是 | 无 | 模型类型 |
| `freq` | `str` | 是 | 无 | GluonTS/Pandas 频率，例如 `"D"`、`"H"`、`"15min"` |
| `prediction_length` | `int` | 是 | 无 | 预测长度，必须大于 0 |
| `dataset` | `DatasetSpec \| DatasetCsvSpec` | 是 | 无 | 训练数据，支持内嵌序列或 CSV 路径 |
| `artifact_root` | `str \| Path` | 否 | `"artifacts/models"` | 模型保存根目录 |
| `training` | `TrainingSettings` | 否 | 见下表 | 通用训练参数 |
| `evaluation` | `EvaluationSettings` | 否 | 见下表 | 评估参数 |
| `hyperparameters` | `dict` | 否 | `{}` | 当前算法的模型超参数 |

未知字段会被拒绝。

### TrainingSettings

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `max_epochs` | `int` | 否 | `5` | 最大训练轮数，必须大于 0 |
| `checkpoint_every_n_epochs` | `int` | 否 | `100` | 每多少个 epoch 保存一次 checkpoint，必须大于 0 |
| `batch_size` | `int` | 否 | `32` | batch 大小，必须大于 0 |
| `num_batches_per_epoch` | `int` | 否 | `50` | 每轮 batch 数，必须大于 0 |
| `accelerator` | `str` | 否 | `"cpu"` | Lightning accelerator |
| `enable_progress_bar` | `bool` | 否 | `False` | 是否显示训练进度条 |
| `enable_model_summary` | `bool` | 否 | `False` | 是否显示模型摘要 |
| `logger` | `bool` | 否 | `False` | 是否启用 Lightning logger |

### EvaluationSettings

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `enabled` | `bool` | 否 | `True` | 是否启用 holdout 评估 |
| `test_length` | `int \| None` | 否 | `None` | 测试集长度；未传时使用 `prediction_length` |
| `num_samples` | `int` | 否 | `100` | 评估预测采样数，必须大于 0 |
| `num_workers` | `int` | 否 | `0` | 评估指标计算使用的 worker 数；`0` 表示单进程 |
| `quantiles` | `list[float]` | 否 | `[0.1, 0.5, 0.9]` | 评估分位数，值必须在 0 到 1 之间 |

如果 `evaluation.enabled=True`，每条 `target` 长度必须大于 `test_length`。如果 `evaluation.enabled=False`，每条 `target` 长度必须至少为 `prediction_length`。

### DeepAR 超参数

当 `algorithm="deepar"` 时，`hyperparameters` 支持以下字段：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `context_length` | `int \| None` | 否 | `None` | 上下文长度 |
| `num_layers` | `int` | 否 | `2` | RNN 层数，必须大于 0 |
| `hidden_size` | `int` | 否 | `40` | 隐藏层大小，必须大于 0 |
| `dropout_rate` | `float` | 否 | `0.1` | dropout，范围 `[0, 1)` |
| `lr` | `float` | 否 | `0.001` | 学习率，必须大于 0 |
| `weight_decay` | `float` | 否 | `0.00000001` | 权重衰减，必须大于等于 0 |
| `num_parallel_samples` | `int` | 否 | `100` | 并行采样数，必须大于 0 |
| `nonnegative_pred_samples` | `bool` | 否 | `False` | 是否裁剪为非负预测样本 |

未知超参数会被拒绝。

### SimpleFeedForward 超参数

当 `algorithm="simple_feedforward"` 时，`hyperparameters` 支持以下字段：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `context_length` | `int \| None` | 否 | `None` | 上下文长度 |
| `hidden_dimensions` | `list[int]` | 否 | `[40, 40]` | 隐藏层维度列表，不能为空，且每项必须大于 0 |
| `lr` | `float` | 否 | `0.001` | 学习率，必须大于 0 |
| `weight_decay` | `float` | 否 | `0.00000001` | 权重衰减，必须大于等于 0 |
| `batch_norm` | `bool` | 否 | `False` | 是否启用 batch norm |

未知超参数会被拒绝。

### 输入示例

直接传入 `series`：

```python
from traingluonts import train_model

result = train_model(
    {
        "model_name": "daily_sales_deepar",
        "algorithm": "deepar",
        "freq": "D",
        "prediction_length": 14,
        "artifact_root": "artifacts/models",
        "dataset": {
            "series": [
                {
                    "item_id": "store_001",
                    "start": "2024-01-01",
                    "target": [12.0, 15.5, 14.2, 18.1, 19.0, 20.2, 18.8],
                }
            ]
        },
        "training": {
            "max_epochs": 5,
            "checkpoint_every_n_epochs": 100,
            "batch_size": 32,
            "num_batches_per_epoch": 50,
            "accelerator": "cpu",
        },
        "evaluation": {
            "enabled": True,
            "test_length": 3,
            "num_samples": 100,
            "num_workers": 0,
            "quantiles": [0.1, 0.5, 0.9],
        },
        "hyperparameters": {
            "context_length": 28,
            "num_layers": 2,
            "hidden_size": 40,
        },
    }
)
```

使用 CSV 文件：

```python
result = train_model(
    {
        "model_name": "daily_sales_deepar",
        "algorithm": "deepar",
        "freq": "D",
        "prediction_length": 14,
        "artifact_root": "artifacts/models",
        "dataset": {
            "type": "csv",
            "path": "data/train_series.csv",
            "timestamp_column": "timestamp",
            "target_column": "target",
            "item_id_column": "item_id",
        },
        "training": {
            "max_epochs": 5,
            "checkpoint_every_n_epochs": 100,
            "batch_size": 32,
            "num_batches_per_epoch": 50,
            "accelerator": "cpu",
        },
        "evaluation": {
            "enabled": True,
            "test_length": 14,
            "num_workers": 0,
        },
        "hyperparameters": {
            "context_length": 28,
            "num_layers": 2,
            "hidden_size": 40,
        },
    }
)
```

### 返回值 TrainingResult

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `model_id` | `str` | 模型 id，例如 `model_20260604_120000_ab12cd` |
| `model_name` | `str` | 请求中的模型名称 |
| `algorithm` | `str` | 模型类型 |
| `status` | `"completed"` | 训练完成状态 |
| `model_path` | `str` | predictor 保存路径 |
| `metadata_path` | `str` | metadata 文件路径 |
| `metrics` | `dict[str, float] \| None` | 评估指标；未启用评估时为 `None` |

返回对象是 Pydantic model，可属性访问，也可转成 dict：

```python
print(result.model_id)
print(result.model_path)
payload = result.model_dump(mode="json")
```

### 训练输出文件

默认写入：

```text
artifacts/models/{model_id}/
  predictor/
  request.json
  metrics.json
  metadata.json
```

## predict

加载已保存的 predictor，对输入时间序列执行推理。

### 函数签名

```python
def predict(request: PredictionRequest | dict) -> PredictionResult:
    ...
```

### 输入字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `dataset` | `DatasetSpec \| DatasetCsvSpec` | 是 | 无 | 待预测数据，支持内嵌序列或 CSV 路径 |
| `model_id` | `str \| None` | 条件必填 | `None` | 模型 id；与 `model_path` 至少传一个 |
| `model_path` | `str \| Path \| None` | 条件必填 | `None` | predictor 路径；与 `model_id` 至少传一个 |
| `artifact_root` | `str \| Path` | 否 | `"artifacts/models"` | 使用 `model_id` 时的模型根目录 |
| `freq` | `str \| None` | 条件必填 | `None` | 序列频率；当无法从模型旁边的 `request.json` 读取时必须传 |
| `prediction` | `PredictionSettings` | 否 | 见下表 | 推理参数 |

`model_id` 和 `model_path` 至少需要提供一个。若二者都提供，当前实现优先使用 `model_path` 作为 predictor 路径，但返回结果仍保留传入的 `model_id`。

### PredictionSettings

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `num_samples` | `int` | 否 | `100` | 预测采样数，必须大于 0 |
| `quantiles` | `list[float]` | 否 | `[0.1, 0.5, 0.9]` | 输出分位数，值必须在 0 到 1 之间 |

### 使用 model_id 推理

如果模型由 `train_model` 保存，推荐使用 `model_id + artifact_root`。模块会读取训练时保存的 `request.json` 获取 `freq`。

```python
from traingluonts import predict

prediction = predict(
    {
        "model_id": "model_20260604_120000_ab12cd",
        "artifact_root": "artifacts/models",
        "dataset": {
            "series": [
                {
                    "item_id": "store_001",
                    "start": "2024-01-01",
                    "target": [12.0, 15.5, 14.2, 18.1],
                }
            ]
        },
        "prediction": {
            "num_samples": 100,
            "quantiles": [0.1, 0.5, 0.9],
        },
    }
)
```

使用 CSV 文件推理：

```python
prediction = predict(
    {
        "model_id": "model_20260604_120000_ab12cd",
        "artifact_root": "artifacts/models",
        "dataset": {
            "type": "csv",
            "path": "data/predict_series.csv",
            "timestamp_column": "timestamp",
            "target_column": "target",
            "item_id_column": "item_id",
        },
        "prediction": {
            "num_samples": 100,
            "quantiles": [0.1, 0.5, 0.9],
        },
    }
)
```

### 使用 model_path 推理

如果 predictor 目录旁边存在 `request.json`，可以不传 `freq`：

```python
prediction = predict(
    {
        "model_path": "artifacts/models/model_20260604_120000_ab12cd/predictor",
        "dataset": {
            "series": [
                {
                    "item_id": "store_001",
                    "start": "2024-01-01",
                    "target": [12.0, 15.5, 14.2, 18.1],
                }
            ]
        },
    }
)
```

如果只有孤立的 predictor 目录，没有同级 `request.json`，必须显式传 `freq`：

```python
prediction = predict(
    {
        "model_path": "D:/models/my_predictor",
        "freq": "D",
        "dataset": {
            "series": [
                {
                    "item_id": "store_001",
                    "start": "2024-01-01",
                    "target": [12.0, 15.5, 14.2, 18.1],
                }
            ]
        },
    }
)
```

### 返回值 PredictionResult

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `model_id` | `str \| None` | 请求中传入的模型 id；使用纯 `model_path` 时为 `None` |
| `model_path` | `str` | 实际加载的 predictor 路径 |
| `forecasts` | `list[ForecastResult]` | 每条序列的预测结果 |

### ForecastResult

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `item_id` | `str \| None` | 序列 id |
| `start_date` | `str` | 预测窗口起始时间 |
| `mean` | `list[float]` | 均值预测，长度等于模型的 `prediction_length` |
| `quantiles` | `dict[str, list[float]]` | 分位数预测，例如 `"0.5"` |

示例：

```python
first = prediction.forecasts[0]
print(first.item_id)
print(first.start_date)
print(first.mean)
print(first.quantiles["0.5"])
```

## load_model

加载已序列化的 GluonTS `PyTorchPredictor`。

### 函数签名

```python
def load_model(model_path_or_id: str | Path, artifact_root: Path | None = None):
    ...
```

### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `model_path_or_id` | `str \| Path` | 是 | 无 | predictor 路径，或模型 id |
| `artifact_root` | `Path \| None` | 否 | `None` | 传模型 id 时使用的模型根目录 |

如果传入 `artifact_root` 且 `model_path_or_id` 不是已存在路径，模块会按如下路径加载：

```text
{artifact_root}/{model_id}/predictor
```

### 返回值

返回 GluonTS `PyTorchPredictor`。

### 示例

```python
from pathlib import Path
from traingluonts import load_model

predictor = load_model("model_20260604_120000_ab12cd", Path("artifacts/models"))
```

## load_predictor

通过模型 id 加载 predictor，是 `load_model(model_id, artifact_root)` 的便捷封装。

### 函数签名

```python
def load_predictor(model_id: str, artifact_root: str | Path = "artifacts/models"):
    ...
```

### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `model_id` | `str` | 是 | 无 | 模型 id |
| `artifact_root` | `str \| Path` | 否 | `"artifacts/models"` | 模型根目录 |

### 返回值

返回 GluonTS `PyTorchPredictor`。

## predict_with_model

通过 predictor 路径直接推理，是 `predict(...)` 的便捷封装。

### 函数签名

```python
def predict_with_model(
    model_path: str | Path,
    dataset,
    *,
    freq: str | None = None,
    num_samples: int = 100,
    quantiles: list[float] | None = None,
) -> PredictionResult:
    ...
```

### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `model_path` | `str \| Path` | 是 | 无 | predictor 路径 |
| `dataset` | `DatasetSpec \| DatasetCsvSpec \| dict` | 是 | 无 | 待预测数据，支持内嵌序列或 CSV 路径 |
| `freq` | `str \| None` | 条件必填 | `None` | 无法从 `request.json` 读取频率时必须传 |
| `num_samples` | `int` | 否 | `100` | 预测采样数 |
| `quantiles` | `list[float] \| None` | 否 | `[0.1, 0.5, 0.9]` | 输出分位数 |

### 返回值

返回 `PredictionResult`。

### 示例

```python
from traingluonts import predict_with_model

prediction = predict_with_model(
    "artifacts/models/model_20260604_120000_ab12cd/predictor",
    {
        "series": [
            {
                "item_id": "store_001",
                "start": "2024-01-01",
                "target": [12.0, 15.5, 14.2, 18.1],
            }
        ]
    },
    freq="D",
    num_samples=100,
    quantiles=[0.1, 0.5, 0.9],
)
```

## 异常

模块会抛出以下专用异常，调用方可按需捕获。

| 异常 | 触发场景 |
| --- | --- |
| `TrainingRequestError` | 训练请求参数不合法 |
| `ModelTrainingError` | 训练、评估或保存过程失败 |
| `PredictionRequestError` | 推理请求参数不合法，例如没有传 `model_id` 或 `model_path` |
| `ModelPredictionError` | 推理执行过程失败 |
| `ModelRegistryError` | 模型路径不存在或 registry 操作失败 |

示例：

```python
from traingluonts import predict
from traingluonts.errors import PredictionRequestError, ModelRegistryError

try:
    result = predict({"dataset": {"series": []}})
except PredictionRequestError as exc:
    print(f"推理请求不合法: {exc}")
except ModelRegistryError as exc:
    print(f"模型路径错误: {exc}")
```

## 最小端到端示例

```python
from traingluonts import predict, train_model

training_request = {
    "model_name": "demo_model",
    "algorithm": "simple_feedforward",
    "freq": "D",
    "prediction_length": 3,
    "dataset": {
        "series": [
            {
                "item_id": "series_0",
                "start": "2024-01-01",
                "target": [
                    10.0,
                    11.0,
                    12.0,
                    13.0,
                    14.0,
                    15.0,
                    16.0,
                    17.0,
                    18.0,
                    19.0,
                    20.0,
                    21.0,
                ],
            }
        ]
    },
    "training": {
        "max_epochs": 1,
        "checkpoint_every_n_epochs": 100,
        "batch_size": 1,
        "num_batches_per_epoch": 1,
        "accelerator": "cpu",
    },
    "evaluation": {
        "enabled": True,
        "test_length": 3,
        "num_workers": 0,
    },
    "hyperparameters": {
        "context_length": 3,
        "hidden_dimensions": [8],
    },
}

training_result = train_model(training_request)

prediction_result = predict(
    {
        "model_id": training_result.model_id,
        "dataset": training_request["dataset"],
    }
)

print(prediction_result.forecasts[0].mean)
```
