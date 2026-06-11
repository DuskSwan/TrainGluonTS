# API 路线开发计划

本文档记录 TrainGluonTS API 路线的定位、边界和后续维护计划。

## 路线定位

API 路线分为两层：

- Python 本地 API：核心业务接口，供 Python 项目直接调用。
- HTTP/FastAPI API：面向前端或外部服务的 HTTP 包装层，复用 Python 本地 API。

Python API 是核心实现，HTTP API 是适配层。二者应共享同一套 schema、数据转换、模型训练、模型加载、推理和错误处理逻辑。

## 当前能力

- 支持训练模型。
- 支持同步推理。
- 支持通过 `model_id + artifact_root` 加载模型。
- 支持通过 `model_path` 加载模型。
- 支持 CSV 数据输入。
- 支持同步 HTTP 训练和推理。
- 支持异步训练 job。
- 支持模型加载检查。
- 支持 HTTP 模型发布，将训练产物复制到可配置发布目录。

## 文档分工

- `docs/api-developer-usage.md`：面向 Python 开发者，说明本地函数调用方式。
- `docs/api-frontend-integration.md`：面向前端或 HTTP 调用方，说明 FastAPI 服务和 HTTP 请求/响应格式。

## 维护原则

- 优先保持 Python API 的稳定性。
- HTTP API 不重复实现业务逻辑，只做请求路径、响应格式和错误格式适配。
- 新增字段时先更新 schema，再同步更新 Python API 文档和 HTTP API 文档。
- 错误响应保持结构化，便于前端展示和日志排查。
- 路径字段继续支持相对路径和绝对路径，但 HTTP 服务侧应明确相对路径解析规则。

## 后续计划

- 根据前端使用情况补充分页、历史 job 查询或持久化 job store。
- 评估是否需要统一 HTTP 与 CLI 的错误码说明。
- 评估是否需要增加模型列表、模型删除、发布记录查询和模型元数据查询接口。
- 补充生产部署建议，例如端口、日志、模型目录权限和并发限制。
