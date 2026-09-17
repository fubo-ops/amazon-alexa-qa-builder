# Amazon Alexa Q&A Builder

一个可作为 Codex Skill 使用的 Amazon Alexa/Rufus Q&A 构建器。它为每个 ASIN 保留完整原始来源映射，再生成证据边界明确的清洗结果；Raw 与 Clean 默认都不设置问题数量上限。

## 输出文件

每个 ASIN 独立生成两个 Excel，输入 N 个 ASIN 时输出 2N 个文件：

```text
{ASIN}_QA_Raw.xlsx    # Q&A Raw Data：保留问题×关键词×查询词×评论ID映射
{ASIN}_QA_Clean.xlsx  # Alexa Q&A：清除污染并只合并真正同义的问题
```

两个 Excel 均只有一个工作表，冻结首行、启用筛选并自动换行。

## 支持环境

- Windows、macOS、Linux
- Python 3.10–3.13
- Node.js，以及 Codex 工作区提供的 `@oai/artifact-tool`
- Playwright Chromium 或本机 Google Chrome

仓库通过 GitHub Actions 在三个操作系统及 Python 最低、最高支持版本上运行离线回归测试。

## 安装

```bash
git clone https://github.com/fubo-ops/amazon-alexa-qa-builder.git
cd amazon-alexa-qa-builder
python -m venv .venv
```

Windows PowerShell：

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
```

macOS / Linux：

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium
```

作为 Codex Skill 使用时，将仓库放到：

```text
~/.codex/skills/amazon-alexa-qa-builder
```

## 数据流程

1. 从目标 Listing、Amazon 联想词和卖家精灵实际数据生成不限量候选。
2. 通过 Rufus `askSearch` 对目标 ASIN、再对竞品 ASIN 定向检索评论证据。
3. Raw 阶段保留重复问题、重复来源和全部多对多映射。
4. Clean 阶段清除错品/品牌污染，仅合并真正同义的问题，不使用固定模板或 Top-N。
5. 答案只使用目标 Listing 事实或目标 ASIN 评论；竞品评论只能证明买家关注。

具体字段、证据边界和上游适配规则见 `SKILL.md` 与 `references/`。

## 批量导出

已取得各 ASIN 的 Raw payload 后：

```powershell
amazon-alexa-qa <ASIN1_RAW.json> <ASIN2_RAW.json> `
  --output-dir outputs --max-clean-questions unlimited `
  --node node --node-modules <CODEX_NODE_MODULES>
```

也可以直接调用：

```powershell
python scripts\export_batch.py <ASIN1_RAW.json> --output-dir outputs `
  --node node --node-modules <CODEX_NODE_MODULES>
```

## 验证

Windows PowerShell：

```powershell
.\tests\run_offline_tests.ps1 -Python python
```

跨平台基础测试：

```bash
python -m unittest discover -s tests -v
```

离线套件验证 unlimited 行为、Raw 来源保留、Clean 语义合并边界、答案证据边界，以及多 ASIN 的 2N 个单工作表 Excel 输出。

## 技术脱敏

- 不读取、导出或打印 Cookie、Token、密码及浏览器凭据。
- 不将竞品事实或竞品评论作为目标商品功能证明。
- 卖家精灵指标只填写实际取得的数据，未取得时明确标记。
- `.gitignore` 排除虚拟环境、输出 Excel、临时文件与缓存。
- 上游 Listing 与评论项目保持不变，仅通过适配器调用。
