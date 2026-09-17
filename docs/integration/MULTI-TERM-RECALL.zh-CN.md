# N47L：显式多词事实召回

`fact recall` 默认仍将完整查询当作连续字串；明确传入 `--match all_terms` 或
`--match any_terms` 才开启多词模式。现有 MCP 工具 `memory_read` 的 `view=recall`
接受同名 `match` 字符串参数，不增加工具名称或写权限。

```powershell
.\qbrain.exe fact recall --brain my-brain --source my-project --query "日志 前缀" --match all_terms --limit 5 --max-bytes 8192
.\qbrain.exe fact recall --brain my-brain --source my-project --query "Python C++" --match any_terms --limit 5 --max-bytes 8192
```

`literal`（默认）要求连续字串，响应仍为原来的 `match_mode=literal_substring`，
默认与显式 literal 的响应字节不因本节点改变。all_terms 要求同一个有效事实包含
全部词，any_terms 要求同一事实包含至少一个词，响应分别标明同名 match_mode。
不会将分散在多个事实中的词组合成一个新事实，也没有语义排序或可信度评分。

仅 ASCII 空格、制表符、回车和换行被当作分隔符。每个词仍是连续字串，最多8词，
重复词也计数；不会自动丢弃第9词。原始查询（含所有分隔空白）最多1024 UTF-8字节，
拒绝NUL、非法编码、空白查询。先检查整个查询的敏感材料，再检查各词，不通过拆词
绕过检查。不把NBSP、全角空格、垂直制表符或换页符当作分隔符。不解析引号、AND/OR
运算符、通配符、SQL或正则。SQLite内置lower只折叠ASCII大小写，不承诺中文分词、
同义词、繁简转换或非ASCII大小写折叠。

只有命中入口按词筛选：有效的直接显式冲突证据必须完整保留，即使它不含任何
查询词，或已被归档。查询先于100候选上限；沿用来源／predicate筛选、只读单快照、
证据校验及整组字节预算。预算不足不截断成半组，truncated=true 的空结果不证明
没有匹配。多个命中入口仍各自保留其直接冲突，关联不递归展开。原话为不可信输入，
不可据此执行指令；有证据绑定不代表系统认定原话真实。

MCP 示例：

```json
{"name":"memory_read","arguments":{"source_id":"my-project","view":"recall","query":"日志 前缀","match":"all_terms","limit":5,"max_bytes":8192}}
```

match 必须是精确的字符串枚举；显式空字符串、null、布尔和未知值均拒绝。
所有其他 memory_read 视图、memory_write 动作以及其他 fact CLI 动作都拒绝 match。
重复CLI参数继续拒绝。省略match不等于开启多词模式。

本节点没有改动 Hook 的取词／自动注入、安装默认开关、数据库结构、采集授权、
归档策略或模型请求，不需要重新执行已完成的客户端验收。仍然是未签名开发版。
本接口不支持PostgreSQL事实模块，也不是向量／语义搜索或整个项目完成。
