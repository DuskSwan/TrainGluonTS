# 二进制打包模块设计

本文档描述 TrainGluonTS 后续如何增加一个专门的二进制包装与打包模块。当前文档仅为设计草案，尚未开始实现。

目标是让边端或非 Python 调用方无需直接 import Python 包，而是运行一个二进制程序，传入参数 JSON 和数据 CSV 路径，即可完成训练或推理。

## 设计目标

- 提供一个稳定 CLI 入口，包装现有 `train_model(...)` 和 `predict(...)`。
- 输入参数使用 JSON 文件，时间序列数据使用 CSV 文件路径引用。
- 输出使用 JSON 文件或 stdout，方便外部进程解析。
- 打包为单个可执行文件或一个可分发目录。
- 保留现有 Python API，不影响大仓直接 import 调用。
- 尽量复用现有 schema、异常和测试数据生成逻辑。

## 非目标

- 不提供 HTTP/FastAPI 服务。
- 不重新实现训练或推理逻辑。
- 不把模型文件打进二进制包。模型仍保存在本地 artifact 目录。
- 不承诺跨操作系统通用同一个二进制文件。Windows、Linux、边端架构需要分别构建。

## 建议新增模块结构

```text
TrainGluonTS/
  src/
    traingluonts/
      cli/
        __init__.py
        main.py            # CLI 总入口
        io.py              # JSON 输入输出、错误输出
        commands.py        # train/predict/version 子命令
      packaging/
        __init__.py
        build.py           # 打包脚本入口
        pyinstaller.spec   # PyInstaller 配置，实施时可选
  docs/
    binary_packaging_design.md
  dist/
    traingluonts/
      traingluonts.exe     # Windows 示例产物
```

说明：

- `traingluonts.cli` 负责运行时命令行行为。
- `traingluonts.packaging` 负责构建二进制包，不参与训练和推理业务逻辑。
- `dist/` 是构建产物，应加入 `.gitignore`。

## 二进制程序名称

建议二进制名称：

```text
traingluonts
```

Windows 下产物：

```text
traingluonts.exe
```

## CLI 命令设计

### 查看版本

```powershell
traingluonts version
```

输出：

```json
{
  "ok": true,
  "version": "0.1.0"
}
```

### 训练模型

```powershell
traingluonts train --input train_request.json --output train_result.json
```

参数：

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `--input` | 是 | 训练请求 JSON 文件路径，包含训练参数和 CSV 数据路径 |
| `--output` | 否 | 训练结果 JSON 文件路径；不传则输出到 stdout |
| `--pretty` | 否 | 是否格式化 JSON 输出 |

输入文件示例：

```json
{
  "model_name": "daily_sales_deepar",
  "algorithm": "deepar",
  "freq": "D",
  "prediction_length": 14,
  "artifact_root": "artifacts/models",
  "dataset": {
    "type": "csv",
    "path": "data/train_series.csv",
    "format": "long",
    "item_id_column": "item_id",
    "timestamp_column": "timestamp",
    "target_column": "target"
  },
  "training": {
    "max_epochs": 5,
    "batch_size": 32,
    "num_batches_per_epoch": 50,
    "accelerator": "cpu"
  },
  "evaluation": {
    "enabled": true,
    "test_length": 3
  },
  "hyperparameters": {
    "context_length": 28,
    "num_layers": 2,
    "hidden_size": 40
  }
}
```

CSV 文件示例：

```csv
item_id,timestamp,target
store_001,2024-01-01,12.0
store_001,2024-01-02,15.5
store_001,2024-01-03,14.2
store_002,2024-01-01,9.0
store_002,2024-01-02,10.1
store_002,2024-01-03,11.3
```

成功输出：

```json
{
  "ok": true,
  "result": {
    "model_id": "model_20260605_100000_ab12cd",
    "model_name": "daily_sales_deepar",
    "algorithm": "deepar",
    "status": "completed",
    "model_path": "artifacts/models/model_20260605_100000_ab12cd/predictor",
    "metadata_path": "artifacts/models/model_20260605_100000_ab12cd/metadata.json",
    "metrics": {
      "MASE": 1.23,
      "MAPE": 0.08,
      "RMSE": 5.67,
      "mean_wQuantileLoss": 0.12
    }
  }
}
```

### 执行推理

```powershell
traingluonts predict --input predict_request.json --output predict_result.json
```

参数：

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `--input` | 是 | 推理请求 JSON 文件路径，包含推理参数和 CSV 数据路径 |
| `--output` | 否 | 推理结果 JSON 文件路径；不传则输出到 stdout |
| `--pretty` | 否 | 是否格式化 JSON 输出 |

输入文件示例：

```json
{
  "model_id": "model_20260605_100000_ab12cd",
  "artifact_root": "artifacts/models",
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

推理 CSV 文件示例：

```csv
item_id,timestamp,target
store_001,2024-01-01,12.0
store_001,2024-01-02,15.5
store_001,2024-01-03,14.2
store_001,2024-01-04,18.1
```

成功输出：

```json
{
  "ok": true,
  "result": {
    "model_id": "model_20260605_100000_ab12cd",
    "model_path": "artifacts/models/model_20260605_100000_ab12cd/predictor",
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
}
```

## 错误输出约定

所有命令失败时，stdout 或 `--output` 文件应输出统一 JSON：

```json
{
  "ok": false,
  "error": {
    "type": "TrainingRequestError",
    "message": "validation error detail"
  }
}
```

退出码约定：

| 退出码 | 场景 |
| --- | --- |
| `0` | 成功 |
| `1` | 未分类运行错误 |
| `2` | 输入参数或 JSON 格式错误 |
| `3` | 训练请求错误 |
| `4` | 推理请求错误 |
| `5` | 模型路径或 registry 错误 |

建议将 Python traceback 只写入 stderr，不写入 JSON 结果，避免外部解析失败。

## CSV 数据输入设计

二进制 CLI 第一版建议只接受 CSV 文件路径，不在请求 JSON 中内嵌完整时间序列。原因：

- 长时间序列会让 JSON 文件过大，不利于传输、调试和日志记录。
- CSV 更适合由数据库、业务系统或边端采集程序直接导出。
- JSON 保持为轻量参数文件，CSV 作为数据文件，两者职责清晰。

### DatasetCsvSpec

CLI 请求中的 `dataset` 建议使用以下结构：

```json
{
  "type": "csv",
  "path": "data/train_series.csv",
  "format": "long",
  "item_id_column": "item_id",
  "timestamp_column": "timestamp",
  "target_column": "target"
}
```

字段说明：

| 字段 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `type` | 是 | 无 | 固定为 `"csv"` |
| `path` | 是 | 无 | CSV 文件路径，可以是相对路径或绝对路径 |
| `format` | 否 | `"long"` | 第一版只支持 long format |
| `item_id_column` | 否 | `"item_id"` | 序列 id 列名；如果 CSV 没有该列，则按单序列处理 |
| `timestamp_column` | 是 | 无 | 时间戳列名 |
| `target_column` | 是 | 无 | 目标值列名 |

### CSV long format

第一版推荐并只承诺支持 long format：

```csv
item_id,timestamp,target
store_001,2024-01-01,12.0
store_001,2024-01-02,15.5
store_001,2024-01-03,14.2
store_002,2024-01-01,9.0
store_002,2024-01-02,10.1
store_002,2024-01-03,11.3
```

转换规则：

1. 按 `item_id_column` 分组。
2. 每组按 `timestamp_column` 升序排序。
3. 每组第一条时间作为 GluonTS `start`。
4. 每组 `target_column` 转为 `target` 数组。
5. 频率仍由请求中的 `freq` 字段提供，例如 `"D"`、`"H"`、`"15min"`。

### 第一版约束

- CSV 必须包含 `timestamp_column` 和 `target_column`。
- `target_column` 必须能转换为 float。
- 同一条序列内时间点应按固定频率连续排列。
- 第一版不自动补齐缺失时间点。
- 第一版不处理多目标列。
- 第一版不处理动态特征列。
- 如果 CSV 不包含 `item_id_column`，则整个 CSV 作为一条单序列。

### 后续可扩展方向

- 支持 wide format，例如一列时间、多列序列。
- 支持缺失时间点补齐和插值策略。
- 支持动态实数特征列。
- 支持静态类别特征列。
- 支持 Parquet，用于更大的边端数据文件。

## 打包工具选择

建议第一版使用 PyInstaller。

理由：

- 对 CLI 程序支持成熟。
- 支持 Windows 单文件或目录模式。
- 可以通过 spec 文件处理 GluonTS、PyTorch、Lightning 的隐藏导入。
- 与当前 `src` layout 兼容。

建议优先使用目录模式，而不是单文件模式：

```powershell
pyinstaller --onedir --name traingluonts src/traingluonts/cli/main.py
```

原因：

- PyTorch 和科学计算依赖较大，单文件启动慢。
- 目录模式更容易排查缺失动态库和 hidden import。
- 边端部署时可以整体复制目录。

等目录模式稳定后，再评估是否需要 `--onefile`。

## 构建命令设计

建议提供一个 Python 构建入口：

```powershell
python -m traingluonts.packaging.build --mode onedir
```

参数：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--mode` | `onedir` | `onedir` 或 `onefile` |
| `--name` | `traingluonts` | 二进制文件名 |
| `--clean` | `false` | 构建前清理 build/dist |
| `--output-dir` | `dist` | 构建输出目录 |

## pyproject.toml 计划变更

实施时建议新增可选依赖：

```toml
[project.optional-dependencies]
packaging = [
    "pyinstaller>=6",
]
```

也可以增加脚本入口，便于开发期测试 CLI：

```toml
[project.scripts]
traingluonts = "traingluonts.cli.main:main"
```

注意：脚本入口只影响 Python 包安装后的命令，不等同于二进制产物。

## 打包风险点

### PyTorch 体积

PyTorch 依赖较大，二进制包可能很大。边端部署前需要确认目标设备存储空间。

### 平台兼容

Windows、Linux、ARM 边端通常需要分别在目标平台或兼容平台构建。

### 隐藏导入

GluonTS、Lightning、PyTorch 可能存在动态导入，PyInstaller 可能需要 `hiddenimports`。

### 动态库

PyTorch 依赖动态库。目录模式更容易保留动态库；单文件模式更容易遇到启动慢或解包问题。

### GPU/CPU

第一版建议只承诺 CPU 运行。GPU 依赖和驱动环境不应打进第一版二进制包承诺范围。

## 测试计划

实施时至少增加以下测试：

- [ ] CLI `version` 命令返回 JSON。
- [ ] CLI `train --input ... --output ...` 可以训练并保存模型。
- [ ] CLI `predict --input ... --output ...` 可以加载模型并输出预测。
- [ ] CLI 可以从 CSV 文件读取训练数据。
- [ ] CLI 可以从 CSV 文件读取推理数据。
- [ ] CSV 缺少必填列时返回统一错误 JSON。
- [ ] 输入 JSON 缺少必填字段时返回统一错误 JSON。
- [ ] 不存在模型路径时返回统一错误 JSON。
- [ ] `--output` 不传时结果写入 stdout。
- [ ] `--output` 传入时结果写入文件。

二进制构建验收：

- [ ] `python -m traingluonts.cli.main version` 可运行。
- [ ] `python -m traingluonts.cli.main train ...` 可运行。
- [ ] `python -m traingluonts.cli.main predict ...` 可运行。
- [ ] PyInstaller `onedir` 构建成功。
- [ ] 构建产物中的 `traingluonts version` 可运行。
- [ ] 构建产物中的 `traingluonts train ...` 可运行。
- [ ] 构建产物中的 `traingluonts predict ...` 可运行。

## 实施清单

- [ ] 新建 `src/traingluonts/cli/`。
- [ ] 实现 `main.py`，使用 `argparse` 提供 `version/train/predict` 子命令。
- [ ] 实现 JSON 输入输出工具。
- [ ] 实现 CSV 数据读取工具，将 `DatasetCsvSpec` 转为现有 `DatasetSpec`。
- [ ] 将模块异常映射为统一错误 JSON 和退出码。
- [ ] 新建 `src/traingluonts/packaging/`。
- [ ] 实现 `build.py`，封装 PyInstaller 调用。
- [ ] 按需添加 PyInstaller spec。
- [ ] 更新 `pyproject.toml` optional dependency 和 script entry。
- [ ] 更新 `.gitignore`，忽略 `build/` 和 `dist/`。
- [ ] 新增 CLI 测试。
- [ ] 新增二进制打包验证说明。

## 外部调用方预期流程

训练：

```powershell
traingluonts train --input train_request.json --output train_result.json
```

推理：

```powershell
traingluonts predict --input predict_request.json --output predict_result.json
```

外部调用方只需要关心：

1. 准备 CSV 数据文件。
2. 按接口文档生成 JSON 参数文件，在 `dataset.path` 中指向 CSV。
3. 调用二进制命令。
4. 读取 JSON 输出文件。
5. 根据 `ok` 判断成功或失败。
6. 成功时读取 `result`，失败时读取 `error`。
