# paper2slides — 论文 → 学术汇报 PPT（带页级证据映射）

把一篇论文 PDF 变成**可讲、可核验、可编辑**的学术 PPT：`slides.pptx`（可编辑源文件）、
`slides.pdf` + 逐页 PNG（真实渲染证明）、`evidence_map.json`（每页内容 → 论文图/表/章节的映射）、
`deck_plan.json`（可审计的页级计划）。

**方法一句话**：脚本抽论文结构 → Agent 写页级计划（一页一主张、每主张挂证据）→
脚本按模板占位符确定性渲染 → 机器自检（密度/编号/备注/图片）→ 输出证据映射。
质量集中在计划上，版面稳定性由脚本保证。

## 目录结构

```
paper2slides/
├── SKILL.md                  # Skill 本体：五阶段流程 + 规则 + 异常处置 + 输出契约
├── scripts/
│   ├── pdf_extract.py        # PDF → 结构/章节/图表清单 (PyMuPDF)
│   ├── inspect_template.py   # 模板 PPTX → 版式与占位符报告
│   ├── build_deck.py         # deck_plan.json → slides.pptx（占位符渲染）
│   ├── check_deck.py         # 计划×成稿×论文 三方一致性自检
│   └── render_preview.py     # PPTX → PDF → PNG（LibreOffice/PyMuPDF 回退链）
├── references/
│   ├── deck-plan.md          # deck_plan.json 完整 schema + 示例
│   └── slide-patterns.md     # 学术汇报页型模式库（P1–P9 + 备份页）
└── examples/
    └── deck_plan.example.json # 最小调用示例（标注为示例，非正式案例结果）
```

## 环境依赖

| 依赖 | 用途 | 安装 |
|---|---|---|
| Python ≥ 3.9 | 全部脚本 | — |
| python-pptx ≥ 0.6.21 | 模板扫描/渲染/自检 | `pip install python-pptx` |
| PyMuPDF ≥ 1.24 | PDF 解析、图片提取、PDF→PNG | `pip install pymupdf` |
| Pillow | 图片等比缩放（可选，缺失时按 4:3） | `pip install pillow` |
| LibreOffice (soffice) | PPTX→PDF 渲染 | 系统安装；无则交付计划+pptx 并如实记录 |

平台内置 `pdf-text-tool` / `pdf-render-tool` / `office-renderer` / `latex-compiler` 时，
SKILL.md 的回退链会优先使用平台工具。

## 快速开始（一篇论文，约 10 分钟）

```bash
# 1. 抽论文结构（页/章节/图表清单）
python3 scripts/pdf_extract.py paper.pdf -o work/paper_structure.json

# 2.（可选）扫模板占位符；无模板则跳过，用内置 16:9
python3 scripts/inspect_template.py template.pptx -o work/template_report.json

# 3. 参照 references/ 写 work/deck_plan.json（质量步骤：一页一主张+证据+备注）

# 4. 渲染成稿 + 证据映射
python3 scripts/build_deck.py work/deck_plan.json -o output/slides.pptx \
       --evidence-out output/evidence_map.json

# 5. 机器自检 + 渲染预览
python3 scripts/check_deck.py work/deck_plan.json output/slides.pptx \
       --paper work/paper_structure.json -o work/check_report.json
python3 scripts/render_preview.py output/slides.pptx --outdir output/previews

# 6. 按 check_report.json 修 deck_plan.json，重跑 4–5；肉眼抽查 3 张 PNG
```

## 输入 / 输出

**输入**：论文 PDF；可选模板 .pptx；任务约束（受众、时长、页数上限）。
**输出**：`output/slides.pptx`、`output/previews/`（slides.pdf + pages/*.png）、
`output/evidence_map.json`、`work/deck_plan.json`、`result.json`（运行摘要，
schema 见 SKILL.md Phase 5）。

## 异常处理（详见 SKILL.md 失败手册）

扫描版 PDF → 走 OCR 并在 `uncertainty` 记录；图片提取失败（矢量图）→ 按页渲染区域替代并记录；
模板缺占位符 → 回退内联排版并降级 `template_compliance`；无 LibreOffice → 交付计划+pptx，
`render.engine="none"` 如实标注。**部分完成必须显式声明**（`status: "partial"`），禁止编造。

## 适用范围与限制

- 适用：单篇/少量论文 → 学术汇报、组会报告、会议 talk；中英文均可。
- 不负责：文献综述写作、科研绘图美化、论文语言润色（相邻课题）。
- 已知限制：双栏排版的图片-文段对应依赖 caption 页内位置启发式；公式建议按图截取
  而非重打；模板合规度取决于模板本身的占位符完备性。

## 自查方法

1. `check_report.json.ok == true`（零问题）
2. 预览 PNG 打开正常，抽查 3 页
3. 逐页读 `evidence.quote` 与页面主张是否真的对得上
4. 每个内容页有 notes，且不是正文复制
5. `result.json` 的 status / uncertainty 如实

## 维护

问题反馈与改进建议见仓库 Issues。版本：v1.0（2026-11）。
