# API 前端对接说明

本文档面向前端调用方，说明 TrainGluonTS FastAPI 服务的启动方式、接口路径、请求结构和响应结构。

当前 HTTP API 是现有本地 Python 接口的包装层：

- `POST /api/v1/train` 调用 `train_model(request)`。
- `POST /api/v1/predict` 调用 `predict(request)`。
- `POST /api/v1/predict-with-model` 调用 `predict_with_model(...)`。
- 模型检查接口调用 `load_model(...)`，只检查是否可加载，不返回 Python predictor 对象。
- `POST /api/v1/models/publish` 将训练产物复制到发布目录，返回发布后的模型路径。

前端和服务运行在同一台机器上，因此第一版不提供 CSV 文件上传。前端直接在 JSON 中传 CSV 文件路径。

## 启动服务

开发期启动：

```powershell
TRAINGLUONTS_API_HOST=0.0.0.0 \
.\.venv\Scripts\python.exe -m traingluonts.api.server
```

如果项目已安装到当前环境，也可以使用脚本入口：

```powershell
traingluonts-api
```

默认监听：

```text
http://127.0.0.1:8012
```

下文 curl 示例默认服务地址为 `http://127.0.0.1:8012`。示例使用 Bash/Git Bash 换行写法；如果在 Windows PowerShell 中 `curl` 被别名占用，请使用 `curl.exe`。

可用环境变量：

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `TRAINGLUONTS_API_HOST` | `127.0.0.1` | 服务监听地址 |
| `TRAINGLUONTS_API_PORT` | `8012` | 服务端口 |
| `TRAINGLUONTS_API_ARTIFACT_ROOT` | `artifacts/models` | 默认模型根目录 |
| `TRAINGLUONTS_API_PUBLISH_ROOT` | `artifacts/published_models` | 默认模型发布根目录 |
| `TRAINGLUONTS_API_DATA_ROOT` | `data` | 相对 CSV 路径的默认根目录 |
| `TRAINGLUONTS_API_ALLOW_ABSOLUTE_PATHS` | `true` | 是否允许前端传绝对路径 |
| `TRAINGLUONTS_API_CORS_ORIGINS` | `http://localhost:80,http://127.0.0.1:80` | CORS 允许来源，逗号分隔 |

## 通用响应

大部分接口成功：

```json
{
  "ok": true,
  "result": {}
}
```

失败：

```json
{
  "ok": false,
  "error": {
    "type": "TrainingRequestError",
    "message": "error detail"
  }
}
```

常见 HTTP 状态码：

| 状态码 | 场景 |
| --- | --- |
| `200` | 成功 |
| `400` | 训练或推理请求不合法 |
| `404` | 模型路径或任务不存在 |
| `422` | HTTP 请求体结构不合法 |
| `500` | 训练、推理或服务内部错误 |

注意：模型发布接口的业务错误，例如 `model_id` 不存在，会使用 HTTP `200` 返回，并在响应体 `code` 和 `message` 中表达业务状态。

## 路径规则

请求 JSON 中的路径字段包括：

- `dataset.path`
- `artifact_root`
- `model_path`
- 发布接口的目标路径由 `TRAINGLUONTS_API_PUBLISH_ROOT`、`user_id` 和清洗后的 `version` 自动生成，前端不直接传发布路径。

解析规则：

- 绝对路径直接使用，例如 `D:/data/train.csv`。
- 相对 `dataset.path` 会按 `TRAINGLUONTS_API_DATA_ROOT` 解析。
- 相对 `artifact_root` 和 `model_path` 会按服务进程当前工作目录解析。
- 如果 `TRAINGLUONTS_API_ALLOW_ABSOLUTE_PATHS=false`，绝对路径会被拒绝。

推荐前端直接传绝对 CSV 路径，最少歧义：

```json
{
  "dataset": {
    "type": "csv",
    "path": "D:/data/train_series.csv",
    "timestamp_column": "timestamp",
    "target_column": "target"
  }
}
```

## 健康检查

### GET `/api/v1/health`

curl：

```bash
curl -s http://127.0.0.1:8012/api/v1/health
```

响应：

```json
{
  "ok": true,
  "result": {
    "status": "healthy"
  }
}
```

### GET `/api/v1/version`

curl：

```bash
curl -s http://127.0.0.1:8012/api/v1/version
```

响应：

```json
{
  "ok": true,
  "result": {
    "version": "0.1.0"
  }
}
```

## 同步训练

### POST `/api/v1/train`

请求体与本地 `train_model(request)` 一致。

示例：

```json
{
  "model_name": "frontend_sales_demo",
  "algorithm": "simple_feedforward",
  "freq": "D",
  "prediction_length": 7,
  "artifact_root": "artifacts/models",
  "dataset": {
    "type": "csv",
    "path": "D:/data/train_series.csv",
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
    "hidden_dimensions": [32, 32]
  }
}
```

curl：

```bash
curl -s -X POST http://127.0.0.1:8012/api/v1/train \
  -H "Content-Type: application/json" \
  -d '{
    "model_name": "frontend_sales_demo",
    "algorithm": "simple_feedforward",
    "freq": "D",
    "prediction_length": 7,
    "artifact_root": "artifacts/models",
    "dataset": {
      "type": "csv",
      "path": "D:/data/train_series.csv",
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
      "hidden_dimensions": [32, 32]
    }
  }'
```

训练请求顶层字段：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `model_name` | `string` | 是 | 无 | 业务侧模型名称，用于标识模型用途；不决定算法 |
| `algorithm` | `string` | 是 | 无 | 模型算法，当前支持 `deepar` 和 `simple_feedforward` |
| `freq` | `string` | 是 | 无 | 时间频率，例如 `D`、`H`、`15min`、`30ms` |
| `prediction_length` | `integer` | 是 | 无 | 预测长度，必须大于 0；训练完成后推理输出长度由它决定 |
| `artifact_root` | `string` | 否 | `TRAINGLUONTS_API_ARTIFACT_ROOT` | 模型保存根目录，支持相对路径和绝对路径 |
| `dataset` | `object` | 是 | 无 | 训练数据配置，HTTP 前端对接推荐使用 CSV 路径 |
| `training` | `object` | 否 | 见下表 | 通用训练参数 |
| `evaluation` | `object` | 否 | 见下表 | 评估参数 |
| `hyperparameters` | `object` | 否 | `{}` | 当前算法的模型超参数 |

CSV 数据源字段：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `type` | `string` | 是 | 无 | 固定为 `csv` |
| `path` | `string` | 是 | 无 | CSV 文件路径，支持相对路径和绝对路径 |
| `format` | `string` | 否 | `long` | CSV 格式，当前只支持 `long` |
| `item_id_column` | `string` | 否 | `item_id` | 序列 id 列名；CSV 没有该列时按单序列处理 |
| `timestamp_column` | `string` | 是 | 无 | 时间戳列名 |
| `target_column` | `string` | 是 | 无 | 目标值列名 |

也可以直接传内嵌序列数据，适合小数据或调试：

```json
{
  "dataset": {
    "series": [
      {
        "item_id": "store_001",
        "start": "2024-01-01",
        "target": [12.0, 15.5, 14.2]
      }
    ]
  }
}
```

内嵌序列字段：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `series` | `object[]` | 是 | 无 | 时间序列数组，不能为空 |
| `series[].item_id` | `string` 或 `null` | 否 | `null` | 序列 id；不传时系统生成 `series_0`、`series_1` 等 |
| `series[].start` | `string` | 是 | 无 | 序列起始时间 |
| `series[].target` | `number[]` | 是 | 无 | 目标值数组，不能为空 |

`training` 字段：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `max_epochs` | `integer` | 否 | `5` | 最大训练轮数，必须大于 0 |
| `checkpoint_every_n_epochs` | `integer` | 否 | `100` | 每多少个 epoch 保存一次 checkpoint，必须大于 0 |
| `batch_size` | `integer` | 否 | `32` | batch 大小，必须大于 0 |
| `num_batches_per_epoch` | `integer` | 否 | `50` | 每轮 batch 数，必须大于 0 |
| `accelerator` | `string` | 否 | `cpu` | Lightning accelerator；CPU 部署建议使用 `cpu` |
| `enable_progress_bar` | `boolean` | 否 | `false` | 是否显示训练进度条 |
| `enable_model_summary` | `boolean` | 否 | `false` | 是否显示模型摘要 |
| `logger` | `boolean` | 否 | `false` | 是否启用 Lightning logger |

`evaluation` 字段：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `enabled` | `boolean` | 否 | `true` | 是否启用 holdout 评估 |
| `test_length` | `integer` 或 `null` | 否 | `null` | 测试集长度；未传时使用 `prediction_length` |
| `num_samples` | `integer` | 否 | `100` | 评估预测采样数，必须大于 0 |
| `num_workers` | `integer` | 否 | `0` | 评估指标计算 worker 数；`0` 表示单进程 |
| `quantiles` | `number[]` | 否 | `[0.1, 0.5, 0.9]` | 评估分位数，每个值必须在 0 到 1 之间 |

`evaluation.num_workers` 默认是 `0`。Windows、边端或容器环境建议保持 `0`，避免 multiprocessing/IPC 受限导致评估失败。

如果 `evaluation.enabled=true`，每条序列的 `target` 长度必须大于 `test_length`。如果 `evaluation.enabled=false`，每条序列的 `target` 长度必须至少为 `prediction_length`。

`algorithm="simple_feedforward"` 时，`hyperparameters` 支持：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `context_length` | `integer` 或 `null` | 否 | `null` | 上下文长度 |
| `hidden_dimensions` | `integer[]` | 否 | `[40, 40]` | 隐藏层维度列表，不能为空，且每项必须大于 0 |
| `lr` | `number` | 否 | `0.001` | 学习率，必须大于 0 |
| `weight_decay` | `number` | 否 | `0.00000001` | 权重衰减，必须大于等于 0 |
| `batch_norm` | `boolean` | 否 | `false` | 是否启用 batch norm |

`algorithm="deepar"` 时，`hyperparameters` 支持：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `context_length` | `integer` 或 `null` | 否 | `null` | 上下文长度 |
| `num_layers` | `integer` | 否 | `2` | RNN 层数，必须大于 0 |
| `hidden_size` | `integer` | 否 | `40` | 隐藏层大小，必须大于 0 |
| `dropout_rate` | `number` | 否 | `0.1` | dropout，范围 `[0, 1)` |
| `lr` | `number` | 否 | `0.001` | 学习率，必须大于 0 |
| `weight_decay` | `number` | 否 | `0.00000001` | 权重衰减，必须大于等于 0 |
| `num_parallel_samples` | `integer` | 否 | `100` | 并行采样数，必须大于 0 |
| `nonnegative_pred_samples` | `boolean` | 否 | `false` | 是否裁剪为非负预测样本 |

未知字段会被拒绝。`hyperparameters` 中也不能传入当前算法不支持的字段。

训练 CSV long format 示例：

```csv
item_id,timestamp,target
store_001,2024-01-01,12.0
store_001,2024-01-02,15.5
store_001,2024-01-03,14.2
store_002,2024-01-01,9.0
store_002,2024-01-02,10.1
store_002,2024-01-03,11.3
```

CSV 规则：

- 必须包含 `timestamp_column` 和 `target_column`。
- 如果包含 `item_id_column`，会按该列分组为多条序列。
- 如果没有 `item_id_column`，整个 CSV 会作为一条序列。
- 每组会按时间戳升序排序。
- 当前不自动补齐缺失时间点。

响应：

```json
{
  "ok": true,
  "result": {
    "model_id": "model_20260608_100000_ab12cd",
    "model_name": "frontend_sales_demo",
    "algorithm": "simple_feedforward",
    "status": "completed",
    "model_path": "D:\\GitRepo\\TrainGluonTS\\artifacts\\models\\model_20260608_100000_ab12cd\\predictor",
    "metadata_path": "D:\\GitRepo\\TrainGluonTS\\artifacts\\models\\model_20260608_100000_ab12cd\\metadata.json",
    "metrics": {
      "MASE": 1.23,
      "MAPE": 0.08,
      "RMSE": 5.67,
      "mean_wQuantileLoss": 0.12
    }
  }
}
```

训练响应字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `ok` | `boolean` | 是否成功 |
| `result.model_id` | `string` | 训练生成的模型 id |
| `result.model_name` | `string` | 请求中的模型名称 |
| `result.algorithm` | `string` | 请求中的模型算法 |
| `result.status` | `string` | 当前固定为 `completed` |
| `result.model_path` | `string` | predictor 目录路径，推理时可直接传入 |
| `result.metadata_path` | `string` | metadata 文件路径 |
| `result.metrics` | `object` 或 `null` | 开启评估时返回指标；关闭评估时为 `null` |

`metrics` 常见字段：

| 字段 | 说明 |
| --- | --- |
| `MASE` | Mean Absolute Scaled Error |
| `MAPE` | Mean Absolute Percentage Error |
| `RMSE` | Root Mean Squared Error |
| `mean_wQuantileLoss` | 平均加权分位数损失 |

模型文件会保存在：

```text
{artifact_root}/{model_id}/
  predictor/
  request.json
  metrics.json
  metadata.json
```

同步训练会一直占用 HTTP 请求，前端正式使用推荐异步训练接口。

## 异步训练

### POST `/api/v1/train/jobs`

请求体：

```json
{
  "request": {
    "model_name": "frontend_sales_demo",
    "algorithm": "simple_feedforward",
    "freq": "D",
    "prediction_length": 7,
    "artifact_root": "artifacts/models",
    "dataset": {
      "type": "csv",
      "path": "D:/data/train_series.csv",
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
      "num_workers": 0
    },
    "hyperparameters": {
      "context_length": 14,
      "hidden_dimensions": [32, 32]
    }
  }
}
```

curl：

```bash
curl -s -X POST http://127.0.0.1:8012/api/v1/train/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "request": {
      "model_name": "frontend_sales_demo",
      "algorithm": "simple_feedforward",
      "freq": "D",
      "prediction_length": 7,
      "artifact_root": "artifacts/models",
      "dataset": {
        "type": "csv",
        "path": "D:/data/train_series.csv",
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
        "num_workers": 0
      },
      "hyperparameters": {
        "context_length": 14,
        "hidden_dimensions": [32, 32]
      }
    }
  }'
```

响应：

```json
{
  "ok": true,
  "result": {
    "job_id": "4d8f6d24b6a64f43a6efca45de3b80b9",
    "status": "queued",
    "created_at": "2026-06-08T10:00:00Z",
    "updated_at": "2026-06-08T10:00:00Z",
    "result": null,
    "error": null
  }
}
```

异步训练创建请求字段：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `request` | `object` | 是 | 无 | 训练请求对象，字段与 `POST /api/v1/train` 完全一致 |

创建任务响应字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `ok` | `boolean` | 是否成功创建任务 |
| `result.job_id` | `string` | 训练任务 id，用于轮询状态 |
| `result.status` | `string` | 创建后通常为 `queued` |
| `result.created_at` | `string` | 任务创建时间，ISO 8601 字符串 |
| `result.updated_at` | `string` | 任务最近更新时间，ISO 8601 字符串 |
| `result.result` | `object` 或 `null` | 任务完成前为 `null` |
| `result.error` | `object` 或 `null` | 任务失败前为 `null` |

### GET `/api/v1/train/jobs/{job_id}`

curl：

```bash
curl -s http://127.0.0.1:8012/api/v1/train/jobs/4d8f6d24b6a64f43a6efca45de3b80b9
```

完成响应：

```json
{
  "ok": true,
  "result": {
    "job_id": "4d8f6d24b6a64f43a6efca45de3b80b9",
    "status": "completed",
    "created_at": "2026-06-08T10:00:00Z",
    "updated_at": "2026-06-08T10:00:10Z",
    "result": {
      "model_id": "model_20260608_100000_ab12cd",
      "model_name": "frontend_sales_demo",
      "algorithm": "simple_feedforward",
      "status": "completed",
      "model_path": "D:\\GitRepo\\TrainGluonTS\\artifacts\\models\\model_20260608_100000_ab12cd\\predictor",
      "metadata_path": "D:\\GitRepo\\TrainGluonTS\\artifacts\\models\\model_20260608_100000_ab12cd\\metadata.json",
      "metrics": {
        "MASE": 1.23,
        "MAPE": 0.08,
        "RMSE": 5.67,
        "mean_wQuantileLoss": 0.12
      }
    },
    "error": null
  }
}
```

任务查询响应字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `ok` | `boolean` | 是否成功查询任务 |
| `result.job_id` | `string` | 训练任务 id |
| `result.status` | `string` | 任务状态，可能是 `queued`、`running`、`completed`、`failed` |
| `result.created_at` | `string` | 任务创建时间，ISO 8601 字符串 |
| `result.updated_at` | `string` | 任务最近更新时间，ISO 8601 字符串 |
| `result.result` | `object` 或 `null` | `completed` 时为完整训练响应内容；其他状态通常为 `null` |
| `result.error` | `object` 或 `null` | `failed` 时包含 `type` 和 `message` |

失败响应中 `status` 为 `failed`，错误详情在 `error` 字段。

注意：第一版 job store 是内存实现，服务重启后历史 job 状态会丢失。模型文件本身仍保存在 `artifact_root`。

## 推理

### POST `/api/v1/predict`

请求体与本地 `predict(request)` 一致。

示例：

```json
{
  "model_id": "model_20260608_100000_ab12cd",
  "artifact_root": "artifacts/models",
  "dataset": {
    "type": "csv",
    "path": "D:/data/predict_series.csv",
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

curl：

```bash
curl -s -X POST http://127.0.0.1:8012/api/v1/predict \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "model_20260608_100000_ab12cd",
    "artifact_root": "artifacts/models",
    "dataset": {
      "type": "csv",
      "path": "D:/data/predict_series.csv",
      "format": "long",
      "item_id_column": "item_id",
      "timestamp_column": "timestamp",
      "target_column": "target"
    },
    "prediction": {
      "num_samples": 100,
      "quantiles": [0.1, 0.5, 0.9]
    }
  }'
```

推理请求顶层字段：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `dataset` | `object` | 是 | 无 | 待预测数据配置，HTTP 前端对接推荐使用 CSV 路径 |
| `model_id` | `string` 或 `null` | 条件必填 | `null` | 模型 id；与 `model_path` 至少传一个 |
| `model_path` | `string` 或 `null` | 条件必填 | `null` | predictor 路径；与 `model_id` 至少传一个 |
| `artifact_root` | `string` | 否 | `TRAINGLUONTS_API_ARTIFACT_ROOT` | 使用 `model_id` 时的模型根目录 |
| `freq` | `string` 或 `null` | 条件必填 | `null` | 序列频率；无法从模型旁边的 `request.json` 读取时必须传 |
| `prediction` | `object` | 否 | 见下表 | 推理参数 |

`model_id` 和 `model_path` 至少需要提供一个。若二者都提供，当前实现优先使用 `model_path` 作为 predictor 路径，返回结果仍保留传入的 `model_id`。

推理 CSV 数据源字段：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `type` | `string` | 是 | 无 | 固定为 `csv` |
| `path` | `string` | 是 | 无 | CSV 文件路径，支持相对路径和绝对路径 |
| `format` | `string` | 否 | `long` | CSV 格式，当前只支持 `long` |
| `item_id_column` | `string` | 否 | `item_id` | 序列 id 列名；CSV 没有该列时按单序列处理 |
| `timestamp_column` | `string` | 是 | 无 | 时间戳列名 |
| `target_column` | `string` | 是 | 无 | 历史观测值列名 |

`prediction` 字段：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `num_samples` | `integer` | 否 | `100` | 预测采样数，必须大于 0 |
| `quantiles` | `number[]` | 否 | `[0.1, 0.5, 0.9]` | 输出分位数，每个值必须在 0 到 1 之间 |

推理请求约束：

- `dataset.path` 指向的 CSV 必须存在。
- `model_path` 指向的 predictor 目录必须存在。
- 使用 `model_id` 时，实际加载路径是 `{artifact_root}/{model_id}/predictor`。
- 如果没有同级 `request.json` 可读取训练频率，必须显式传 `freq`。
- 输出数组长度由模型训练时的 `prediction_length` 决定，不由推理请求单独指定。

响应：

```json
{
  "ok": true,
  "result": {
    "model_id": "model_20260608_100000_ab12cd",
    "model_path": "D:\\GitRepo\\TrainGluonTS\\artifacts\\models\\model_20260608_100000_ab12cd\\predictor",
    "forecasts": [
      {
        "item_id": "store_001",
        "start_date": "2024-03-02",
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

推理响应字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `ok` | `boolean` | 是否成功 |
| `result.model_id` | `string` 或 `null` | 请求中传入的模型 id；纯 `model_path` 推理时为 `null` |
| `result.model_path` | `string` | 实际加载的 predictor 路径 |
| `result.forecasts` | `object[]` | 预测结果数组，每条输入序列对应一项 |

`forecasts` 中每一项对应一条输入序列：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `item_id` | `string` 或 `null` | 序列 id |
| `start_date` | `string` | 预测窗口起始时间 |
| `mean` | `number[]` | 均值预测数组，长度等于模型训练时的 `prediction_length` |
| `quantiles` | `object` | 分位数预测数组，key 为请求中的分位数 |

## 使用模型路径推理

### POST `/api/v1/predict-with-model`

适用于前端已经拿到 predictor 目录路径的场景。

```json
{
  "model_path": "D:/models/model_20260608_100000_ab12cd/predictor",
  "freq": "D",
  "dataset": {
    "type": "csv",
    "path": "D:/data/predict_series.csv",
    "timestamp_column": "timestamp",
    "target_column": "target"
  },
  "prediction": {
    "num_samples": 100,
    "quantiles": [0.5]
  }
}
```

curl：

```bash
curl -s -X POST http://127.0.0.1:8012/api/v1/predict-with-model \
  -H "Content-Type: application/json" \
  -d '{
    "model_path": "D:/models/model_20260608_100000_ab12cd/predictor",
    "freq": "D",
    "dataset": {
      "type": "csv",
      "path": "D:/data/predict_series.csv",
      "timestamp_column": "timestamp",
      "target_column": "target"
    },
    "prediction": {
      "num_samples": 100,
      "quantiles": [0.5]
    }
  }'
```

请求字段：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `model_path` | `string` | 是 | 无 | predictor 目录路径，可以直接使用训练响应中的 `result.model_path` |
| `freq` | `string` 或 `null` | 条件必填 | `null` | 序列频率；无法从模型旁边的 `request.json` 读取时必须传 |
| `dataset` | `object` | 是 | 无 | 待预测数据配置，字段同 `POST /api/v1/predict` |
| `prediction` | `object` | 否 | 见推理参数表 | 推理参数 |

响应结构与 `POST /api/v1/predict` 相同。纯 `model_path` 推理时，响应中的 `result.model_id` 为 `null`。

如果 predictor 旁边存在训练时保存的 `request.json`，`freq` 可以省略；如果没有，则必须显式传入。

## 模型加载检查

HTTP 接口不能返回 Python predictor 对象，因此只提供可加载性检查。

### POST `/api/v1/models/load-check`

使用 `model_id`：

```json
{
  "model_id": "model_20260608_100000_ab12cd",
  "artifact_root": "artifacts/models"
}
```

curl：

```bash
curl -s -X POST http://127.0.0.1:8012/api/v1/models/load-check \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "model_20260608_100000_ab12cd",
    "artifact_root": "artifacts/models"
  }'
```

使用 `model_path`：

```json
{
  "model_path": "D:/models/model_20260608_100000_ab12cd/predictor"
}
```

curl：

```bash
curl -s -X POST http://127.0.0.1:8012/api/v1/models/load-check \
  -H "Content-Type: application/json" \
  -d '{
    "model_path": "D:/models/model_20260608_100000_ab12cd/predictor"
  }'
```

请求字段：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `model_id` | `string` 或 `null` | 条件必填 | `null` | 模型 id；与 `model_path` 至少传一个 |
| `model_path` | `string` 或 `null` | 条件必填 | `null` | predictor 路径；与 `model_id` 至少传一个 |
| `artifact_root` | `string` 或 `null` | 否 | `TRAINGLUONTS_API_ARTIFACT_ROOT` | 使用 `model_id` 时的模型根目录 |

如果同时传 `model_id` 和 `model_path`，当前实现优先检查 `model_path`。

响应：

```json
{
  "ok": true,
  "result": {
    "loadable": true,
    "model_id": "model_20260608_100000_ab12cd",
    "model_path": "D:\\GitRepo\\TrainGluonTS\\artifacts\\models\\model_20260608_100000_ab12cd\\predictor",
    "checked_at": "2026-06-08T10:00:00Z"
  }
}
```

响应字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `ok` | `boolean` | 是否成功完成检查 |
| `result.loadable` | `boolean` | 是否可加载；成功响应中固定为 `true` |
| `result.model_id` | `string` 或 `null` | 请求中传入的模型 id |
| `result.model_path` | `string` | 实际检查的 predictor 路径 |
| `result.checked_at` | `string` | 检查时间，ISO 8601 字符串 |

### GET `/api/v1/models/{model_id}/load-check`

使用默认 `TRAINGLUONTS_API_ARTIFACT_ROOT` 检查模型。

curl：

```bash
curl -s http://127.0.0.1:8012/api/v1/models/model_20260608_100000_ab12cd/load-check
```

## 模型发布

### POST `/api/v1/models/publish`

将训练好的模型复制到发布目录，并用用户 id 与版本号建立稳定路径。源模型只通过 `model_id` 指定，服务会从默认 `TRAINGLUONTS_API_ARTIFACT_ROOT` 查找：

```text
{TRAINGLUONTS_API_ARTIFACT_ROOT}/{model_id}
```

发布目标根目录由 `TRAINGLUONTS_API_PUBLISH_ROOT` 配置，默认是 `artifacts/published_models`。目标路径格式为：

```text
{TRAINGLUONTS_API_PUBLISH_ROOT}/{user_id}/{清洗后的 version}
```

版本号允许中文。`/`、`\`、`:`、`*`、`?`、`"`、`<`、`>`、`|` 等不适合作为路径片段的字符会被替换为 `_`。如果相同 `user_id + version` 已经发布过，当前实现会覆盖旧发布目录。

请求体：

```json
{
  "model_id": "model_20260608_100000_ab12cd",
  "user_id": 1001,
  "version": "版本1/正式"
}
```

发布请求字段：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `model_id` | `string` | 是 | 无 | 要发布的训练模型 id；源路径为 `{TRAINGLUONTS_API_ARTIFACT_ROOT}/{model_id}` |
| `user_id` | `integer` | 是 | 无 | 前端或平台用户 id，用于生成发布目录 |
| `version` | `string` | 是 | 无 | 发布版本号，允许中文 |

模型发布接口使用独立的前端业务响应格式：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "path": "D:/models/published/1001/v1"
  }
}
```

curl：

```bash
curl -s -X POST http://127.0.0.1:8012/api/v1/models/publish \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "model_20260608_100000_ab12cd",
    "user_id": 1001,
    "version": "版本1/正式"
  }'
```

成功响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "path": "D:\\GitRepo\\TrainGluonTS\\artifacts\\published_models\\1001\\版本1_正式"
  }
}
```

如果源模型不存在，HTTP 状态仍为 `200`，错误信息放在 `code` 和 `message`：

```json
{
  "code": 404,
  "message": "model_id not found in artifact root: model_missing",
  "data": {}
}
```

发布响应字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | `integer` | 业务状态码；成功为 `0` |
| `message` | `string` | 业务状态说明；成功为 `success` |
| `data.path` | `string` | 发布后的模型根目录，里面包含 `predictor/`、`request.json`、`metadata.json` 等文件 |

版本号中的 `/`、`\`、`:`、`*`、`?`、`"`、`<`、`>`、`|` 等不适合作为路径片段的字符会被替换为 `_`。如果相同 `user_id + version` 已经发布过，当前实现会覆盖旧发布目录。

前端判断发布结果时应读取响应体中的 `code`，不要只看 HTTP 状态码。

## 前端推荐流程

```text
1. 前端准备本地 CSV 路径。
2. 调 POST /api/v1/train/jobs 发起训练。
3. 轮询 GET /api/v1/train/jobs/{job_id}。
4. 训练 completed 后保存 model_id 和 model_path。
5. 调 POST /api/v1/predict 执行推理。
6. 展示 forecasts 中的 mean 和 quantiles。
7. 需要发布时，调 POST /api/v1/models/publish，保存返回的 data.path。
```
