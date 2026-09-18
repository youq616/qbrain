# N47N：search 查询内容与命令选项

本变更只处理命令行语法，不把 search 改为全文精确子串搜索，不改变排序、
向量、MCP 来源权限或模型调用策略。以下语法需要包含 N47N 的新源码构建；
旧 N47L Release 不支持新增语法。

普通命令保持可用，选项可穿插在普通查询词之间：

```powershell
.\qbrain.exe search "日志前缀" --brain my-brain --json --no-vector
```

查找以选项形式开头的文字，用以下任意一种形式：

```powershell
.\qbrain.exe search --brain my-brain --json --no-vector --query "--brain sentinelneedle"
.\qbrain.exe search --brain my-brain --json --no-vector -- "--brain sentinelneedle"
.\qbrain.exe search --brain my-brain --json --no-vector "--query=--brain sentinelneedle"
```

`--` 自身不是查询的一部分，它之后所有参数都是查询文字，即使是 `--json`、
`--brain`、`--mode`、`--rerank-llm`。实际选项必须放在它前面。查询多个参数仍
用单个空格连接，并去除整体首尾空白，与原普通位置参数路径一致。

`--query` 消费紧随的一整个参数，包括以 `--` 开头的参数；它不重新解析里面
的内容。`--query "--"` 可传入字面 `--`。显式查询保留传入文本，不与其他
位置查询拼接。空或只有空白的查询按 query required 拒绝，不打开脑库。
只加引号不能让选项自动变为查询，因为 shell 会移除引号；应使用明确入口。

`--brain`、`--limit`、`--mode` 支持 `--名称=值`。它们的分离值若以 `--`
开头会被视为缺值拒绝；确需这样的值，使用等号形式，例如 `--brain=--json`。
限额和模式后续含义仍由已有 search 操作处理，本阶段不改变其数值/模式策略。

重复真实选项、未知长选项、标志携带值（如 `--json=true`）、缺值，以及混用
`--query` 与位置查询都会在打开脑库前退出 2，并给出错误。单横线开头的
普通文字仍是查询。`--source` 不是 search CLI 选项，本次没有增加此选项；
本地搜索仍按原策略跨本脑库来源检索，MCP 搜索仍按既有来源限制。

`--no-vector` 仅关闭向量查询请求，不代表所有模型请求都关闭。显式选择
`--mode tokenmax` 或相应重排标志仍保留原有重排策略。查询文本本身不会再
把这些标志或模式打开。本次测试使用合成数据且没有真实提供方凭据。
