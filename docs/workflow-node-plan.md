# 工作流二进制推理节点开发计划

## 目标

新增一个面向数据分析工作流的二进制节点入口，只提供推理能力，不包含训练能力。

该节点由平台启动后常驻运行，通过 ZeroMQ 非 Multipart 模式接收上游 JSON 数据，并返回工作流后续节点需要的预测结果。

## 已明确边界

- 只做推理，不支持训练、评估或模型保存。
- 只支持非 Multipart 通信，即平台使用 REQ，节点使用 REP。
- `pyzmq` 依赖已经添加到项目环境和依赖配置中，开发时直接使用。
- 模型路径由平台通过 `--model-path` 注入。
- `--zmq-endpoint`、`--zmq-protocol`、`--model-path` 由平台托管，不要求用户在启动参数中手动填写。
- 推理相关超参数和字段映射在节点启动时通过启动参数传入。
- 工作流输出只返回预测值，不返回分位数、模型路径、完整 forecast 元信息等冗余信息。
- 现有 `traingluonts train`、`traingluonts predict` 批处理 CLI 保持兼容，不作为本次节点入口直接改造。

## 节点命令入口

新增独立入口，建议命名为：

```text
traingluonts-workflow-node
```

源码结构建议：

```text
src/traingluonts/workflow_node/
  __init__.py
  main.py        # argparse、ZeroMQ REP 服务循环
  service.py     # 模型加载、单次请求处理、预测调用
  payloads.py    # 工作流 data 与 GluonTS DatasetSpec/输出行之间的转换
```

`pyproject.toml` 中新增脚本入口：

```toml
traingluonts-workflow-node = "traingluonts.workflow_node.main:main"
```

## 启动参数

节点必须解析平台托管参数：

```bash
--zmq-endpoint tcp://127.0.0.1:<port>
--zmq-protocol REQ
--model-path <已发布模型路径>
```

节点只接受 `--zmq-protocol REQ`。如果收到其他值，启动阶段直接返回非 0 退出码，并在 stderr 输出明确错误。

建议支持的业务启动参数：

```bash
--target_name <输入数据中的目标值字段>
--timestamp_name <输入数据中的时间字段，可选>
--start_time <无时间字段时使用的虚拟起始时间，可选，默认 1970-01-01 00:00:00>
--item_id_name <输入数据中的序列 ID 字段，可选>
--freq <GluonTS 频率，可选>
--num_samples <采样数量，可选，默认 100>
--output_name <输出预测字段名，可选，默认 predict_value>
```

为兼容 Python 参数习惯，也可以同时支持短横线别名：

```bash
--target-name
--timestamp-name
--start-time
--item-id-name
--num-samples
--output-name
```

`freq` 的解析优先级：

1. 启动参数 `--freq`。
2. `--model-path` 对应模型目录旁的 `request.json`。
3. 如果仍无法解析，则启动失败或首次请求返回 `code: 500`，错误信息提示必须提供 `--freq`。

## 输入协议

节点接收平台发送的 JSON 字符串，格式遵循 `docs/binary-workflow-node-doc.md`：

```json
{
  "data": [
    {
      "time": "2026-05-25T08:24:00",
      "RF_FWD_PWR": 448.47
    }
  ]
}
```

校验规则：

- 请求必须是 JSON object。
- `data` 必须是非空数组。
- `data` 中每个元素必须是 object。
- 每行必须包含 `--target_name` 指定字段。
- 如果指定了 `--timestamp_name`，第一行必须包含该字段，用于构造序列起始时间。
- 如果未指定 `--timestamp_name`，使用 `--start_time` 作为虚拟序列起点。
- 如果未指定 `--item_id_name`，默认把整批数据视为单条序列 `series_0`。
- 如果指定 `--item_id_name`，按该字段分组，分别构造多条序列。

## 推理处理流程

启动阶段：

1. 解析启动参数。
2. 校验 `--zmq-protocol` 为 `REQ`。
3. 解析并校验 `--model-path`。
4. 将模型路径规范化：
   - 如果路径名是 `predictor`，直接作为 predictor 目录。
   - 如果路径下存在 `predictor/`，使用该子目录。
5. 加载 GluonTS predictor，常驻复用，避免每次请求重复加载模型。
6. 绑定 `--zmq-endpoint`，创建 REP socket。

每次请求：

1. 接收 JSON 字符串。
2. 校验并解析 `data`。
3. 根据启动参数把行数据转换为 GluonTS `DatasetSpec`。
4. 调用已加载 predictor 执行预测。
5. 只提取 forecast mean 作为预测结果。
6. 返回统一 JSON 响应。

## 输出协议

成功响应：

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

输出字段规则：

- `data` 始终是数组，便于平台后续节点继续处理。
- 每个预测步输出一行。
- 默认预测字段名为 `predict_value`。
- 如果启动参数传入 `--output_name y_hat`，则预测字段改为 `y_hat`。
- 多序列预测时保留 `item_id`。
- 不返回 `quantiles`。
- 不返回 `model_path`。
- 不返回完整 `forecasts` 结构。

错误响应：

```json
{
  "code": 500,
  "message": "missing target field: RF_FWD_PWR",
  "data": {}
}
```

错误响应仍通过 REP socket 返回，不让进程因为单次坏请求退出。启动参数错误、模型加载失败、端口绑定失败这类启动期问题可以直接非 0 退出。

## 代码改动清单

1. 新增 `src/traingluonts/workflow_node/` 模块。
2. 新增工作流节点脚本入口 `traingluonts-workflow-node`。
3. 新增数据转换函数：
   - 工作流 `data` 行列表到 `DatasetSpec`。
   - GluonTS forecast mean 到工作流输出行。
4. 新增 predictor 复用逻辑，避免请求级重复加载模型。
5. 扩展 PyInstaller 打包逻辑，支持打包工作流节点入口。
6. 新增或更新文档，说明工作流节点二进制构建与平台配置方式。
7. 保留原有 CLI 和 HTTP API 行为，不改动现有响应结构。

## 打包计划

当前 `traingluonts.packaging.build` 固定打包 CLI 入口。建议增加目标参数：

```bash
python -m traingluonts.packaging.build \
  --target workflow-node \
  --name traingluonts-workflow-node \
  --mode onedir \
  --clean
```

`--target cli` 继续打包现有批处理 CLI，保持默认兼容。

## 测试计划

单元测试：

- 参数解析：REQ 合法，非 REQ 被拒绝。
- 模型路径规范化：支持 predictor 目录和模型根目录。
- 输入校验：缺少 `data`、空数组、缺少目标字段、目标字段不可转 float。
- 数据转换：单序列、多序列都能正确生成 GluonTS 数据集。
- 输出转换：只包含预测值，不包含 quantiles、model_path、完整 forecasts。

集成测试：

- 启动 REP 节点，使用测试 REQ 客户端发送 JSON。
- 验证成功响应 `code/message/data` 格式。
- 验证坏请求返回 `code: 500` 且进程继续可处理下一次请求。

可选手工验证：

```bash
traingluonts-workflow-node \
  --zmq-endpoint tcp://127.0.0.1:55555 \
  --zmq-protocol REQ \
  --model-path artifacts/models/<model_id>/predictor \
  --target_name RF_FWD_PWR \
  --timestamp_name time \
  --freq min
```

## 不实现

- Multipart / DEALER / ROUTER 流式响应。
- 训练能力。
- 分位数输出。
- HTTP 服务能力。
- 每次请求动态传入模型路径或超参数。
- 多模型热切换。
