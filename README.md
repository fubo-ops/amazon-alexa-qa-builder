# Amazon Alexa Q&A Builder

Codex Skill：为一个或多个 Amazon ASIN 生成两阶段 Q&A Excel。

- `{ASIN}_QA_Raw.xlsx`：保留问题、关键词、查询词与评论证据的完整来源映射。
- `{ASIN}_QA_Clean.xlsx`：清除污染并合并真正同义的问题；默认不限制最终问题数量。
- 多 ASIN 输入时，每个 ASIN 独立生成以上两个文件，避免数据互相污染。

## 安装

将本仓库复制或克隆到：

```text
~/.codex/skills/amazon-alexa-qa-builder
```

该 Skill 通过适配器复用本地 Amazon Listing 优化和 Rufus 评论采集项目，不复制或修改上游仓库，也不读取或保存 Cookie、Token、密码与浏览器凭据。具体字段、证据边界和运行流程见 `SKILL.md` 与 `references/`。

## 离线验证

```powershell
.\tests\run_offline_tests.ps1 -Python python
```

离线套件验证 unlimited 行为、Raw 来源保留、Clean 语义合并边界、答案证据边界，以及多 ASIN 的 `2N` 个单工作表 Excel 输出。
