# Amazon Alexa 问答构建器

## 一眼看懂

- 这是什么：整理亚马逊商品的 Alexa 双语问答，附评论证据。
- 什么时候用：准备商品页问答，或核对每条答案有没有评论支持时。
- 给它什么：候选问题、Listing 信息和评论证据。
- 它给你什么：每个商品两份表格，原始记录和清洗问答。

## 项目简介

`amazon-alexa-qa-builder` 是面向 Amazon US 商品的 Alexa/Rufus 问答整理工具，也可作为 Codex Skill 使用。它接收当前商品的候选问题与评论证据，保留原始来源映射，再清洗成有证据边界的双语问答；每个 ASIN 分别导出 Raw、Clean 两个 Excel。

仓库提供评论采集适配器、数据组装、清洗、校验及出表脚本。Listing、联想词、卖家精灵数据的取得和候选问题生成由 [SKILL.md](SKILL.md) 约定的上游流程完成，仓库没有独立的一键全流程入口，也不自带上游评论仓库代码。

## 核心功能

- 🗂️ **原始映射**：保留问题、查询词与评论 ID
- 🎯 **定向采集**：目标商品优先，竞品补证
- 🧹 **语义合并**：按语义键合并同义问题
- 🔍 **证据校验**：竞品评论不算目标商品证据
- 📦 **批量出表**：每个商品导出两份表格
- 🧪 **离线自检**：合成数据校验与结构检查

## 技术栈

| 层级 | 技术 | 版本 |
| --- | --- | --- |
| 语言 | Python | >=3.10,<3.14 |
| 浏览器自动化 | Playwright（Python 依赖） | >=1.55,<2 |
| Excel 出表 | Node.js + `@oai/artifact-tool` | — |
| 打包 | setuptools | — |
| 测试 | Python unittest / PowerShell 脚本 / GitHub Actions | — |

版本取自 `pyproject.toml`、`requirements.txt` 与 `.python-version`（本地锁定 `3.12.13`）。Node.js 与 `@oai/artifact-tool` 由 Codex 工作区提供，仓库未锁定版本，故记「—」。

## 快速开始

需要 Python 3.10–3.13；出表另需带 `@oai/artifact-tool` 的 Node.js 环境，在线采集还需上游评论仓库及其依赖。

1. 克隆仓库并进入目录

   ```bash
   git clone https://github.com/fubo-ops/amazon-alexa-qa-builder.git
   cd amazon-alexa-qa-builder
   ```

2. 创建虚拟环境并安装依赖，再装 Playwright 浏览器

   ```bash
   python -m venv .venv
   python -m pip install -r requirements.txt
   python -m playwright install chromium
   ```

3. 作为 Codex Skill 使用时，把仓库放进 Skills 目录

   ```bash
   cp -r . ~/.codex/skills/amazon-alexa-qa-builder
   ```

4. 用合成数据跑离线校验，不需要在线采集

   ```bash
   python -B -m unittest discover -s tests -v
   python -B scripts/validate_payload.py tests/fixtures/valid_payload.json
   ```

5. 用两份合成输入验证批量出表，生成四个工作簿到 `outputs/`

   ```bash
   python scripts/export_batch.py tests/fixtures/clean_35_questions.json tests/fixtures/valid_payload_2.json --output-dir outputs/sample --max-clean-questions unlimited --node node --node-modules "<CODEX_NODE_MODULES>"
   ```

6. 查看采集、组装、导出三个入口的参数说明

   ```bash
   python scripts/collect_targeted_reviews.py --help
   python scripts/assemble_raw_payload.py --help
   python scripts/export_batch.py --help
   ```

第 5 步要把 `<CODEX_NODE_MODULES>` 换成当前环境里含 `@oai/artifact-tool` 的绝对目录；设置 `ALEXA_QA_BATCH_OUTPUT` 指向输出目录后重跑 unittest 才会检查工作簿结构。真实任务按 [来源流程](references/source-flows.md) 与 [数据契约](references/data-contract.md) 组织输入，评论适配器的 `--review-repo` 必须指向上游评论仓库。

## 项目结构

只列两层，完整文件清单见文末《详细说明》。

```text
amazon-alexa-qa-builder/
├── .github/                                # CI 工作流目录
├── .gitignore                              # 忽略运行目录与生成文件
├── .python-version                         # 本地 Python 版本锁定
├── README.md                               # 项目总览与快速开始
├── SKILL.md                                # Skill 入口与完整作业流程
├── agents/                                 # Agent 配置
├── pyproject.toml                          # Python 包元数据与依赖
├── references/                             # 数据契约与来源流程文档
├── requirements.txt                        # Python 运行依赖
├── scripts/                                # 采集、组装、清洗与出表脚本
│   ├── assemble_raw_payload.py             # 组装 Raw payload
│   ├── build_clean_workbook.mjs            # 生成 Clean Excel
│   ├── build_workbook.mjs                  # 生成 Raw Excel
│   ├── clean_payload.py                    # 语义合并与清洗
│   ├── collect_targeted_reviews.py         # 定向评论采集适配器
│   ├── export_batch.py                     # 批量导出入口
│   ├── validate_clean_payload.py           # Clean 数据校验
│   └── validate_payload.py                 # Raw 数据校验
└── tests/                                  # 离线测试与合成数据
    ├── fixtures/                           # 合成候选、payload 与评论证据
    ├── run_offline_tests.ps1               # Windows 完整出表测试脚本
    └── test_offline.py                     # 离线单元测试
```

## 架构图

```text
┌──────────────────────────────────────────────────┐
│   上游：Listing 事实、联想词、卖家精灵、评论     │
└────────────────────────┬─────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────┐
│   SKILL.md 约定的候选问题生成与商品隔离          │
└────────────────────────┬─────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────┐
│   collect_targeted_reviews.py 定向评论采集       │
└────────────────────────┬─────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────┐
│   assemble_raw_payload.py → Raw payload          │
└────────────────────────┬─────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────┐
│   validate_payload.py → build_workbook.mjs       │
└────────────────────────┬─────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────┐
│   clean_payload.py → validate_clean_payload.py   │
└────────────────────────┬─────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────┐
│   build_clean_workbook.mjs → 每 ASIN 两份 Excel  │
└──────────────────────────────────────────────────┘
```

Raw 保留全部来源映射，Clean 只做语义合并；答案只用目标 Listing 事实或目标 ASIN 评论，缺证据时写固定的中英文未验证答案。运行输入、浏览器资料、断点和输出文件都不进 Git。

## 开发计划

### Phase 1: 采集与组装

- ✅ 定向评论适配器（目标优先、竞品补证）
- ✅ 低并发与断点续跑
- ✅ Raw payload 组装与来源映射保留

### Phase 2: 清洗与校验

- ✅ `semantic_key` 语义合并与相关性过滤
- ✅ 答案证据边界与双语未验证回退
- ✅ Raw / Clean 双校验脚本

### Phase 3: 出表与批量

- ✅ 单 ASIN 的 Raw、Clean 工作簿
- ✅ 冻结首行、筛选与自动换行
- ✅ 批量导出每 ASIN 两个单表工作簿

### Phase 4: 工程化与上线

- ✅ 离线 unittest 与合成数据
- ✅ GitHub Actions 三平台与 Python 3.10/3.13 矩阵
- ⬜ CI 内准备 Node.js 出表依赖并跑通导出检查
- ⬜ 上游评论仓库兼容性与真实业务验收记录
- ⬜ 独立开发路线图与版本锁定

## 文档

- [Skill 入口与完整工作流程](SKILL.md)
- [候选、Raw、Clean 字段与答案证据契约](references/data-contract.md)
- [当前任务来源、上游适配与商品隔离](references/source-flows.md)
- [离线测试入口](tests/test_offline.py)
- [Windows 完整出表测试脚本](tests/run_offline_tests.ps1)
- [CI 配置](.github/workflows/test.yml)

## 许可证

待补充。仓库当前未提供 `LICENSE` 文件，使用和分发授权范围需由维护者确认。

---

原 README 里的环境要求、安装配置、完整命令、数据边界、项目文件清单、开发状态与历史记录等细节，已全部迁移到 [docs/详细说明.md](docs/详细说明.md)。
