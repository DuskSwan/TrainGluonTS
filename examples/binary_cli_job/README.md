# 二进制 CLI 独立测试目录

这个目录用于独立测试打包后的 `traingluonts.exe`。

推荐先在仓库根目录完成打包，然后按下面三步运行。

## 1. 训练

```powershell
.\dist\traingluonts\traingluonts.exe train `
  --input examples\binary_cli_job\train_request.json `
  --output examples\binary_cli_job\results\train_result.json `
  --pretty
```

训练完成后，模型会写入：

```text
examples/binary_cli_job/models/{model_id}/
```

## 2. 准备推理模型路径

训练生成的 `model_id` 是随机的。为了让 `predict_request.json` 保持固定，本目录提供了一个脚本，把刚训练出的模型复制到 `models/latest`：

```powershell
powershell -ExecutionPolicy Bypass -File examples\binary_cli_job\prepare_latest_model.ps1
```

该脚本只会覆盖本目录下的：

```text
examples/binary_cli_job/models/latest/
```

## 3. 推理

```powershell
.\dist\traingluonts\traingluonts.exe predict `
  --input examples\binary_cli_job\predict_request.json `
  --output examples\binary_cli_job\results\predict_result.json `
  --pretty
```

成功后查看：

```text
examples/binary_cli_job/results/train_result.json
examples/binary_cli_job/results/predict_result.json
```

