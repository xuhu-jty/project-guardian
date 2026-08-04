# Project Guardian（项目开发守护）

Project Guardian 是一个面向 Codex 的本地开发管理插件。它把需求、Codex 任务、Git 分支与工作树、模块、文件、函数、参数、测试证据和合并状态组织成一张持续更新的项目图，帮助非专业开发者在项目变复杂之后仍然知道：

- 当前有哪些功能正在开发；
- 每个分支和工作树在做什么；
- 某个功能涉及哪些模块、文件、函数和参数；
- AI 当前处于规划、执行还是独立复审阶段；
- 功能是否真的完成，为什么仍不能合并；
- AI 是否越界修改、削弱测试或偏离原始需求。

Guardian 不会自动合并代码。只有所有门槛通过后，它才会请用户确认是否合并。

## 主要能力

- 项目接入与真实基线识别；
- 分支、工作树和 Codex 任务绑定；
- 模块、文件、符号、函数签名和参数索引；
- 原始需求、验收条件、非目标和受保护行为持久化；
- 自动判断新功能、问题诊断、维护、重构和架构任务；
- 自动创建风险等级并选择合适的模型路线；
- 修改范围锁定、跨任务冲突和架构漂移检测；
- 基线、目标、相关、全量、集成、独立复审和架构证据门槛；
- 连续无效修复自动升级为架构审查；
- 小白友好的项目图和唯一下一步提示。

## 自动模型调度

用户只需要描述需求，不需要选择模型或风险等级。

| 风险 | 规划 | 执行 | 独立复审 | 典型任务 |
| --- | --- | --- | --- | --- |
| 低风险 | GPT-5.6 Terra · Medium | GPT-5.6 Luna · High | GPT-5.6 Terra · Medium | README、文档和局部低影响维护 |
| 标准风险 | GPT-5.6 Terra · High | GPT-5.6 Luna · Xhigh | GPT-5.6 Terra · High | 普通功能、Bug 和边界明确的重构 |
| 高风险（执行明确） | GPT-5.6 Sol · Xhigh | GPT-5.6 Luna · Xhigh | GPT-5.6 Sol · Xhigh | 核心算法、商业关键逻辑 |
| 高风险（需要判断） | GPT-5.6 Sol · Xhigh | GPT-5.6 Terra · Xhigh | GPT-5.6 Sol · Xhigh | 新项目架构、跨模块协议、迁移和连续失败 |
| 重大 Bug | — | 独立 GPT-5.6 Sol · Xhigh 修复 | 另一个 GPT-5.6 Sol · Xhigh 最终复审 | 安全、数据、架构或严重回归问题 |

如果指定模型不可用，Guardian 会停在当前阶段并说明原因，不会偷偷换成较弱模型。

## 环境要求

- Codex Desktop 或带插件命令的 Codex CLI；
- Git；
- Python 3.10 或更高版本；
- 需要管理的项目本身必须是 Git 仓库。

## 安装

### 方式一：安装到个人 marketplace（推荐）

1. 克隆到固定的个人插件目录。

Windows PowerShell：

```powershell
git clone https://github.com/xuhu-jty/project-guardian.git "$env:USERPROFILE\plugins\project-guardian"
```

macOS / Linux：

```bash
git clone https://github.com/xuhu-jty/project-guardian.git "$HOME/plugins/project-guardian"
```

2. 打开个人 marketplace 文件：

- Windows：`%USERPROFILE%\.agents\plugins\marketplace.json`
- macOS / Linux：`~/.agents/plugins/marketplace.json`

如果文件不存在，创建以下内容：

```json
{
  "name": "personal",
  "interface": {
    "displayName": "Personal"
  },
  "plugins": [
    {
      "name": "project-guardian",
      "source": {
        "source": "local",
        "path": "./plugins/project-guardian"
      },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Productivity"
    }
  ]
}
```

如果文件已经存在，只把上面 `plugins` 数组中的 `project-guardian` 对象加入现有 `plugins` 数组；不要覆盖其他插件。

3. 安装插件：

```bash
codex plugin add project-guardian@personal
```

4. 检查安装结果：

```bash
codex plugin list
```

应当看到 `project-guardian@personal` 的状态为 `installed, enabled`。

5. 新建一个 Codex 任务以加载新 SKILL 和 MCP 工具。通常不需要重启 Codex；如果新任务仍看不到插件，再重启一次。

### 升级

Windows PowerShell：

```powershell
git -C "$env:USERPROFILE\plugins\project-guardian" pull
codex plugin add project-guardian@personal
```

macOS / Linux：

```bash
git -C "$HOME/plugins/project-guardian" pull
codex plugin add project-guardian@personal
```

升级后请新建 Codex 任务，旧任务不会热更新已加载的工具定义。

### 卸载

```bash
codex plugin remove project-guardian@personal
```

卸载插件不会自动删除 Guardian 已保存的本地项目状态。如需清理数据，请先确认不再需要历史项目图和工作项记录。

## 第一次使用

1. 在 Codex 中打开需要管理的 Git 项目目录。
2. 新建一个 Codex 任务。
3. 输入：

```text
使用项目开发守护接入这个项目，然后打开项目图。
```

Guardian 会自动：

1. 检查 MCP 和本地状态；
2. 扫描分支、工作树和真实代码基线；
3. 建立模块、文件、函数和参数地图；
4. 检查已登记的测试命令；
5. 在回复下方显示当前状态和唯一下一步。

项目图不是左侧永久页面。以后在同一项目的任意 Codex 任务里输入：

```text
打开项目图
```

即可重新显示。

## 日常使用

### 提出新功能

直接描述结果，不需要先决定分支、工作树或模型：

```text
新增牌局回放筛选功能，可以按玩家和日期筛选，但不要改变现有回放格式。
```

Guardian 会自动判断是否复用已有任务、创建新工作项、评估风险、规划范围并选择模型路线。

### 提交“为什么”问题

```text
为什么已经听牌还会选择碰牌？
```

这类问题首先建立只读诊断项。Guardian 在复现并确认原因之前不会授权修改代码；确认需要修复后，才会建立变更任务。

### 查看进度

可以输入：

```text
项目进度
```

或：

```text
我下一步做什么？
```

### 查看分支与工作树

```text
怎么看各分支和工作树在做什么？
```

Guardian 会显示分支的代码区域、最新提交、是否有未提交修改、所属工作项和 Codex 任务。

### 查看功能对应的代码

```text
显示“出牌决策”模块涉及的文件、函数、参数、依赖和测试。
```

Guardian 会按需读取相关模块，避免把整个项目塞进一个过长的会话。

### 查看模型是否真的被调用

输入：

```text
打开项目图，显示当前任务的风险判断、规划/执行/复审模型和已经记录的模型运行。
```

项目图会区分“计划使用的路线”和“已经完成并持久化的运行阶段”。创建任务不等于完成；只有 `record_task_stage` 记录的真实结果才算完成。

## 合并规则

Guardian 只有在以下条件都满足后才会请求合并确认：

- 原始需求和验收条件完整；
- 变更位于绑定的 Codex 工作树；
- 所有修改都落在声明范围内；
- 没有未处理的跨任务范围冲突；
- 当前风险路线的规划、执行和独立复审均已完成；
- 测试和证据属于当前工作树指纹；
- 架构审查、测试完整性和集成门槛按需通过；
- 独立复审晚于最后一次代码修改。

插件不会运行自动合并。用户明确确认后，才允许执行实际 Git 合并并记录真实合并提交。

## 决策、训练和统计系统

对于麻将决策、推荐、排序和训练系统，仅仅“测试通过”不代表效果提升。Guardian 要求补充：

- 固定基线对比；
- 固定随机种子或可重放样本；
- 未参与调参的保留集；
- 预先声明的产品指标；
- 预期变化和无法解释变化的分离记录。

同一问题连续三次没有改善真实产品结果时，即使单元测试全部通过，也会被记录为失败并升级到 Sol Xhigh 架构重规划。

## 本地数据

Guardian 的持久状态保存在本机，不写入被管理项目的代码目录：

- Windows：`%LOCALAPPDATA%\ProjectGuardian`
- macOS / Linux：`~/.local/share/project-guardian`

可以通过环境变量 `PROJECT_GUARDIAN_DATA` 或 `PLUGIN_DATA` 指定其他数据目录。

## 常见问题

### 为什么项目接入后不能立即开发？

Guardian 可能还没有确认真实代码基线，或者登记的测试命令引用了不存在的文件。先完成项目图给出的唯一下一步，避免在错误分支上继续开发。

### 为什么全新空项目可以接入，旧项目的空 `main` 却被阻塞？

只有所有可见分支都指向同一个初始提交时，Guardian 才把空默认分支视为全新项目基线。如果其他分支已经包含不同代码，它会要求判断哪条代码线才是真实项目，防止选错基线。

### 为什么不直接让 Sol Xhigh 处理所有任务？

普通任务使用 Terra 和 Luna 更节省资源；架构、核心算法、商业关键、安全、数据和连续失败任务才升级 Sol Xhigh。重大 Bug 始终由独立 Sol 修复并由另一个 Sol 复审。

### 为什么当前 Codex 任务仍显示旧版本？

Codex 任务会在创建时加载插件工具定义。升级后新建任务；仍未更新时再重启 Codex。

## 开发与验证

在插件仓库根目录运行：

```bash
python -m unittest discover -s tests -v
```

当前版本包含项目接入、代码图、工作树绑定、风险路由、模型阶段、漂移阻断、证据门槛、UTF-8 MCP 通信和状态迁移测试。

## 项目结构

```text
.codex-plugin/plugin.json                 插件清单
.mcp.json                                 MCP 服务器配置
hooks/                                    会话和写入保护钩子
scripts/project_guardian_core.py          项目状态与开发门槛核心
scripts/project_guardian_inventory.py     Git、模块、文件和符号扫描
scripts/project_guardian_mcp.py           MCP 工具入口
skills/manage-project-development/        Codex 开发管理 SKILL 与策略
tests/                                    自动化测试
```

## 许可证

[MIT License](LICENSE)
