# Search 字面查询与选项边界（N47N）

本页描述 N47N 源码。现有 `multiterm-preview-17e9a435` 的 N47L 下载包不含
N47M/N47N 修复；不能用旧包验证这里的新语法。本阶段不发布新 Release/tag。

## 常规查询与两种明确写法

普通调用保留：`qbrain search "日志 前缀" --brain my-brain --json --no-vector`。
真实脑库名称需替换示例中的 `my-brain`。

当查询包含 `--brain` 等选项文字时，使用以下一种写法：

```powershell
.\qbrain.exe search --brain my-brain --no-vector --json --query "--brain sentinelneedle"
.\qbrain.exe search --brain my-brain --no-vector --json -- "--brain sentinelneedle"
```

第一种 `--query VALUE` 始终消耗紧随其后的一个命令行参数，把它作为完整查询，
也支持 `--query=VALUE`。查询内的 `--brain`、`--json`、`--rerank-llm` 等不会变成
新的选项。明确的 query 值保留首尾空白，但完全空白的查询拒绝。

第二种在真正的选项位置用 `--` 结束选项解析。之后所有参数都是查询内容，
用空格连接并沿用旧版的首尾空白裁剪；真正的选项必须放在分隔符之前。
在分隔符之后再出现的 `--` 也作为查询内容保留。

```powershell
.\qbrain.exe search --brain my-brain --no-vector --json --query "--"
.\qbrain.exe search --brain my-brain --no-vector --json -- -- --json
```

第二条实际查询是 `-- --json`。**“字面”指 CLI 不把数据二次当作选项；不是新增
精确字串匹配模式，也不保证标点必须命中。** 后端分词、候选、排名、预算与 MCP
语义未改；例如纯 `--` 可以与 MCP 一样返回空数组。

## 选项与空值

值选项为 `--brain`、`--limit`、`--mode`、`--query`，都支持 `--key=value`。
标志为 `--json`、`--no-vector`、`--rerank`、`--rerank-llm`，不接受 `=true`。
普通位置查询与选项仍可交错；明确 `--query` 不可再混入位置查询词。

除 `--query` 外，分离式值选项后紧随另一个 `--...` 会报缺值。要表达这样的
真实值，应使用等号，例如脑库名确实是 `--json` 时写 `--brain=--json`。
脑库选择仍为：真实显式选项 > `QBRAIN_BRAIN` > 配置文件 > `default`。

`--limit` 必须是完整的十进制有符号 32 位整数；允许前导 `+`，有效整数仍由
原操作限制到 1..100，零或负数得到 1。明确空值保留原配置缺省行为，
可用 `--limit=` 避免不同 Shell 的空参数传递差异。`--mode` 为
`balanced`、`conservative` 或 `tokenmax`；`--mode=` 保留缺省模式。
空脑库名称不合法。单横线开头的词（如 `-h`）仍是查询数据。

## 有意收紧的旧行为

未知双横线选项、重复选项、缺失值、混合查询形式、空查询、错误模式和不完整
或溢出的整数现在会在打开脑库前失败（退出码 2，stderr 诊断），不再静默忽略
部分输入、取重复参数的首个值，或先创建脑库再报错。

例如 `search q --limit 1tail`、`search q --mode typo`、`search q --brain --json`
和 `search q --json --json` 均拒绝；合法旧输入仍按回归范围保持输出字节兼容。
这不是承诺所有以前被宽松解析的输入都兼容。

## 权限和范围

没有新增 `--source`。CLI 搜索继续使用原来的本地搜索范围；MCP 保留已有来源
授权。测试中的 CLI/MCP 对照使用单来源合成数据，不代表两种入口拥有相同权限。

`--no-vector` 关闭查询嵌入，不等于禁止所有模型调用；真实 `--rerank-llm` 或
已有重排配置仍按原逻辑生效。本轮没有新增外发许可、模型调用模式、数据库迁移、
全局解析器改写或自动采集默认值。不把没有凭据的测试当作真实 provider-egress 验收。

验证与审核身份见 [N47N 审核](../nodes/N47N-HARD-AUDIT.md)，当前源码和公开下载
是否一致见 [当前状态](../../CURRENT-STATUS.md)。
