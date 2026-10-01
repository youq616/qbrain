# 统一检索与 Cursor 开发候选

本候选整合已分别验证的 N49A、PR68 目录范围检索和 PR67 Cursor 适配；新的统一版本仍须独立完成所有验收。

目录检索示例：qbrain search --query needle --uri qbrain://default/resources/docs/ --no-vector --json
目录 URI 必须以斜线结尾。resources、skills、memories 分别限定命名空间，目录前缀在排序前限制候选。没有 --uri 时保留原检索路径。
--no-vector 与 conservative 禁用查询向量生成，但显式 LLM rerank 或 tokenmax 仍可调用已配置模型；不能把它们解释为无模型开关。

Cursor 接入限项目目录，默认关闭采集，采集和事实提升需要各自明确许可。只在 sessionStart 返回 additional_context；beforeSubmitPrompt 不伪造提问前上下文注入。测试安装只在可丢弃的 CI 目录进行。

当前并不证明真实登录 Cursor 消费记忆、真实模型质量或费用、PostgreSQL 对等、用户 Windows11 环境、签名发行或整个项目完成。没有修改主分支或公开发布包。最终证据在源代码树外绑定精确提交；仓库中的待验收说明保留为发布前历史。
