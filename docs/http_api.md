# TrainGluonTS HTTP API 文档

本文档面向前端调用方，说明 TrainGluonTS FastAPI 服务的启动方式、接口路径、请求结构和响应结构。

当前 HTTP API 是现有本地 Python 接口的包装层：

- `POST /api/v1/train` 调用 `train_model(request)`。
- `POST /api/v1/predict` 调用 `predict(request)`。
- `POST /api/v1/predict-with-model` 调用 `predict_with_model(...)`。
- 模型检查接口调用 `load_model(...)`，只检查是否可加载，不返回 Python predictor 对象。

前端和服务运行在同一台机器上，因此第一版不提供 CSV 文件上传。前端直接在 JSON 中传 CSV 文件路径。

## 启动服务

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
http://127.0.0.1:8012
```

可用环境变量：

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `TRAINGLUONTS_API_HOST` | `127.0.0.1` | 服务监听地址 |
| `TRAINGLUONTS_API_PORT` | `8012` | 服务端口 |
| `TRAINGLUONTS_API_ARTIFACT_ROOT` | `artifacts/models` | 默认模型根目录 |
| `TRAINGLUONTS_API_DATA_ROOT` | `data` | 相对 CSV 路径的默认根目录 |
| `TRAINGLUONTS_API_ALLOW_ABSOLUTE_PATHS` | `true` | 是否允许前端传绝对路径 |
| `TRAINGLUONTS_API_CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | CORS 允许来源，逗号分隔 |

## 通用响应

成功：

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

## 路径规则

请求 JSON 中的路径字段包括：

- `dataset.path`
- `artifact_root`
- `model_path`

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

### GET `/api/v1/train/jobs/{job_id}`

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
      "model_path": "D:\\GitRepo\\TrainGluonTS\\artifacts\\models\\model_20260608_100000_ab12cd\\predictor"
    },
    "error": null
  }
}
```

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

使用 `model_path`：

```json
{
  "model_path": "D:/models/model_20260608_100000_ab12cd/predictor"
}
```

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

### GET `/api/v1/models/{model_id}/load-check`

使用默认 `TRAINGLUONTS_API_ARTIFACT_ROOT` 检查模型。

## 前端推荐流程

```text
1. 前端准备本地 CSV 路径。
2. 调 POST /api/v1/train/jobs 发起训练。
3. 轮询 GET /api/v1/train/jobs/{job_id}。
4. 训练 completed 后保存 model_id 和 model_path。
5. 调 POST /api/v1/predict 执行推理。
6. 展示 forecasts 中的 mean 和 quantiles。
```
