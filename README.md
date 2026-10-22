# lumerical-matlab-paper-reproduction

面向科研智能体的 Lumerical × MATLAB 论文复现 Skill。用户提交 PDF 并说“复现这篇论文”，智能体按 SKILL.md 自主完成全图登记、模型审计、求解、绘图与验证。Python 工具负责可重复的机械步骤；论文理解、复杂子图校正和物理模型重建由调用 Skill 的智能体完成。

**实际边界：这不是“任意论文 PDF 一键保证正确复现”的通用求解器。** 提取/分类结果默认待审；未知物理模型必须从原文构建。开发环境没有 Lumerical/MATLAB，商业接口与 MATLAB 绘图仅完成代码和契约测试，未实际运行。示例中的真实数值数据标为 PYTHON_REFERENCE；Xiang 当前候选仍收敛到固定点，不能作为自脉冲复现成功交付。

## 安装

需要 Python 3.10+。仓库不含商业软件或许可证。Windows PowerShell、macOS、Linux 均可使用：

```sh
git clone <YOUR-GITHUB-REPOSITORY-URL> lumerical-matlab-paper-reproduction
cd lumerical-matlab-paper-reproduction
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
python -m paper_repro doctor --out ./work
python -m pytest -q
```

Skill 安装：把**整个仓库目录**放入智能体的 skills 目录，如 `~/.codex/skills/lumerical-matlab-paper-reproduction`。保留根目录 SKILL.md、paper_repro、references、templates 和 examples。本 Skill 不依赖平台私有 API；支持 Agent Skills 的智能体可按其安装方式加载此目录。只有已保存到当前应用的 Skill 才会出现在当前应用技能列表，单纯 pip 安装只安装工具包。

设置商业软件路径后探测接口：

```sh
# Linux/macOS 示例；Windows 使用 $env:LUMAPI_PATH / $env:MATLAB_EXECUTABLE
export LUMAPI_PATH=/opt/lumerical/vXXX/api/python/lumapi.py
export MATLAB_EXECUTABLE=/usr/local/MATLAB/RXXXX/bin/matlab
python -m paper_repro doctor --out ./work --probe-lumerical --product INTERCONNECT
```

使用安装版本自带/官方支持的 SDK 和 Python；“路径存在”不等于“许可证可用”。probe 只证明所测产品的脚本接口可调用，不证明物理仿真正确。

## 最简使用

对智能体说：**“使用 lumerical-matlab-paper-reproduction 复现这篇论文。”** 上传 PDF。智能体读取 SKILL.md 并完成后续工作，不应把下面的开发命令逐条转交用户。

命令行入口：

```sh
python -m paper_repro prepare /path/to/paper.pdf --out ./work/paper-project
```

输出完整页面、原生图片/矢量、公式/表格候选、待审子图、Figure Manifest、环境探测、REPORT.md、AGENT_TASKS.md。智能体检查**每一页**，校正图框、分类、坐标/单位和公式，构建共享模型并填写模型关联。此时没有仿真数据，报告保持 D。`prepare` 不会伪称已经“理解并求解整篇论文”。

## 可运行的最小例子

```sh
python scripts/run_case.py minimal --out ./work/minimal --backend python-reference
```

它真实积分线性腔解析测试模型、保存 MAT/运行收据并核对解析解。数据明确属于合成测试，绝非论文数据。默认后端为 Lumerical；只有显式指定 python-reference 才使用 SciPy。

论文案例：

```sh
python scripts/run_case.py xiang --out ./work/xiang --backend lumerical --budget 600
python scripts/run_case.py biasi --out ./work/biasi --backend lumerical --budget 600
```

没有软件会保存代码与 BLOCKED 原因，不会捏造输出。Xiang 包含字面模型、显式物理符号候选、失败诊断、近似数字化参考和受约束辨识配置；Biasi 使用独立的非厄米双模模型和实际状态继承扫描。详见 references 下两个案例说明。旧 Xiang 成功候选的精确参数/日志未提供，仓库不会伪造这段历史。

## 工具与边界

| 能力 | 已实现 | 仍需智能体或真实环境 |
|---|---|---|
| 全文/图片/矢量/公式锚点/表格提取 | PyMuPDF，页码/坐标/哈希，OCR 可选 | 扫描数学、复杂排版、无标签图完整性审阅 |
| 子图/分类/优先级/Manifest | 启发式、逐子图分类、人工语义覆盖接口 | 视觉校正、科学价值判断，不自动宣称全覆盖 |
| 物理模型与参数审计 | 安全表达式 IR、Pint 单位、来源分级、同器件一致性 | 从论文重建具体模型、审查假设/守恒 |
| Lumerical | LSF RK4/指数中点代码生成、feval、产品脚本契约、运行收据 | 商业运行未验证；空间求解器需具体结构/边界脚本 |
| MATLAB | 真实 MAT 输入、曲线/热图、PNG/PDF/SVG/FIG、输出检查 | 未实测 MATLAB 执行或渲染 |
| 参考提取/误差 | 色掩膜/标定/对数轴/空缺/像素误差；曲线/热图/本征值指标 | 重叠曲线、误差棒、分岔支路、参考真实性 |
| 调度 | SQLite DAG、缓存哈希、过期租约恢复、预算、并行独立任务 | 前台执行；不承诺脱离会话后持续后台运行 |
| 辨识 | 有界 D 参数、真实试算、保留基线/候选/失败 | 多图目标/不确定性及独立验证需按论文设计 |
| 评级 | 真实数据/模型/收据/收敛/物理检查门槛 | PDE 专用收敛/评级需要按论文补充 |

全部 CLI 参数：`python -m paper_repro --help`。scripts 中提供与常见任务名称对应的便捷入口。各子命令 `--help` 给出实际参数。

```sh
python -m paper_repro audit models/ring.json --out audit.json
python -m paper_repro compile models/ring.json --script simulation.lsf --data data.mat
python -m paper_repro run-model models/ring.json --out data.mat
python -m paper_repro digitize figure.png calibration.json --out reference.csv
python -m paper_repro compare reference.csv data.mat --column out_output_power --out metrics.json
python -m paper_repro schedule PROJECT --budget 600 --workers 1
python -m paper_repro report PROJECT
```

`identify` 只调整明确的 D 类参数且不覆盖原始模型；`sweep` 为每个点真正积分并保存末态。缺少数据、软件或物理依据时退出码20（BLOCKED）；输入错误为2，普通运行错误非0。修改依赖/恢复已有项目时使用相同目录，避免无意义重新提取。

## 测试、证据与发布

运行 `python -m pytest -q`，测试包括真正构造的多子图 PDF、原生图片和矢量提取、分类/量纲/恶意表达式拦截、解析 ODE 对照、数据哈希、缓存失效、断点恢复、正反扫描状态、ND 数组契约、绘图进程契约以及独立积分器收敛。绘图契约测试明确 mock MATLAB 进程；不是 MATLAB 实际仿真证据。

`examples/*/*run*` 中已有的开发数据只保留真实执行记录，来源和后端写在 receipt 中。`DEVELOPMENT_VALIDATION.md` 记录本次环境、实测结果和未验证部分。GitHub Actions 按 Python 3.10/3.12 执行纯开源测试，不需要商业许可证。独立工程可以直接建立 GitHub 仓库并推送；不要把用户论文、许可证、个人路径/秘密或大规模运行输出推到公共仓库。

MIT 许可证仅覆盖本项目原创代码/文档。被引用论文/原图属于各自权利人；仓库不附商业软件或完整论文。科学数据和近似提取结果的来源必须保留。物理真实性优先于数字吻合，数字吻合优先于排版相似。
