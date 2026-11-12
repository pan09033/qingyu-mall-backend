# 商城智能客服：功能、验收和代码阅读入口

## 本次功能范围

- 用户客服入口仍为前端 `/assistant`，改用 `/support` 接口。会话、问答及人工工单持久化到 MySQL。
- 规则咨询：BGE + PostgreSQL 检索；多主题问题不会因关键词排列顺序被限制到单个主题。
- 知识回答：聊天模型返回结构化的答案和原文证据；校验资料编号、逐字摘录和答案引用。不再把“找到了相似资料”直接当成“能够回答”。
- 发票、保修、优惠券等指定事项增加候选原文覆盖检查；资料未涉及该事项时直接说明依据不足。
- 纯预算推荐直接查询 MySQL 当前价格及有库存商品。带“耳机”等具体语义要求的推荐仍走知识检索。
- 查询本人订单和商城退款申请进度、按现有业务条件说明如何申请退款；不执行退款、支付或修改订单。
- 缺订单号时追问编号；订单查询后可继续问“那这一单还能退吗”。订单追问每次重新读取真实记录。
- 知识追问复用上一轮问题，例如先问已发货退款，再问“那需要满足什么条件”。这是明确规则支持的有限上下文，不是任意复杂长对话推理。
- 无资料或服务失败时可提交人工工单。直接说“转人工”也能创建工单；创建工单不是即时接通在线客服。
- 管理员在前端 `/admin/support` 查看完整会话、接手工单、回复并标记解决。用户回到对应会话刷新查看回复。

## 数据与权限

会话、订单身份从JWT当前用户取得，客户端不能指定 `user_id` 或上传历史角色消息。会话详情、问答、人工转接全部校验归属。其他用户的订单与不存在的订单使用相同提示。

传给聊天模型的内容是提问和检索出的商城知识。订单查询走只读业务工具，其手机号、地址、收件人和支付流水不送入模型，也不保存到客服回答摘要。

每轮请求携带UUID `request_id`；同一会话重试相同请求返回已保存的回答，不重复产生问答。相同编号配不同问题返回409。会话版本控制阻止并发旧答案覆盖新上下文，模型调用期间不持有会话行锁。

每个会话最多100轮，历史列表分页。一个会话对应一张工单，重复转接返回同一张；已解决后有新的问题应新建会话。管理员用版本号更新工单，过期编辑返回409。解决工单必须有用户可见的回复。

日志只记录会话编号、回答分支、来源数量、耗时和错误类型，不记录问题原文、订单详情或API密钥。客服表时间统一以UTC写入，接口带时区，浏览器按本地时区展示。

## 本地启动

后端在 `qingyu-mall` 环境、项目根目录运行：

```powershell
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

前端在 `mall-frontend` 目录运行：

```powershell
npm.cmd run dev
```

本次新增迁移 `f8d029a4c631`，建立 `support_conversations`、`support_turns`、`support_tickets`，不改商品、订单或现有知识库数据。2026-09-28 本地 MySQL 已应用该迁移。虚拟机容器未在本次改动中重新构建，旧镜像不会自动包含这些代码。

后续部署时需要同时更新后端与前端、构建镜像、先运行MySQL迁移，再替换后端容器。沿用项目的 `DEPLOYMENT.md`。旧 `/assistant/questions` 仍保留用于兼容以前的单轮练习；新客服能力从 `/support/conversations/...` 进入。

## 接口

| 方法与路径 | 作用 |
| --- | --- |
| POST /support/conversations | 新建当前用户的会话 |
| GET /support/conversations?skip=0&limit=20 | 分页读取本人会话 |
| GET /support/conversations/{id} | 本人会话、问答与工单 |
| POST /support/conversations/{id}/messages | 提问，正文为 question 和 request_id |
| POST /support/conversations/{id}/handoff | 提交人工工单，正文可带 reason |
| GET /admin/support/tickets | 管理员分页查看工单，支持 status 筛选 |
| GET /admin/support/tickets/{id} | 管理员查看工单及对应会话 |
| PATCH /admin/support/tickets/{id} | 管理员保存 status、reply 和读取时的 version |

## 验收方式

```powershell
python -m pytest -q
python -m scripts.evaluate_customer_support --output output/support-retrieval-evaluation.json
```

第二条只读本地 PostgreSQL 并加载本地 BGE，不调用聊天API。固定题中5道有目标资料，当前5道均在前5条命中、4道排第1；发票题仍能召回相邻的支付资料，但原文覆盖检查应阻止它进入生成。这不是完整答案准确率。

本次最终完整自动测试413项通过，前端生产构建通过。隔离浏览器完成订单查询、订单追问、刷新恢复、无资料提示、提交工单、管理员回复和用户查看处理结果；390px手机布局无横向溢出，两个浏览器会话均无控制台错误。

经授权后可执行以下命令调用已配置的聊天API，产生少量API费用，并发送测试问题和检索到的知识片段：

```powershell
python -m scripts.evaluate_customer_support --answers --output output/support-evaluation.json
```

结构与摘录校验通过，也不等于模型每个结论都正确。脚本保留回答供人工审核，不能用结构通过率冒充事实准确率。2026-09-28 用户明确授权后，已完成5次真实DeepSeek调用，另1题在本地依据不足分支拒答；6个案例的预设结构与来源条件全部通过。详见 [评测说明](customer-support-evaluation-2026-09-28.md) 和已移到项目外的 历史回答结果（仅本机保留，不随仓库发布）。

可以用 `--prompt-preview output/support-prompt-preview.json` 导出实际待发送的系统提示、测试问题和资料正文供审阅；不加 `--answers` 就不会发送到外部API。当前6题中发票题在本地就会拒答，其余5题需要模型生成。

隔离浏览器验收可运行 `python -m tests.manual.support_preview`，后端为 `127.0.0.1:8101`。前端设置 `VITE_API_BASE_URL=http://127.0.0.1:8101` 后使用5174端口。该环境使用内存SQLite、模拟知识回答和专用演示账户，不使用真实用户数据、不调用AI，关闭后数据消失；只用于开发验收，不用于部署。

## 后续读代码顺序

1. `mall-frontend/src/views/AssistantView.vue`：从点击“发送问题”开始，找到API调用。
2. `app/routers/support.py` 与 `app/schemas/support.py`：看请求入口、登录依赖和参数约束。
3. `app/services/support.py`：跟踪一次请求如何选择订单、商品、知识或人工分支。
4. `app/services/support_tools.py`：理解业务工具如何读取真实数据和限制权限。
5. `app/rag/services/grounded_qa.py`：跟踪检索、模型生成、证据校验和拒答。
6. `app/repositories/support.py` 与 `app/models/support.py`：看会话如何保存、为什么重试不会重复。
7. `app/routers/admin_support.py` 与 `mall-frontend/src/views/AdminSupportView.vue`：沿着工单继续看到人工处理结果。
8. `tests/test_support.py`：通过正常、越权、重复和故障场景核对自己的理解。

本次没有引入LangChain或MCP；只读工具和客服编排已形成明确边界，后续可在保持这些权限与回归测试的基础上替换编排方式。
