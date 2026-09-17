# 下一阶段只读评估：memory/context 命名参数的二次解析

**建议最小下一节点：仅修复 `cmd_memory`、`cmd_context` 的参数值读取；search 留作独立语法待办。** 检查版本 `17e9a435`，实跑 `build/takeover/qbrain`（SHA256 `030b4b0a86431e301f3e83d0184c19d5a5ee4f0f6a11ccf024a1da2c399cfe3c`）。这些函数及全局 `opt`／brain resolver 与 `d033bdb2` 基线逐段字节相同，**不是 N47L 引入，不改变 N47L 已有审核结论**。

隔离 Linux fixture：脑库 `intended`；合法来源 `alpha`、`--limit` 的原话均含 `--source`，分别标识 `ALPHASOURCE`／`SHADOWSOURCE`；合法来源 `--brain` 有页面 `docs/first`。memory/context 每条都有只调整真实选项顺序的成功对照。下表省略可执行前缀 `qbrain`。

| 已实际执行的输入 | 实际结果与定位 |
|---|---|
| `memory read --brain intended --query --source --limit 5 --source alpha` | exit 0，却返回来源 **`--limit` 的 SHADOWSOURCE**；将真实 `--source alpha` 提前即返回 ALPHASOURCE。`commands.cpp:393` 重扫查询值。 |
| `memory read --query --brain --source alpha --brain intended` | exit 1／`source_not_found`，先误建 **`brains/--source`**；真实 `--brain intended` 提前则正常。`commands.cpp:390` 将未解析 argv 交给 resolver。 |
| `context read --source --brain --uri qbrain://--brain/resources/docs/first --layer L2 --brain intended` | exit 1／`source_not_found`，先误建 **`brains/--uri`**；真实 brain 选项提前即可读同一页。`commands.cpp:506` 同类问题。 |
| `search "--brain sentinelneedle" --no-vector` | 在 `QBRAIN_BRAIN=intended`、无模型 fixture 中 exit 1／`query required`；相同精确查询经真实 MCP 命中测试页面。`commands.cpp:120` 丢弃整个以 `--` 开头的 argv；独立子代理实证。 |

建议下一节点复用 N47L 的局部做法：在上述两个命名参数处理器的现有严格验证循环中保存 value map／flag set，后续只读取已解析值，并仅将真实 `--brain` 传给开库逻辑。保持现有动作、授权和缺省值，不改全局解析器，不扩大为全 CLI 重写。必要验收：

- 上述 memory/context 失败样本及顺序对照；正常／空／缺失值、重复与未知选项；显式 brain、环境变量、配置文件的原有优先级。
- 与基线正常输入 stdout 字节兼容；CLI/MCP 来源、原话／页面和 revision 一致；参数文字不改变脑库、来源、预算或产生意外目录。
- 同处理器的 capture/extract/forget/drain 与 context summary 保持原有写入／授权行为；保留 N47L 回归，并执行 Windows 原生及真实进程验收。

**边界：** search 的独立 `"--brain"` 与缺值选项存在语法歧义；已观察失败前误建 `brains/--no-vector`，需另行定义 literal query／`--` 边界，不能据此声称已有明确字面语法承诺。未实测 search 的 limit/mode/rerank 组合；它没有传递 `--source`，不宣称搜索来源被重路由。以上是临时合成数据下的实证，未改生产源码、未建 PR，不构成 Windows 验收。memory/context 原始命令和输出见 [旁附证据](next-stage-memory-context-evidence.json)。
