# TrainGluonTS 工作流二进制节点前端接入说明

本文面向前端和平台工作流配置方，说明 TrainGluonTS 工作流二进制节点如何配置、启动参数如何填写、平台需要发送什么 JSON、节点会返回什么 JSON。

## 适用范围

该二进制节点只用于数据分析工作流中的模型推理。

- 可执行程序：`traingluonts-workflow-node`
- 通信方式：ZeroMQ 非 Multipart
- 平台客户端 socket：REQ
- 节点服务端 socket：REP
- 是否支持训练：不支持
- 是否支持 Multipart：不支持
- 输出内容：只返回预测结果，不返回分位数、模型路径或完整 forecast 信息

## 前端节点配置

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

## 平台托管参数

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

## 启动参数

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

## 字段含义

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

## freq 说明

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

## 输入 JSON

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

## 成功响应

节点返回统一 JSON：

```json
{
  "code": 200,
  "message": "success",
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

## 错误响应

单次请求出错时，节点不会退出，会返回：

```json
{
  "code": 500,
  "message": "missing target field: RF_FWD_PWR",
  "data": {}
}
```

前端处理建议：

- `code == 200`：读取 `data`。
- `code != 200`：展示或记录 `message`。
- 不要依赖 HTTP 状态码；这是 ZeroMQ JSON 协议。

启动期错误，例如模型路径不存在、协议不是 REQ、端口绑定失败，会导致进程非 0 退出，平台应按外部进程启动失败处理。

## 本地联调命令

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

## 前端配置建议

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

## 常见问题

### 输入没有时间字段怎么办？

可以不配置 `timestamp_name`。节点会使用 `start_time` 作为虚拟序列起点。只要输入行顺序正确，并且 `freq` 与训练时一致，就可以推理。

### item_id_name 是要忽略的字段吗？

不是。`item_id_name` 是分组字段，不作为数值输入进入模型，但会决定哪些行属于同一条序列，并会出现在输出结果中。

### num_samples 是从 100 个点里抽一个吗？

不是。`num_samples` 是概率预测采样条数。节点最终返回这些采样结果的均值。数值越大通常越稳定，但推理更慢。

### 为什么返回多个 step？

返回的 step 数量由模型训练时的 `prediction_length` 决定，不由本次工作流请求决定。

### 为什么没有 quantiles？

工作流节点当前只返回预测均值，避免给后续节点传递过多字段。CLI 和 HTTP 推理接口仍可以返回分位数。
