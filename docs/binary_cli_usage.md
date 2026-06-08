# 二进制 CLI 使用说明

本文档面向前端或外部进程调用方，说明在已经拿到 Linux 二进制包后，如何通过命令行执行训练和推理。

如果需要了解如何从源码构建二进制包，请看：

```text
docs/binary_packaging_usage.md
```

## 程序位置

当前推荐使用 Linux `onedir` 产物，目录结构通常是：

```text
dist/
  traingluonts/
    traingluonts
    _internal/
      ...
```

部署时需要整体复制 `dist/traingluonts/` 目录，不能只复制 `traingluonts` 文件。

以下示例假设程序路径是：

```bash
./dist/traingluonts/traingluonts
```

如果部署目录不同，把命令中的程序路径替换为实际路径即可。

## 最小接入流程

前端或外部进程只需要按下面的顺序调用：

1. 准备训练 CSV 和 `train_request.json`。
2. 执行 `traingluonts train`，等待进程结束。
3. 读取 `train_result.json`，判断 `ok`。
4. 成功后保存 `result.model_id` 和 `result.model_path`。
5. 准备推理 CSV 和 `predict_request.json`。
6. 执行 `traingluonts predict`。
7. 读取 `predict_result.json`，展示 `forecasts` 中的 `mean` 和 `quantiles`。

## 命令总览

查看版本：

```bash
./dist/traingluonts/traingluonts version --pretty
```

训练：

```bash
./dist/traingluonts/traingluonts train \
  --input edge_job/train_request.json \
  --output edge_job/results/train_result.json \
  --pretty
```

推理：

```bash
./dist/traingluonts/traingluonts predict \
  --input edge_job/predict_request.json \
  --output edge_job/results/predict_result.json \
  --pretty
```

参数说明：

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `--input` | 训练/推理必填 | 请求 JSON 文件路径 |
| `--output` | 否 | 输出 JSON 文件路径；不传则输出到 stdout |
| `--pretty` | 否 | 格式化 JSON 输出，方便人工查看 |

## 推荐目录结构

前端或外部进程可以按下面的方式组织一次任务：

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
    train_result.json
    predict_result.json
```

## 路径规则

请求 JSON 里的路径字段支持相对路径和绝对路径：

- `dataset.path`
- `artifact_root`
- `model_path`

相对路径会按 `--input` 指向的请求 JSON 所在目录解析。

例如命令是：

```bash
./dist/traingluonts/traingluonts train \
  --input edge_job/train_request.json \
  --output edge_job/results/train_result.json
```

而 `train_request.json` 中写：

```json
{
  "artifact_root": "models",
  "dataset": {
    "type": "csv",
    "path": "data/train_series.csv",
    "timestamp_column": "timestamp",
    "target_column": "target"
  }
}
```

实际解析为：

```text
edge_job/models
edge_job/data/train_series.csv
```

也可以直接传 Linux 绝对路径：

```json
{
  "artifact_root": "/opt/traingluonts/jobs/job_001/models",
  "dataset": {
    "type": "csv",
    "path": "/opt/traingluonts/jobs/job_001/data/train_series.csv",
    "timestamp_column": "timestamp",
    "target_column": "target"
  }
}
```

## 训练请求

`train_request.json` 示例：

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

顶层字段：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `model_name` | `string` | 是 | 无 | 业务侧模型名称，用于标识模型用途 |
| `algorithm` | `string` | 是 | 无 | 模型算法，当前支持 `deepar` 和 `simple_feedforward` |
| `freq` | `string` | 是 | 无 | 时间频率，例如 `D`、`H`、`15min` |
| `prediction_length` | `integer` | 是 | 无 | 预测长度，必须大于 0 |
| `artifact_root` | `string` | 否 | `artifacts/models` | 模型保存根目录，支持相对路径和绝对路径 |
| `dataset` | `object` | 是 | 无 | 训练数据配置，二进制调用推荐使用 CSV |
| `training` | `object` | 否 | 见下表 | 训练参数 |
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

`training` 字段：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `max_epochs` | `integer` | 否 | `5` | 最大训练轮数，必须大于 0 |
| `batch_size` | `integer` | 否 | `32` | batch 大小，必须大于 0 |
| `num_batches_per_epoch` | `integer` | 否 | `50` | 每轮 batch 数，必须大于 0 |
| `accelerator` | `string` | 否 | `cpu` | Lightning accelerator；Linux CPU 部署建议使用 `cpu` |
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

`evaluation.num_workers` 默认是 `0`。Ubuntu 边端或容器环境建议保持 `0`，避免 multiprocessing/IPC 受限导致 `Operation not permitted`。

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

## 训练响应

成功响应示例：

```json
{
  "ok": true,
  "result": {
    "model_id": "model_20260608_100000_ab12cd",
    "model_name": "daily_sales_simple_feedforward",
    "algorithm": "simple_feedforward",
    "status": "completed",
    "model_path": "/opt/traingluonts/edge_job/models/model_20260608_100000_ab12cd/predictor",
    "metadata_path": "/opt/traingluonts/edge_job/models/model_20260608_100000_ab12cd/metadata.json",
    "metrics": {
      "MASE": 1.23,
      "MAPE": 0.08,
      "RMSE": 5.67,
      "mean_wQuantileLoss": 0.12
    }
  }
}
```

调用方需要重点保存：

- `result.model_id`
- `result.model_path`

模型文件会保存在：

```text
{artifact_root}/{model_id}/
  predictor/
  request.json
  metrics.json
  metadata.json
```

## 推理请求

推荐直接使用训练响应中的 `model_path`：

```json
{
  "model_path": "/opt/traingluonts/edge_job/models/model_20260608_100000_ab12cd/predictor",
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

也可以使用 `model_id + artifact_root`：

```json
{
  "model_id": "model_20260608_100000_ab12cd",
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

推理 CSV 与训练 CSV 一样使用 long format。推理时 `target` 是历史观测值，模型会从序列末尾继续预测 `prediction_length` 个点。

## 推理响应

成功响应示例：

```json
{
  "ok": true,
  "result": {
    "model_id": null,
    "model_path": "/opt/traingluonts/edge_job/models/model_20260608_100000_ab12cd/predictor",
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

`forecasts` 中每一项对应一条输入序列：

| 字段 | 说明 |
| --- | --- |
| `item_id` | 序列 id |
| `start_date` | 预测窗口起始时间 |
| `mean` | 均值预测数组 |
| `quantiles` | 分位数预测数组，key 为请求中的分位数 |

## 失败响应

失败时程序会返回非 0 退出码，并输出统一 JSON：

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

前端或外部进程建议处理流程：

1. 执行命令。
2. 检查进程退出码。
3. 读取 `--output` 指定的 JSON 文件，或读取 stdout。
4. 判断 `ok`。
5. 成功时读取 `result`，失败时读取 `error.type` 和 `error.message`。

## 常见注意事项

- `onedir` 部署时必须整体复制 `dist/traingluonts/`，不能只复制单个 `traingluonts` 文件。
- 如果程序没有执行权限，先运行 `chmod +x dist/traingluonts/traingluonts`。
- 二进制程序不提供 HTTP 服务，只通过命令行输入输出 JSON。
- 模型产物不包含在二进制包内，由训练请求中的 `artifact_root` 决定保存位置。
- CPU 运行时如果看到 `Can't initialize NVML`，通常只是 Torch 检测不到 NVIDIA/NVML，不影响 CPU 训练和推理。
- Ubuntu 边端或容器环境建议保持 `evaluation.num_workers=0`，避免多进程评估受系统权限限制。
