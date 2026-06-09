# 第三方小模型接入数据分析工作流二进制节点指南

本文面向第三方算法/小模型开发者，说明如何把一个本地可执行程序接入平台“数据分析工作流”，作为二进制节点参与数据处理、预测、推理或结果流式输出。

## 适用场景

数据分析二进制节点适合接入以下第三方程序：

- 小模型推理程序，例如温控预测、设备异常检测、轻量时序预测。
- 数据处理程序，例如 CSV 行级处理、特征计算、规则判断。
- 工业控制辅助程序，例如共享内存数据处理、设备状态评估。
- 本地模型服务包装器，例如 Python/C++/Go/Rust 编译后的可执行文件。

第三方程序只需要提供一个可执行入口，平台会负责启动进程，并通过 ZeroMQ 与进程交换 JSON 数据。

## 接入方式概览

平台会在运行工作流时启动第三方程序，并自动追加通信参数：

```bash
--zmq-endpoint tcp://127.0.0.1:<port>
--zmq-protocol REQ
```

如果节点开启了“是否需要模型”，平台还会追加：

```bash
--model-path <已发布模型路径>
```

第三方程序需要实现：

1. 解析 `--zmq-endpoint`、`--zmq-protocol`、可选的 `--model-path`。
2. 在 `--zmq-endpoint` 上绑定 ZeroMQ 服务端 socket。
3. 接收平台发送的 JSON 行数据。
4. 返回 JSON 结果；如果开启 Multipart 模式，可以分多段返回。

## 自定义节点配置

在平台工作流页面进入“自定义节点”管理，创建节点时选择：

```text
AI数据分析二进制
```

关键配置如下：

| 配置项 | 说明 |
| --- | --- |
| 可执行文件路径 | 第三方程序的绝对路径，例如 `/opt/models/predictor` 或 `D:\models\predictor.exe` |
| 进程运行目录 | 程序启动时的工作目录，模型文件、配置文件可相对该目录读取 |
| 启动等待秒数 | 程序启动后需要加载模型或预热时填写，例如 `2` 或 `5` |
| Multipart 模式 | 关闭时使用 REQ；开启时使用 DEALER，支持流式或多段返回 |
| 是否需要模型 | 开启后平台会选择已发布模型，并通过 `--model-path` 传给程序 |
| 启动参数 | 第三方程序自己的参数，不要手动填写平台托管参数 |

以下参数由平台统一注入，第三方开发者不要在“启动参数”里手动配置：

- `--zmq-endpoint`
- `--zmq-protocol`
- `--model-path`

## 输入数据协议

数据分析二进制节点会读取上游数据集，并逐行发送 JSON。每次请求是一段数据（n行m列）。

示例：

```json
{
    "data": [
        {
            "time": "2026-05-25T08:24:00",
            "step_id": "Stabilize",
            "RF_FWD_PWR": 448.47,
            "RF_REF_PWR": 9.69
        },
        {
            "time": "2026-05-25T08:25:00",
            "step_id": "Stabilize",
            "RF_FWD_PWR": 447.52,
            "RF_REF_PWR": 9.59
        },
        {
            ...
        }
    ]
}
```

data 字段的内容为列表，其中每个元素是一个字典，以键值对形式描述一行数据。

## 非流式响应协议

关闭 Multipart 模式时，平台使用 REQ/REP 通信。第三方程序每收到一个 JSON，就返回一个 JSON 响应。

推荐响应格式：

```json
{
  "code": 200,
  "message": "success",
  "data": [
    {
        "target1": "12.34",
        "target2": "7",
    },
    {
        "target1": "56.78",
        "target2": "8",
    }
  ]
}
```

和输入的data格式一样，输出中的data以字典列表的形式描述数据，每个字典代表一行。

平台会取响应里的 `data` 作为当前行的输出结果。

如果程序直接返回业务对象，平台也能处理：

```json
{
  "predict_value": 451.2,
  "score": 0.93,
  "status": "normal"
}
```

但为了便于排查问题，推荐统一使用 `code/message/data`。

错误响应示例：

```json
{
  "code": 500,
  "message": "模型推理失败",
  "data": {
    "reason": "missing RF_FWD_PWR"
  }
}
```

## Multipart 流式/多段响应协议

数据分析二进制节点也支持 Multipart 模式。开启后，平台使用 DEALER socket，第三方程序可以对同一行输入返回多段结果。

适用场景：

- 单行推理会产生多个中间结果。
- 第三方模型希望实时输出进度。
- 结果需要分批返回到运行时图表或后续处理。
- 推理耗时较长，需要先返回阶段性结果。

每个分片建议返回：

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "time": "2026-05-25T08:24:00",
    "field": "RF_FWD_PWR",
    "stage": "feature_extract",
    "value": 448.47
  },
  "done": false
}
```

最后一个分片：

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "time": "2026-05-25T08:24:00",
    "predict_value": 451.2,
    "score": 0.93,
    "status": "normal"
  },
  "done": true
}
```

平台识别以下结束标记：

- `done: true`
- `finish_reason: "stop" | "finished" | "done" | "complete" | "completed"`
- `status: "stop" | "finished" | "done" | "complete" | "completed"`

如果返回 `code` 且不等于 `200`，平台会把该分片视为异常终止结果。

## ZeroMQ socket 对照

| 平台配置 | 平台客户端 socket | 第三方程序建议 socket | 用途 |
| --- | --- | --- | --- |
| Multipart 关闭 | REQ | REP | 一问一答 |
| Multipart 开启 | DEALER | ROUTER 或兼容 DEALER 的服务端实现 | 多段/流式返回 |

非流式模式更简单，建议第三方第一次接入时先使用非流式模式验证链路。

## Python 示例：非流式数据分析节点

```python
#!/usr/bin/env python
import argparse
import json

import zmq


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--zmq-endpoint", required=True)
    parser.add_argument("--zmq-protocol", default="REQ")
    parser.add_argument("--model-path", default="")
    return parser.parse_args()


def predict(row: dict) -> dict:
    fwd = float(row.get("RF_FWD_PWR") or 0)
    ref = float(row.get("RF_REF_PWR") or 0)
    return {
        "time": row.get("time"),
        "lot_id": row.get("lot_id"),
        "wafer_id": row.get("wafer_id"),
        "predict_value": fwd - ref,
        "score": 0.95,
        "status": "normal" if fwd > 0 else "invalid",
    }


def main():
    args = parse_args()
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind(args.zmq_endpoint)

    print(f"model_path={args.model_path}", flush=True)
    print(f"bind={args.zmq_endpoint}", flush=True)

    while True:
        text = socket.recv_string()
        try:
            row = json.loads(text)
            result = predict(row)
            socket.send_json({"code": 200, "message": "success", "data": result})
        except Exception as exc:
            socket.send_json({"code": 500, "message": str(exc), "data": {}})


if __name__ == "__main__":
    main()
```

## Python 示例：Multipart 多段数据分析节点

下面示例使用 ROUTER 接收 DEALER 客户端消息，并对同一行数据返回两段结果。

```python
#!/usr/bin/env python
import argparse
import json
import time

import zmq


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--zmq-endpoint", required=True)
    parser.add_argument("--zmq-protocol", default="DEALER")
    parser.add_argument("--model-path", default="")
    return parser.parse_args()


def main():
    args = parse_args()
    context = zmq.Context()
    socket = context.socket(zmq.ROUTER)
    socket.bind(args.zmq_endpoint)

    while True:
        frames = socket.recv_multipart()
        identity = frames[0]
        payload = frames[-1]

        try:
            row = json.loads(payload.decode("utf-8"))
            fwd = float(row.get("RF_FWD_PWR") or 0)
            ref = float(row.get("RF_REF_PWR") or 0)

            first = {
                "code": 200,
                "message": "success",
                "data": {
                    "time": row.get("time"),
                    "stage": "feature_extract",
                    "RF_FWD_PWR": fwd,
                    "RF_REF_PWR": ref,
                },
                "done": False,
            }
            socket.send_multipart([identity, json.dumps(first, ensure_ascii=False).encode("utf-8")])

            time.sleep(0.2)

            final = {
                "code": 200,
                "message": "success",
                "data": {
                    "time": row.get("time"),
                    "lot_id": row.get("lot_id"),
                    "predict_value": fwd - ref,
                    "score": 0.95,
                },
                "done": True,
            }
            socket.send_multipart([identity, json.dumps(final, ensure_ascii=False).encode("utf-8")])
        except Exception as exc:
            error = {"code": 500, "message": str(exc), "data": {}, "done": True}
            socket.send_multipart([identity, json.dumps(error, ensure_ascii=False).encode("utf-8")])


if __name__ == "__main__":
    main()
```

## 模型路径与启动参数

如果第三方程序需要加载模型，请在节点配置中开启“是否需要模型”。平台会把选择的已发布模型路径传给程序：

```bash
--model-path /path/to/model
```

第三方程序可以这样使用：

```python
if args.model_path:
    load_model(args.model_path)
```

其他启动参数可以在节点配置的“启动参数”里添加，例如：

```bash
--threshold 0.8
--mode fast
--config config.yaml
```

平台会把这些参数与托管参数一起传给第三方程序。

## 打包与部署建议

第三方程序建议满足以下要求：

- 能通过命令行直接启动。
- 标准输出和错误输出使用 UTF-8。
- 启动后不要立即退出，需要持续监听 ZeroMQ 请求。
- 不要固定端口，端口由 `--zmq-endpoint` 动态传入。
- 模型加载耗时较长时，配置合理的“启动等待秒数”。
- 单次处理耗时尽量控制在平台超时时间内；耗时较长时建议使用 Multipart 模式返回阶段性结果。
- 程序退出码非 0 时，平台会认为外部进程异常。

Linux 示例：

```bash
chmod +x /opt/vendor-model/bin/predictor
/opt/vendor-model/bin/predictor --zmq-endpoint tcp://127.0.0.1:55555 --zmq-protocol REQ
```

Windows 示例：

```powershell
D:\vendor-model\predictor.exe --zmq-endpoint tcp://127.0.0.1:55555 --zmq-protocol REQ
```

## 调试流程

1. 本地先单独启动第三方程序，确认可以绑定 `--zmq-endpoint`。
2. 使用简单 ZeroMQ 客户端发送一行 JSON，确认响应结构正确。
3. 在平台创建 `AI数据分析二进制` 自定义节点。
4. 填写可执行文件路径、运行目录、启动参数、模型配置。
5. 把自定义节点添加到数据分析工作流。
6. 连接上游 CSV、数据采集或其他数据源节点。
7. 点击“测试”，观察运行日志和节点输出。
8. 如果程序启动慢，增加“启动等待秒数”。
9. 如果单次推理慢或需要多段输出，开启 Multipart 模式。

## 常见问题

### 外部进程启动失败

检查：

- 可执行文件路径是否存在。
- 进程运行目录是否存在。
- Linux 下程序是否有执行权限。
- 启动参数是否能被程序正确解析。
- 程序启动后是否立即退出。
- 模型文件或配置文件路径是否正确。

### 等待外部响应超时

检查：

- 第三方程序是否已经绑定 `--zmq-endpoint`。
- REQ 模式下第三方服务端是否使用 REP。
- Multipart 模式下第三方服务端是否正确返回 multipart 消息。
- 单行推理是否超过平台等待时间。
- 是否需要增加启动等待秒数或改用 Multipart 模式。

### 开启模型后没有加载到模型

检查：

- 节点是否开启“是否需要模型”。
- 是否选择了模型类型。
- 是否选择了已发布模型。
- 已发布模型记录是否包含 `model_path`。
- 第三方程序是否解析了 `--model-path`。

### 后续节点拿不到字段

检查：

- 响应是否把业务结果放在 `data` 中。
- 字段名是否使用稳定英文名或下划线命名。
- 是否透传了必要的标准字段，例如 `time`、`lot_id`、`wafer_id`。
- Multipart 模式下最终分片是否包含后续节点需要的字段。

## 第三方交付清单

第三方交付二进制节点时，建议提供：

- 可执行文件或启动脚本。
- 运行目录及依赖文件。
- 模型文件或模型发布路径说明。
- 启动参数说明。
- 输入 JSON 示例。
- 非流式输出 JSON 示例。
- Multipart 输出 JSON 示例。
- 是否需要模型路径。
- 是否需要 Multipart 模式。
- 预估启动耗时。
- 单行推理平均耗时。
- 异常响应格式说明。
