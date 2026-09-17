N47L 固定草稿恢复实施交接

恢复 workflow 与离线验证已完成，交付字节已冻结。本文记录实施和离线验证范围；实际恢复运行、公开 release 状态及其最终回读由 root 和 CI 审查者另行确认。

冻结文件是 `n47l-publish-recovery.yml`，SHA256 为 `d81f84d3dd0b2f83b05ad6812fdca4f7105db0ee36a85624041b68add42f60f3`。root 已告知将该字节提交至原 delivery 分支，恢复提交为 `7caeb8f24b3a9b8e40d512bad23c7c81181dd110`。本实施子代理仅写 scratch 文件、执行离线验证，没有执行提交、推送或发布。

原交付 run `35233247840`、attempt `1`、commit `2f254681c31fd493fa9cb5ab14ae089608f8a4ad` 已完成 1094 项候选回读并创建草稿，但随后通过 tag 查草稿失败，尚未执行发布 PATCH。GitHub 的按 tag 查询接口只返回已经发布的 release；因此恢复入口直接固定为 release ID `390787606`，下载入口直接固定为 asset ID。原工作流的失败记录保留，原上传资产也保持原字节。

恢复仍只在 `delivery/n47l-reviewed-17e9a435` 分支及原 `.github/workflows/publish-reviewed-n47l.yml` 路径触发。原全部 source、review、merge、PR 28、SUMMARY、固定 N44/N42 run、实时完整 jobs/steps、七份原 CI artifact 元数据与大小/hash、离线 verifier 1094 项及原 CI inner ZIP 门槛均保留。对原冻结 `n47l-publish-final.yml` 的对应完整代码段进行了逐字节比较，结果一致；源文件 SHA256 为 `389b6f38cf695e2f1ebfe149761e45ccd5b8dac35142f97e8ff1650991fe7a3a`。

产品 source 固定为 `17e9a435f94e45b3ca22d3da062ba4683c135c4b`，tree 为 `f9d42819772df53dd8c6337c3cb19c8940d7023a`；N44 run 为 `35228307025`，N42 run 为 `35228306922`。恢复不会构建或重新压缩产品。

恢复只接受以下同一草稿的三份原资产，并在下载前、发布前和公开后重复绑定唯一名称、唯一正整数 ID、uploaded 状态、精确大小和 GitHub `sha256:` digest。缺失 digest、同字节换 ID、重复 ID、错误 source/tag、资产缺失或草稿已公开均拒绝。

| 资产 | 固定 ID | 字节数 | SHA256 |
| --- | ---: | ---: | --- |
| qbrain-windows-x64-multiterm.zip | 570420529 | 2114341 | ed44a43d79e1e76efa768e74872223cd5d867dfb92881fe67aab129789cd4408 |
| PROVENANCE.json | 570420531 | 2049 | 6cc243b432dbb444f83f9983f4294d0a4c516edc2ad0180b9a2940cc810cd59a |
| SHA256SUMS.txt | 570420528 | 181 | 5cd993f0e3a1fe73cfb818706f27e353902738ceabb5e01482b120489c0d715b |

下载使用 `GET releases/assets/{固定 ID}` 和 `Accept: application/octet-stream`。如果服务返回 JSON 或错误字节，精确大小/hash 检查失败。产品字节还必须与重新验证的原 CI inner ZIP 完全相同；实际下载的原 PROVENANCE 必须与固定 source/review/merge、初始失败交付 run/attempt/commit 等完整预期字段一致；原 SHA256SUMS 必须逐字节绑定产品和原 PROVENANCE。恢复代码没有创建、删除、替换、上传 release 资产或改变 tag 的路径。

所有门槛通过后，唯一 release/tag/产品资产变更是 `PATCH releases/390787606`，body 为 `{"draft":false,"prerelease":true,"make_latest":"false"}`。之后检查 PATCH 响应、按 ID 和按 tag 的公开元数据、source tag 与非 latest 状态。原有 Actions 证据 artifact 上传仍保留，供真实恢复运行回读。

交付 artifact 名仍为 `qbrain-n47l-reviewed-delivery`，成功路径包含：

- `readback.json`：重新验证原七份 artifact 的 1094 项结果。
- `release-assets/`：三份从固定 asset ID 实际下载的原字节。
- `draft-before-publication.json`、`release-public.json`、`release-by-tag.json`：发布前后固定 release 元数据。
- `publication.json`：保留原 PROVENANCE 的 `delivery_run`、`delivery_run_attempt`、`delivery_commit`，另列 `initial_delivery_*`、`initial_delivery_conclusion: "failure"`、本次 `recovery_run`、`recovery_run_attempt`、`recovery_commit`、`publication_mode: "RECOVER_FIXED_DRAFT"`、`original_assets_replaced: false`、原 PROVENANCE hash 及固定 asset pins。

我方检查程序 `n47l-recovery-offline-check.py` 的 SHA256 为 `ddf237948c523fe72542d1b4527c73bcfd2f2782f2a224dc75524949c5bb3fef`；结果 `n47l-recovery-offline-check.json` 的 SHA256 为 `9db079271046093107c14964065331e272aef71f5d9627d6dbeecc1cb6f0b943`。实际从冻结 YAML 抽取恢复尾段和原 helper 执行，transport 使用 mock。16 个案例全部符合预期：正确控制只 PATCH 固定 release 一次；15 个错误身份、错误状态、错误资产、错误下载、下载后资产变化、发布前 tag 变化及原 CI 字节不符的案例均在 PATCH 前拒绝，release 变更次数为零。检查还确认只有一个非 GET 的 API 调用且为指定 PATCH。

可复跑命令：

```sh
python3 -I -S -B /workspace/scratch/8ee4dd18bee0/n47l-recovery-offline-check.py \
  --workflow /workspace/scratch/8ee4dd18bee0/n47l-publish-recovery.yml \
  --original /workspace/scratch/8ee4dd18bee0/n47l-publish-final.yml \
  --fixture /workspace/scratch/8ee4dd18bee0/n47l-recovery-review-fixture \
  --metadata /workspace/scratch/8ee4dd18bee0/n47l-evidence-tool/new-candidate/candidate-metadata.json \
  --report /workspace/scratch/8ee4dd18bee0/n47l-recovery-offline-check.json
```

独立 storage 审查者对同一冻结 workflow 执行了另外 22 个案例，结果 `PASS_RECOVERY_OFFLINE_CONTROL_SCOPED`：正常路径通过，20 个发布前负例没有 release 变更，另一个案例明确演示 PATCH 已提交后连接失败的窗口。其测试原样保留 API helper 并替换 transport，模拟按 tag 仅返回已发布 release，所有案例在发布前查 tag 的次数均为零。审查程序为 `n47l-recovery-review-probe.py`，SHA256 `78315ee1cf17aa2f55a977787d5b043d68138c125be7dbde29e927904f5553c9`；报告为 `N47L-RECOVERY-OFFLINE-REVIEW-FINAL.json`，SHA256 `37b2ed75609a79d5f54c16e75d1133b4dadf3643e56e9a391a4c60cbedc242af`。独立审查未发现此恢复范围内的新 blocker。

两套离线测试均未连接 GitHub、未运行产品、未重新执行 CI 全部门槛或真实发布。产品 fixture 来自原 CI inner ZIP；PROVENANCE 和 checksum fixture 按原冻结工作流及已确认初始运行身份重建，并已与真实 draft 元数据的大小/hash 对齐，不能把该 fixture 称为实际 release 下载。真实下载证据由恢复运行产生。

发布前门槛失败不会由本恢复流程发布草稿。PATCH 在服务端成功后，如果后续 API 或网络检查失败，release 可能已经公开而收据尚未写入；此窗口不具备跨远端请求的原子性，因此不能承诺所有异常都保持 draft。失败后应先读取真实状态，不得直接重新创建、覆盖或移动已有 release、资产或 tag。

事实范围继续限定为 unsigned、prerelease、nonlatest 的原 CI 产品字节；没有新增 PostgreSQL 集成、live host/model 消费或 provider 出站验收，也不代表整个项目完成。
