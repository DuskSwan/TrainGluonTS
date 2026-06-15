# 二进制包前端对接说明

本文档面向前端或外部进程调用方，说明 TrainGluonTS 二进制包的两种前端对接方式：

- 离线 CLI 二进制：通过命令行执行 `version/train/predict`。
- 工作流节点二进制：作为平台“AI数据分析二进制”节点，通过 ZeroMQ 接收数据并返回预测结果。

如果需要了解如何从源码构建二进制包，请看：

```text
docs/binary-developer-usage.md
```

## 离线 CLI 二进制

### 程序位置

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

### 最小接入流程

前端或外部进程只需要按下面的顺序调用：

1. 准备训练 CSV 和 `train_request.json`。
2. 执行 `traingluonts train`，等待进程结束。
3. 读取 `train_result.json`，判断 `ok`。
4. 成功后保存 `result.model_id` 和 `result.model_path`。
5. 准备推理 CSV 和 `predict_request.json`。
6. 执行 `traingluonts predict`。
7. 读取 `predict_result.json`，展示 `forecasts` 中的 `mean` 和 `quantiles`。

### 命令总览

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

### 版本接口

版本接口用于检查二进制程序是否能正常启动，以及确认当前程序版本。

命令：

```bash
./dist/traingluonts/traingluonts version --pretty
```

成功响应：

```json
{
  "ok": true,
  "version": "0.1.0"
}
```

字段说明：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `ok` | `boolean` | 是否成功 |
| `version` | `string` | TrainGluonTS 包版本 |

### 推荐目录结构

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

### 路径规则

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

### 训练请求

训练接口会读取请求 JSON 和 CSV 数据，完成模型训练、按需评估，并把模型产物写入 `artifact_root`。

命令：

```bash
./dist/traingluonts/traingluonts train \
  --input edge_job/train_request.json \
  --output edge_job/results/train_result.json \
  --pretty
```

命令参数：

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `--input` | 是 | 训练请求 JSON 文件路径 |
| `--output` | 否 | 训练结果 JSON 文件路径；不传则输出到 stdout |
| `--pretty` | 否 | 格式化 JSON 输出 |

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
| `checkpoint_every_n_epochs` | `integer` | 否 | `100` | 每多少个 epoch 保存一次 checkpoint，必须大于 0 |
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

### 训练响应

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

### 推理请求

推理接口会加载已保存的 predictor，对输入 CSV 中的历史序列继续预测。

命令：

```bash
./dist/traingluonts/traingluonts predict \
  --input edge_job/predict_request.json \
  --output edge_job/results/predict_result.json \
  --pretty
```

命令参数：

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `--input` | 是 | 推理请求 JSON 文件路径 |
| `--output` | 否 | 推理结果 JSON 文件路径；不传则输出到 stdout |
| `--pretty` | 否 | 格式化 JSON 输出 |

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

推理请求顶层字段：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `dataset` | `object` | 是 | 无 | 待预测数据配置，二进制调用推荐使用 CSV |
| `model_id` | `string` 或 `null` | 条件必填 | `null` | 模型 id；与 `model_path` 至少传一个 |
| `model_path` | `string` 或 `null` | 条件必填 | `null` | predictor 路径；与 `model_id` 至少传一个 |
| `artifact_root` | `string` | 否 | `artifacts/models` | 使用 `model_id` 时的模型根目录 |
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

### 推理响应

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

### 失败响应

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

常见错误类型：

| `error.type` | 常见原因 |
| --- | --- |
| `CliArgumentError` | 命令行参数不合法 |
| `CliInputError` | 输入 JSON 文件不存在、无法读取或不是合法 JSON |
| `TrainingRequestError` | 训练请求字段不合法、CSV 缺列、目标列无法转数值 |
| `PredictionRequestError` | 推理请求字段不合法，例如未传 `model_id` 或 `model_path` |
| `ModelRegistryError` | 模型路径不存在或无法加载 |
| `ModelTrainingError` | 训练、评估或模型保存过程失败 |
| `ModelPredictionError` | 推理执行过程失败 |

前端或外部进程建议处理流程：

1. 执行命令。
2. 检查进程退出码。
3. 读取 `--output` 指定的 JSON 文件，或读取 stdout。
4. 判断 `ok`。
5. 成功时读取 `result`，失败时读取 `error.type` 和 `error.message`。

### 常见注意事项

- `onedir` 部署时必须整体复制 `dist/traingluonts/`，不能只复制单个 `traingluonts` 文件。
- 如果程序没有执行权限，先运行 `chmod +x dist/traingluonts/traingluonts`。
- 二进制程序不提供 HTTP 服务，只通过命令行输入输出 JSON。
- 模型产物不包含在二进制包内，由训练请求中的 `artifact_root` 决定保存位置。
- CPU 运行时如果看到 `Can't initialize NVML`，通常只是 Torch 检测不到 NVIDIA/NVML，不影响 CPU 训练和推理。
- Ubuntu 边端或容器环境建议保持 `evaluation.num_workers=0`，避免多进程评估受系统权限限制。

## 工作流节点二进制

### 适用范围

该二进制节点只用于数据分析工作流中的模型推理。

- 可执行程序：`traingluonts-workflow-node`
- 通信方式：ZeroMQ 非 Multipart
- 平台客户端 socket：REQ
- 节点服务端 socket：REP
- 是否支持训练：不支持
- 是否支持 Multipart：不支持
- 输出内容：只返回预测结果，不返回分位数、模型路径或完整 forecast 信息

### 前端节点配置

在平台自定义节点中选择：

```text
AI数据分析二进制
```

推荐配置如下：

| 配置项 | 值 |
| --- | --- |
| 可执行文件路径 | `traingluonts-workflow-node` 的绝对路径 |
| 进程运行目录 | 二进制所在目录，或平台约定的工作目录 |
| Multipart 模式 | 关闭 |
| 是否需要模型 | 开启 |
| 启动等待秒数 | 建议 `2` 到 `10`，视模型加载耗时调整 |
| 启动参数 | 只填写业务参数，不填写平台托管参数 |

如果是一体化部署的 onefile 产物，可执行文件路径示例：

```text
/opt/traingluonts/bin/traingluonts-workflow-node
```

如果是 onedir 产物，可执行文件路径示例：

```text
/opt/traingluonts/traingluonts-workflow-node/traingluonts-workflow-node
```

### 平台托管参数

以下参数由平台启动进程时自动追加，前端不要让用户手动填写到“启动参数”中：

```bash
--zmq-endpoint tcp://127.0.0.1:<port>
--zmq-protocol REQ
--model-path <已发布模型路径>
```

说明：

| 参数 | 说明 |
| --- | --- |
| `--zmq-endpoint` | 平台分配的本地 ZeroMQ 地址 |
| `--zmq-protocol` | 固定传 `REQ` |
| `--model-path` | 平台选择的已发布模型路径，可以是模型根目录或 `predictor` 目录 |

节点只接受 `--zmq-protocol REQ`。如果传入其他值，进程会启动失败。

### 启动参数

前端需要在“启动参数”中配置字段映射和推理参数。

最小示例：

```bash
--target_name RF_FWD_PWR --freq 30ms
```

带时间列示例：

```bash
--target_name RF_FWD_PWR --timestamp_name time --freq 30ms
```

多序列分组示例：

```bash
--target_name RF_FWD_PWR --timestamp_name time --item_id_name sensor_id --freq 30ms
```

自定义输出字段名示例：

```bash
--target_name RF_FWD_PWR --timestamp_name time --freq 30ms --output_name predict_value
```

参数清单：

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `--target_name` | 是 | 无 | 输入行中作为时间序列目标值的字段名 |
| `--timestamp_name` | 否 | 无 | 输入行中的时间字段名 |
| `--start_time` | 否 | `1970-01-01 00:00:00` | 没有时间字段时使用的虚拟序列起点 |
| `--item_id_name` | 否 | 无 | 多序列分组字段名 |
| `--freq` | 否 | 从模型 `request.json` 读取 | 时间频率，必须和训练时一致 |
| `--num_samples` | 否 | `100` | 预测采样数，越大均值越稳定但越慢 |
| `--output_name` | 否 | `predict_value` | 输出预测值字段名 |

参数也支持短横线写法：

```text
--target-name
--timestamp-name
--start-time
--item-id-name
--num-samples
--output-name
```

### 字段含义

`target_name` 是模型真正用于推理的数值字段。

例如：

```bash
--target_name RF_FWD_PWR
```

表示节点会从每一行中读取 `RF_FWD_PWR`，组成时间序列。

`timestamp_name` 是时间字段。它不是模型目标值，但会用于确定序列起点。如果输入数据没有时间列，可以不传 `timestamp_name`，节点会使用 `start_time` 作为虚拟起点。

`item_id_name` 是分组字段。它不会作为数值输入进入模型，只用于把一批数据拆成多条时间序列，并在输出中标识每条序列。

例如：

```bash
--item_id_name sensor_id
```

输入数据会按 `sensor_id` 分组，分别预测。

### freq 说明

`freq` 表示输入时间序列相邻两个点的时间间隔，必须和训练模型时保持一致。

常见示例：

| `freq` | 含义 |
| --- | --- |
| `30ms` | 30 毫秒一个点 |
| `50ms` | 50 毫秒一个点 |
| `1s` | 1 秒一个点 |
| `5min` | 5 分钟一个点 |
| `D` | 1 天一个点 |

如果不传 `--freq`，节点会尝试从模型目录旁的 `request.json` 中读取训练时保存的 `freq`。

`prediction_length` 来自训练好的模型，不由工作流请求动态传入。例如模型训练时 `prediction_length=3`，则一次请求会返回 3 个预测步。

### 输入 JSON

平台通过 ZeroMQ 发送 JSON 字符串。根对象必须包含 `data` 字段。

单序列示例：

```json
{
  "data": [
    {
      "time": "2026-05-25T08:24:00",
      "RF_FWD_PWR": 448.47,
      "RF_REF_PWR": 9.69
    },
    {
      "time": "2026-05-25T08:24:00.030",
      "RF_FWD_PWR": 447.52,
      "RF_REF_PWR": 9.59
    }
  ]
}
```

对应启动参数：

```bash
--target_name RF_FWD_PWR --timestamp_name time --freq 30ms
```

多序列示例：

```json
{
  "data": [
    {
      "sensor_id": "A",
      "time": "2026-05-25T08:24:00",
      "RF_FWD_PWR": 448.47
    },
    {
      "sensor_id": "A",
      "time": "2026-05-25T08:24:00.030",
      "RF_FWD_PWR": 447.52
    },
    {
      "sensor_id": "B",
      "time": "2026-05-25T08:24:00",
      "RF_FWD_PWR": 310.12
    }
  ]
}
```

对应启动参数：

```bash
--target_name RF_FWD_PWR --timestamp_name time --item_id_name sensor_id --freq 30ms
```

输入校验规则：

- 请求必须是 JSON object。
- `data` 必须是非空数组。
- `data` 中每个元素必须是 JSON object。
- 每行必须包含 `target_name` 指定字段。
- `target_name` 对应值必须能转为数字。
- 如果配置了 `timestamp_name`，每条序列的第一行必须包含该字段。
- 如果配置了 `item_id_name`，每行必须包含该字段且不能为空。

### 成功响应

节点返回统一 JSON：

```json
{
  "code": 200,
  "message": "success",
  "type": "timeseries",
  "data": [
    {
      "item_id": "series_0",
      "step": 1,
      "predict_value": 451.2
    },
    {
      "item_id": "series_0",
      "step": 2,
      "predict_value": 452.7
    }
  ]
}
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `code` | 成功时为 `200` |
| `message` | 成功时为 `success` |
| `type` | 当前固定为 `timeseries`，表示时间序列推理结果 |
| `data` | 预测结果数组 |
| `item_id` | 序列 ID；未配置 `item_id_name` 时为 `series_0` |
| `step` | 第几个预测步，从 `1` 开始 |
| `predict_value` | 预测值字段，字段名可由 `--output_name` 修改 |

如果配置了：

```bash
--output_name predicted
```

则响应字段会变成：

```json
{
  "item_id": "series_0",
  "step": 1,
  "predicted": 451.2
}
```

### 错误响应

单次请求出错时，节点不会退出，会返回：

```json
{
  "code": 500,
  "message": "missing target field: RF_FWD_PWR",
  "type": "timeseries",
  "data": {}
}
```

前端处理建议：

- `code == 200`：读取 `data`。
- `code != 200`：展示或记录 `message`。
- `type == "timeseries"`：按时间序列预测结果处理。
- 不要依赖 HTTP 状态码；这是 ZeroMQ JSON 协议。

启动期错误，例如模型路径不存在、协议不是 REQ、端口绑定失败，会导致进程非 0 退出，平台应按外部进程启动失败处理。

### 本地联调命令

onefile 产物示例：

```bash
/opt/traingluonts/bin/traingluonts-workflow-node \
  --zmq-endpoint tcp://127.0.0.1:55555 \
  --zmq-protocol REQ \
  --model-path /opt/traingluonts/models/model_20260605_100000_ab12cd/predictor \
  --target_name RF_FWD_PWR \
  --timestamp_name time \
  --freq 30ms
```

onedir 产物示例：

```bash
/opt/traingluonts/traingluonts-workflow-node/traingluonts-workflow-node \
  --zmq-endpoint tcp://127.0.0.1:55555 \
  --zmq-protocol REQ \
  --model-path /opt/traingluonts/models/model_20260605_100000_ab12cd/predictor \
  --target_name RF_FWD_PWR \
  --timestamp_name time \
  --freq 30ms
```

平台正式运行时，不需要前端手动拼接 `--zmq-endpoint`、`--zmq-protocol` 和 `--model-path`，这些参数由平台托管。

### 前端配置建议

建议前端把用户可配置项限制在以下字段：

| 前端字段 | 对应启动参数 | 控件建议 |
| --- | --- | --- |
| 目标值字段 | `--target_name` | 必填输入框或字段下拉 |
| 时间字段 | `--timestamp_name` | 可选输入框或字段下拉 |
| 虚拟起始时间 | `--start_time` | 可选输入框 |
| 分组字段 | `--item_id_name` | 可选输入框或字段下拉 |
| 时间频率 | `--freq` | 输入框，默认从模型读取 |
| 采样数 | `--num_samples` | 数字输入，默认 `100`，必须大于 `0` |
| 输出字段名 | `--output_name` | 输入框，默认 `predict_value` |

建议前端隐藏或禁止用户填写：

- `--zmq-endpoint`
- `--zmq-protocol`
- `--model-path`

建议默认值：

```text
num_samples = 100
output_name = predict_value
start_time = 1970-01-01 00:00:00
Multipart 模式 = 关闭
是否需要模型 = 开启
```

### 常见问题

#### 输入没有时间字段怎么办？

可以不配置 `timestamp_name`。节点会使用 `start_time` 作为虚拟序列起点。只要输入行顺序正确，并且 `freq` 与训练时一致，就可以推理。

#### item_id_name 是要忽略的字段吗？

不是。`item_id_name` 是分组字段，不作为数值输入进入模型，但会决定哪些行属于同一条序列，并会出现在输出结果中。

#### num_samples 是从 100 个点里抽一个吗？

不是。`num_samples` 是概率预测采样条数。节点最终返回这些采样结果的均值。数值越大通常越稳定，但推理更慢。

#### 为什么返回多个 step？

返回的 step 数量由模型训练时的 `prediction_length` 决定，不由本次工作流请求决定。

#### 为什么没有 quantiles？

工作流节点当前只返回预测均值，避免给后续节点传递过多字段。CLI 和 HTTP 推理接口仍可以返回分位数。
