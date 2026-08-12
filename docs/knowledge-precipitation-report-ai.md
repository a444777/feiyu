# 知识沉淀系统技术报告（AI 实现参考版）

> 本文是从 StaffDeck `backend/app/knowledge/` 等模块提取的完整技术规格，用于指导实现一个独立的"知识沉淀"系统。
> 所有结论均有代码出处（标注 `文件:行号`），常量、公式、提示词契约均按原文给出。
> 阅读对象：执行开发的 AI agent。按本文可实现功能等价系统，无需回看原代码。

---

## 0. 系统定位与技术路线总纲

**一句话路线**：无 embedding、无向量库、无 langchain。检索 = 中/英文词法打分（含中文 n-gram）+ LLM 分层路由（概念→文档→桶→分块）；入库 = 规则解析 + LLM 分桶 + OKF Wiki 生成 + LLM 发现 SOP/工具草稿；**所有知识写回都经过人工审核闸口**。

**核心设计哲学**（实现时必须保持的不变量）：

1. 沉淀物（Wiki/草稿/版本）与检索技术解耦——即使日后加 embedding，也只替换召回层
2. 每层 LLM 调用都必须有确定性回退（词法打分），LLM 输出必须白名单校验
3. 知识以结构化 Wiki（OKF）形态存在：可编辑、可导出、可 lint、可版本化、可溯源，而非不可读向量
4. 进化节奏 = 机器发现 + 人审核；不存在全自动写回闭环
5. 每个证据块携带完整溯源链：`文件名 / 章节路径 / evidence N`

**依赖栈**（StaffDeck 实测最小集）：FastAPI + SQLModel + SQLite（可换 PostgreSQL/JSONB）+ openai/anthropic SDK + pypdf + python-docx + beautifulsoup4 + PyYAML。无其他。

---

## 1. 数据模型（SQLModel / 可平移到任意 ORM）

所有知识表均带 `tenant_id`（多租户）和 `knowledge_base_version_id`（版本快照隔离，可空）。

### 1.1 核心表

| 表 | 关键字段 | 说明 |
|---|---|---|
| `knowledge_bases` | `id(kb_*), tenant_id, name, description, status(active\|archived\|deleted), capability_scope, metadata_json` | `metadata_json["current_version"]` 存当前主干版本号。唯一约束 `(tenant_id, name)` |
| `knowledge_base_versions` | `id(kbver_*), knowledge_base_id, version(默认"1.0.0"), name, description, status, capability_scope, metadata_json` | 唯一约束 `(tenant_id, knowledge_base_id, version)`。默认版本 ID 规则 `kbver_{kb_id}_1_0_0` |
| `agent_knowledge_branches` | `agent_id, knowledge_base_id, base_version, head_version, status, sync_state(synced\|diverged)` | 每个消费者对某库的分支指针 |
| `knowledge_documents` | `filename, file_type, title, status(processing\|ready\|failed\|archived), bucket_count, chunk_count, metadata_json, error` | `metadata_json` 存 `document_card / section_tree / ingest_schema_version / char_count / chunk_stats / bucket_quality / okf` |
| `knowledge_buckets` | `document_id, bucket_key, title, summary, token_estimate(≈len/2), metadata_json` | "内部索引"主题页。`metadata_json`: `content(≤6000), bucket_type(structure\|task\|okf), concept_type, section_ids, section_paths, representative_chunk_ids(前3), applicable_query_types, quality` |
| `knowledge_chunks` | `bucket_id, chunk_index, content, summary(≤180), source_ref, metadata_json` | 证据块 ≤900 字符。`metadata_json`: `related_group_id, related_chunk_ids, related_previous/next_chunk_id, section_id, section_path, source_span, context_window` |
| `knowledge_concepts` | `concept_id(路径式), concept_type, title, description, content_md, frontmatter_json, links_json, citations_json, source_refs_json, status` | OKF Wiki 页。唯一约束 `(tenant_id, knowledge_base_version_id, concept_id)` |
| `knowledge_discovery_suggestions` | `document_id, bucket_id, suggestion_type(skill\|tool\|warning), title, status(pending\|invalid\|confirmed\|rejected), payload_json, source_refs_json, reason` | 审核队列 |
| `knowledge_ingest_jobs` | `document_id, filename, status(queued\|running\|succeeded\|failed\|cancel_requested\|cancelled), stage, progress, error, metadata_json, started_at, finished_at` | `metadata_json`: `content_base64`(临时) / `stage_label, stage_detail, stage_stats, ingest_steps` |
| `memories` | `user_id, username, session_id, kind(conversation\|profile\|preference\|fact\|summary), content(≤1200), importance(0-1,默认0.5), metadata_json` | agent 归属存 `metadata_json["agent_id"]` |
| `message_feedback` | `rating, analysis_status, bucket, reason, summary, confidence, analysis_json` | 反馈归因 |
| `team_blackboard_entries` | `team_id, content, tags_json, source_type(member\|leader\|human), source_agent_id, source_task_id, citation_json, status, pinned` | 团队黑板 |

### 1.2 关系链

```
KnowledgeBase 1—n KnowledgeBaseVersion 1—n KnowledgeDocument 1—n KnowledgeBucket 1—n KnowledgeChunk
KnowledgeConcept 按 (version_id, concept_id) 挂载到版本
AgentKnowledgeBranch 是 (agent, kb) 上的 (base_version, head_version) 版本指针
```

---

## 2. 入库流水线（异步 Job + 10 阶段状态机）

### 2.1 入口与调度

```
POST /api/enterprise/knowledge/documents (文件 base64)
  → create_ingest_job: 内容暂存 job.metadata_json["content_base64"]
  → enqueue_async_job("knowledge_ingest", run_ingest_job, job_id)
  → _run_ingest_job
```

### 2.2 阶段表（`INGEST_STAGES`，`service.py:90`）

每阶段通过 `_update_ingest_stage` 持久化 `stage/progress/stage_label/stage_detail/stage_stats/ingest_steps`。

| key | label | progress | 实质工作 |
|---|---|---|---|
| queued | 排队中 | 0.00 | 任务落库 |
| parsing | 解析原始资料 | 0.08 | base64 解码 → `extract_text` 按扩展名抽取正文 |
| normalizing | 规范化 Source | 0.16 | 统一换行、压缩连续空行 |
| documenting | 写入 Source Document | 0.24 | 构建章节树 + 文档卡片；创建 document(status=processing) |
| bucketing | 规划 Wiki 页面 | 0.36 | 结构桶 + LLM 任务桶合并去重；先删旧桶/块/建议再重建 |
| bucket_writing | 写入 OKF Wiki | 0.48 | 桶行落库 |
| chunking | 生成引用来源 | 0.62 | 证据块切分 + 前后链 + OKF 概念生成 |
| summarizing | 刷新 PageIndex | 0.74 | 文档状态 ready，写统计 |
| discovering | 发现 SOP/工具 | 0.88 | LLM 发现 skill/tool/warning 建议 |
| done | 完成入库 | 1.00 | 清除 base64 暂存 |

**取消机制**：`cancel_ingest_job` 置 `cancel_requested` → 各阶段间 `_raise_if_ingestCancelled` 轮询抛异常 → 级联删除半成品（suggestions/concepts/chunks/buckets/document）。`cancel_requested` 超 15s 无响应由兜底任务收尾。

### 2.3 解析器（`parser.py`）

- 支持扩展名：`.txt .md .markdown .html .htm .pdf .docx`（`.doc` 直接报错）
- 纯文本：依次试 `utf-8 → utf-8-sig → gb18030 → latin-1`
- HTML：bs4 剔除 `script/style/noscript`；异常回退标准库 `HTMLParser`
- PDF：`pypdf.PdfReader.extract_text`，按页拼成 `# PDF 文档\n\n## 第 N 页` 结构
- DOCX：`python-docx` 保留 Heading 1-6（兼容中文样式名"标题 N"），表格转 `cell | cell` 行；异常回退 zipfile 直读 `word/document.xml`

### 2.4 章节树（`_build_section_nodes`，`service.py:1602`）

- 识别 markdown `#` 标题 + 中文"第X章/节/篇/部/分"双模式
- 超过 `SECTION_TARGET_CHARS = 1400` 的章节拆分，拆分块共享 `related_section_id`
- 每节点：`section_id, level, title, parent_id, path, summary, content, source_span, anchor_entities`
- `anchor_entities`：抽英文标识符、2-12 字中文词、版本号，上限 40 个
- 无标题文档退化为单一"全文"节点

### 2.5 文档卡片（`_build_document_card`，`service.py:1713`）

供检索路由层使用的压缩摘要：
- `outline`：前 60 节
- `summary`：前 12 节摘要拼接后截 520 字符
- `applicable_scenarios`：前 8 个标题
- `key_entities`：从前 12000 字符抽取，上限 24

### 2.6 分桶（`_build_buckets`，`service.py:784`）

双路并行后合并：
1. **结构桶** `_structure_bucket_specs`：按顶级目录分组
2. **LLM 任务桶** `_bucket_with_llm`（提示词 `knowledge_bucket_prompt.md`）→ `_normalize_llm_bucket_specs`

合并：`_unique_bucket_specs` 按 `bucket_key` 或 `section_ids` 签名去重；全部失败回退 `_fallback_bucket_specs`。桶内容上限 `BUCKET_SECTION_CHARS = 6000`。

### 2.7 分块（`_chunk_text_related_groups`，`service.py:1490`）

- 按空行聚合段落（无空行退化按行）；遇标题 flush 当前组
- 超 `EVIDENCE_CHUNK_CHARS = 900` 的段落按 `。！？.!?；;` 句子边界切，单句过长硬切
- 同组块建立 `related_group_id` 和 `related_previous/next_chunk_id` 前后链；单块组不建链
- `source_ref = "{filename} / {section.path} / evidence N"`
- 段落组上限 `PARAGRAPH_GROUP_CHARS = 4200`

### 2.8 关键常量

```
SECTION_TARGET_CHARS = 1400        # 章节目标长度
EVIDENCE_CHUNK_CHARS = 900         # 证据块长度
BUCKET_SECTION_CHARS = 6000        # 桶内容上限
PARAGRAPH_GROUP_CHARS = 4200       # 段落组上限
KNOWLEDGE_INGEST_SCHEMA_VERSION = 2
CANCEL_REQUEST_STALE_AFTER = 15s
```

---

## 3. OKF（Open Knowledge Format）规范

自定义 Wiki 格式，`OKF_VERSION = "0.1"`。**概念 ID 即文件路径**。

### 3.1 概念 ID 规则

`normalize_concept_id`：段内 `safe_path_segment` = 小写、非 `[a-z0-9一-鿿]` 转 `-`、≤80 字符。

```
sources/{doc-slug}                          # Source Document 入口页
sources/{doc-slug}/sections/{section-slug}  # Source Section（入库时最多 80 节）
topics/{bucket_key}                         # 由桶转换，目录按 concept_type 选择
playbooks/{key}
rules/{key}
```

### 3.2 概念类型

`Source Document / Source Section / Topic / Playbook / Business Rule / Query Analysis`

### 3.3 单文件结构 = YAML frontmatter + markdown 正文

frontmatter 字段：`type`(缺省补 Topic) `title` `description` `resource` `tags` `timestamp` `source_document` `section_path`
- `resource` 取值：`ultrarag://knowledge/documents/{id}` / `...#section={id}` / `ultrarag://knowledge/buckets/{id}`

正文固定分节：`# Summary` / `# Outline` / `# Knowledge Buckets` / `# Source Sections` / `# Notes` / `# Content` / `# Citations`

### 3.4 链接与引用

- `extract_links`：抓正文全部 `[label](target)`
- `extract_citations`：只抓 `# Citations`（或 `# 引用`）节内 `[n] [label](target)` → `{index,label,target}`
- 原始引用固定为 `[1] [Original document](ultrarag://knowledge/documents/{id})`

### 3.5 导出 / 导入 / Lint

- **导出** `export_okf_bundle`：zip = `index.md`（frontmatter + 按类型分组的链接清单）+ `log.md`（按日期倒序更新日志）+ 每概念一个 `{concept_id}.md`。`index.md`/`log.md` 为保留文件名
- **导入** `parse_okf_bundle`：`.zip`（PyYAML 解析 frontmatter，失败回退逐行解析）或单 `.md`；导入后 `upsert_concepts` 落库并为每概念建 `okf_concept_bucket` 桶 + 900 字符分块，使其可被统一检索
- **Lint** `lint_okf_concepts` 四类规则：`missing_type`、`missing_citation`（Topic/Query Analysis 豁免）、`broken_link`（目标不在库内且非 http(s)/ultrarag）、`orphan_concept`（非 Source Document 且无入站链接）、`duplicate_title`。**Lint 问题转成 `suggestion_type="warning"` 的待审建议汇入审核队列**（按标题去重，上限 100 条）

---

## 4. 检索算法（无向量方案，公式可直接照搬）

### 4.1 请求模型

```
query_type ∈ {answer, policy_check, tool_discovery, skill_discovery}
mode       ∈ {chat, skill_discovery, debug}
默认值：max_buckets=4, max_chunks=8, budget_tokens=4000, max_depth=2, need_evidence_pack=True
```

### 4.2 流水线

```
OKF 概念路由 → 文档路由 → 桶路由 → 章节展开 → 分块排序 → 多样性选取 → 相关块扩展 → 证据包
```
每步记 `route_trace`。无可见知识时直接返回空响应。

### 4.3 查询预处理（`_query_terms`）

- 正则取词：`[A-Za-z0-9_.-]{2,}|[\u4e00-\u9fff]{2,}`
- 中文噪声词删除：`我想知道/麻烦帮我/什么时候/请问/怎么/如何/什么/哪些/哪个/一下` 等 11 个
- ≥3 字中文词追加 4/3/2 字 n-gram 滑窗
- 去重，上限 96 词；多行查询按变体处理：`_score_text = 最高分变体 + 0.15 × 其余变体之和`

### 4.4 词法打分公式（`_score_single_query`）

- 整串命中：+5.0
- 单词权重：默认 1.2；≥3 字中文 2.0；≥4 字中文 2.7；长度≥5 为 3.2
- 重复出现加成：`min(1.5, 1.0 + (count-1) × 0.15)`
- 多字段加权和：`_score_weighted_text = Σ(字段分 × 字段权重)`

### 4.5 分层细节

| 层 | 字段权重 | 阈值 | LLM 路由 | 回退 |
|---|---|---|---|---|
| 概念层 `search_concepts` | heading(id+type+title+desc) 命中 +6+min(len,6)；body(去 frontmatter 前 2400 字符) +3+min(len,4)×0.5；整串 +10；Source Document -2 | `MIN_CONCEPT_SEARCH_SCORE=4.0`，上限 max(max_buckets,4)，候选加载≤120 | 无（纯词法） | — |
| 文档层 `_score_documents` | title×3.0 + filename×2.0 + document_card JSON×1.0 | `SEARCH_MIN_DOCUMENT_SCORE=2.0` | 词法 top120 → `_select_documents_with_llm`（提示词 `knowledge_document_route_prompt.md`，输出 `selected_document_ids`，白名单校验，上限 5） | LLM 失败/无效 → 词法 top5，记 `document_route_lexical_fallback` |
| 桶层 `_score_buckets` | title×3.0 + summary×1.8 + section_paths×1.4 + content×0.6；`query_type ∈ applicable_query_types` 额外 +2.0 | 2.0 | 候选≤160 → `_select_buckets_with_llm`（提示词 `knowledge_search_prompt.md`，输出 `selected_bucket_ids`） | 词法回退 |
| 章节展开 `_expand_sections` | 从 document metadata `section_tree` 取命中桶的 section_ids，递归收子节点至 max_depth | — | — | — |
| 分块排序 `_rank_chunks` | section_title×2.0 + section_path×1.5 + summary×1.4 + content×1.0；章节加成 `min(3.0, 章节分×0.2)`；排序键 `(总分, -桶名次, -chunk_index)` | `SEARCH_MIN_CHUNK_SCORE=2.0` | — | — |
| 多样性选取 | `diversity_slots = min(桶数, max(1, max_chunks-1))`，每个选中桶保底 1 个最高分块，再按名次填满 | — | — | — |
| 相关块扩展 | 以命中块为中心向两侧扩展同 `related_group_id` 连续块；约束 `RELATED_CHUNK_MAX_COUNT=6` 块、`RELATED_CHUNK_MAX_CHARS=4800` 字符；同组只展开一次 | — | — | — |

### 4.6 证据包（`_build_evidence_pack`）

每条证据含：`chunk_id / related_group_id / related_chunk_ids / document_id / bucket_id / source_path / section_path / summary / content 与 excerpt(截 6000 字符) / relevance_score / confidence_reason`（三档措辞："直接命中 / 同连续章节 / 低分但命中"）。间接块（无组且非直中且分 < 2.0）过滤。

### 4.7 回答侧引用（`citations.py`）

- `knowledge_source_candidates`：按 evidence→concept→okf 层级取第一组非空来源；同 `related_group_id` 合并为一条引用
- `knowledge_citations_from_results`：按语义 identity 去重后编号 `[1]…[n]`（默认 limit=4）
- `compact_knowledge_citation_labels`：按回答中首次出现顺序重编号，自动补"参考来源"行
- `restore_truncated_atomic_references`：把模型缩写的邮箱类原子引用从证据原文唯一还原

### 4.8 运行时接入

agent 输出 `knowledge_query` 触发检索 → 结果压缩后经 `retrieved_knowledge` 注入下一轮。注入规则（`step_agent_knowledge_rules.md`，全文 1 行）：**只基于本轮证据推进，证据不足不得编造，需再查输出 knowledge_query**。

---

## 5. 提示词契约清单（`llm/prompts/`）

| 文件 | 输入 → 输出契约 |
|---|---|
| `knowledge_bucket_prompt.md` | 章节节点列表(section_id/path/title/summary/excerpt≤1800，前60节) → `{"buckets":[{bucket_key,title,summary,bucket_type="task",concept_type,section_ids,applicable_query_types}]}`；只补跨章节任务桶，禁止编造，必须保留 section_ids |
| `knowledge_document_route_prompt.md` | query + 文档卡片(id/title/summary/outline/key_entities) → `{"selected_document_ids":[...]}`；只选不答，可空数组 |
| `knowledge_search_prompt.md` | query + query_type + 桶摘要(id/title/summary/bucket_type/applicable_query_types/section_paths/quality) → `{"selected_bucket_ids":[...]}`；按相关性排序，可空 |
| `knowledge_discovery_prompt.md` | 文档信息 + 桶摘要与 excerpt(≤2400) → `{"discoveries":[{suggestion_type,title,bucket_id,reason,source_refs,payload}]}`；仅原文明确业务流程才产 skill、明确接口信息才产 tool；skill payload 为完整 SkillCard，字段名严格（node_id/type/name/instruction、source_node_id/next_node_id），图须从 start 可达且可达 terminal；`ask_user/continue_flow/answer_user/handoff_human` 为平台动作白名单 |
| `memory_extractor_prompt.md` | 对话历史 + existing_memories + step_result/tool_result → `{"memories":[{operation:upsert\|delete,kind:profile\|preference\|fact,key,content,importance}],"updated_summary":""}`；只存稳定用户记忆，禁存业务流水；同 key 覆盖；importance 参考区间：称呼≥0.9、偏好 0.75-0.9、弱事实 0.5-0.7 |
| `skill_distiller_prompt.md` | 原始文本 + 可用工具目录 → SkillCard 草稿 + warnings + tool_suggestions |
| `skill_editor_prompt.md` | current_skill + target_path(s) + instruction → `{assistant_message, patches:[{path,value}], draft_skill?, tool_mentions?}`；局部改写，url 必须逐字来自上下文，禁止臆造 API 路径 |
| `skill_reflection_prompt.md` | source + candidate_skill + rubrics → `{passed, rubric_results:[{name,passed,finding,origin}], draft_skill?}`；7 条 rubric：source_alignment / closed_loop / adaptive_progression / tool_grounding / tool_call_format / side_effect_confirmation / interruption_and_recovery |
| `step_agent_knowledge_rules.md` | 运行时注入规则（1 行）：只用本轮 retrieved_knowledge，不足不得编造，需再检索输出 knowledge_query |
| 反馈分析（内联于 `feedback/service.py:29`） | 反馈 + 上下文 + 执行轨迹 → `{bucket, confidence, reason≤80字, summary≤120字, evidence≤3条, suggested_action≤80字}` |

**LLM 交互统一模式**：读 .md 提示词 → `generate_json` → pydantic 校验 → 白名单过滤 → 失败回退。

---

## 6. 沉淀与进化机制

### 6.1 发现建议生命周期（核心闭环）

```
入库末段 → LLM 发现（knowledge_discovery_prompt.md）
  → skill 类立即跑 validate_discovered_skill（失败落 status="invalid" 附原因）
  → 落库 status="pending"
  → GET /discoveries 列表对 pending skill 再校验一次（失效不展示）
  → 人工 confirm / reject
```

- `confirm_discovery`（仅 pending 可转，否则 409）：
  - tool → 创建 Tool 行（name 冲突 409，默认 bucket="知识自发现工具"、method=POST、enabled=True）
  - skill → 创建 Skill 行 status="draft"（skill_id 冲突 409，禁止覆盖现有技能）
  - warning → 仅标记 confirmed
  - `IntegrityError` 统一转 409
- `reject_discovery` → status="rejected"

**SkillCard 校验规则**：顶层/节点/边字段白名单（未知字段即拒）；pydantic 校验（错误取前 5 条）；`skill_id`/`name` 非空；节点须有 `node_id/name/instruction`；从 `start_node_id` BFS 全部节点可达；反向 BFS 全部节点可达 `terminal_node_ids` 之一。

### 6.2 版本分支语义（`agents/branching.py`）

- **可见性**：overall agent 看主干（`kb.metadata_json["current_version"]`，缺省 1.0.0）；普通 agent 看自己分支 `head_version` + 资源绑定可见性
- **sync-from-overall**：`base = head = 主干当前版本`，`sync_state="synced"`——放弃本地分叉
- **promote-to-overall**：次版本 +1（1.0.0→1.1.0）建新版本行，`_retag_knowledge_version` 把 documents/buckets/chunks/concepts/discoveries 五张表的 `knowledge_base_version_id` 从源版本**指针重挂**到目标版本（不复制数据），更新 `current_version`，分支 `base=head=新版本`
- **rollback**：head 指回指定版本；`sync_state = synced if head==base else diverged`
- 分支演进版本号：`{base}-branch.{agent_id}.{n}`
- **删除语义**：普通 agent 删库 = 分支+binding 标记 deleted（隐藏）；仅管理员物理级联删除（8 张子表）

### 6.3 记忆捕获（`memory/`）

- 触发：每轮对话结束 `enqueue_memory_capture` → 异步 job `memory.capture_turn`；截取到该轮 assistant 消息为止的最近 12 条 user/assistant 消息
- 抽取：对话 + 已有记忆（最近30条）+ step_result/tool_result → LLM；非法 kind/operation 过滤；upsert 按 `(tenant,user,kind,key,agent)` 覆盖（content≤1200），delete 按键删；importance 夹取 [0,1]，非法默认 0.7
- 读取：只放 profile/preference/fact；按 `(user,kind,agent_id,key)` 去重；失败只记事件不影响主链路

### 6.4 反馈分析（`feedback/service.py`）

- 赞踩 → 异步 LLM 分析（最多 3 次尝试，退避 0.6s×attempt；无默认模型 → needs_model；失败 → failed+retryable）
- 归因桶：`model_issue / skill_issue / tool_or_system_issue / user_random_or_unclear / positive_or_resolved`（rating=up 且桶不明时强制 positive_or_resolved）
- 分析载荷：目标消息 ±6 条邻近消息 + session slots/active_skill + 最近 30 条执行轨迹事件
- 聚合：按桶计数、top5 点踩摘要、"当前点踩主要集中在「X」（n 次）"话术
- **已知断点**：`suggested_action` 仅存储展示，没有自动改技能/知识库的执行器——**独立系统应补上这一环**（见 §8.4）

### 6.5 团队黑板（`teams/service.py`）

写入管线 `write_blackboard_entries`：
1. 规范化（压缩全部空白）
2. 批内去重
3. 与既有 active 条目完全相同 → 跳过
4. **是既有条目子串 → 跳过**（已有更完整条目）
5. **既有条目是新内容子串 → 合并更新**（最长匹配者：覆盖 content、并集 tags、更新 citation/updated_at，即 supersede）
6. 否则新增。citation 回链 `{task_id, task_title}`

来源：`source_type ∈ {member(TL 裁决), leader, human}`；成员在报告末尾输出 `{"blackboard_suggestions":[{content,tags}]}`，经 TL 验收裁决后落板。

读取注入：query 与条目 tags 子串重叠计分 → `(-score, 非pinned, -updated_at)` 排序取 top 10，渲染 `- [tag1,tag2] content`。

升级通道：高价值黑板条目可走完整 `INGEST_STAGES` 沉淀进知识库。

---

## 7. API 端点清单

### 7.1 `/api/enterprise/knowledge-bases`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | "" | 列表 |
| POST | "" | 创建 |
| GET/PUT | "/{kb_id}" | 详情/更新 |
| GET | "/{kb_id}/versions" | 版本列表 |
| GET/PUT | "/{kb_id}/okf/concepts/{concept_id:path}" | 概念读取/人工编辑 |
| GET | "/{kb_id}/okf/export" | OKF zip 导出 |
| POST | "/{kb_id}/okf/lint" | 健康检查 → warning 建议 |
| DELETE | "/{kb_id}" | 删除（分支隐藏或物理级联） |
| POST | "/{kb_id}/sync-from-overall" | 分支对齐主干 |
| POST | "/{kb_id}/promote-to-overall" | 分支提升为新主干版本 |
| POST | "/{kb_id}/rollback" | 分支回滚 |

### 7.2 `/api/enterprise/knowledge`

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | "/documents" | 上传文档（base64）并 enqueue 入库 |
| POST | "/okf/import" | OKF zip/md 导入 |
| GET | "/jobs", "/jobs/{job_id}" | 任务列表/详情（含进度阶段） |
| POST | "/jobs/{job_id}/cancel" | 取消入库 |
| GET/PUT | "/documents", "/documents/{document_id}" | 文档列表/详情/更新 |
| GET/PUT | "/documents/{document_id}/buckets", "/buckets/{bucket_id}" | 桶列表/编辑 |
| GET/PUT | "/buckets/{bucket_id}/chunks", "/chunks/{chunk_id}" | 分块列表/编辑 |
| POST | "/search" | 知识检索（返回桶/块/trace/概念/证据包） |
| GET | "/discoveries" | 建议列表（按可见版本过滤） |
| POST | "/discoveries/{id}/confirm", "/discoveries/{id}/reject" | 审核 |

---

## 8. 独立系统实现路线建议

### 8.1 组件拆分（推荐模块边界）

```
parsers/          # 按扩展名分派的解析器（pypdf / python-docx / bs4 / 多编码纯文本）
ingest/           # 10 阶段流水线 + job 状态机 + 取消/级联清理
indexing/         # 章节树、文档卡片、双路分桶、分块+前后链
okf/              # 概念生成/upsert、导出/导入/lint
retrieval/        # 词法打分 + LLM 分层路由 + 证据包 + 引用重编号
discovery/        # LLM 发现 → 校验 → pending 队列 → confirm/reject
versioning/       # 版本 + 分支 sync/promote/rollback（指针重挂）
memory/           # 可选：turn 后异步 LLM 记忆抽取
feedback/         # 可选：赞踩归因分析
llm/              # 提示词文件 + generate_json + pydantic 校验 + 白名单回退
```

### 8.2 实现顺序

1. 存储层 9 张核心表（§1）
2. 解析器 + 章节树 + 文档卡片（§2.3-2.5）——**章节树是检索的地基，最先做**
3. 分桶 + 分块（§2.6-2.7）
4. 检索全链路（§4），先纯词法跑通，再接 LLM 路由
5. OKF 生成 + 导出/导入/lint（§3）
6. 发现队列 + 审核 API（§6.1）
7. 版本分支（§6.2）
8. 可选：记忆、反馈、黑板

### 8.3 无向量方案的权衡（照抄前必读）

**收益**：零额外基础设施（SQLite 即可）、打分完全可解释、无 embedding 模型运维、中文靠 n-gram + LLM 路由补偿语义。

**代价**：语义召回弱（同义词/改写漏召靠 LLM 路由层弥补）、每次检索 2 次 LLM 调用（文档+桶路由）带来延迟与成本、千级文档下词法预筛和 LLM 候选窗口（120/160）成瓶颈。

**迁移路径**：若预期文档量 > 数百篇或查询语义多样，在文档层/桶层加 embedding 预筛（向量库只用于召回候选，保留 LLM 精排与词法回退），其余架构原样保留。

### 8.4 相对 StaffDeck 应补强的点

1. **反馈闭环补全**：把高置信 `skill_issue` 的 `suggested_action` 自动转成 discovery suggestion，完成"反馈→草稿→人工确认"闭环
2. **检索可观测**：`route_trace` 每步落库，便于调权重
3. **审核队列统一**：discovery、lint warning、feedback 转化建议复用同一 pending 队列与 UI
4. **黑板升级通道**：高价值黑板条目一键走完整入库管线

### 8.5 实现红线（不可省略的设计）

- 每层 LLM 调用必须有确定性词法回退
- LLM JSON 输出必须 pydantic 校验 + ID 白名单过滤（防幻觉引用不存在的文档/桶）
- 证据块必须带 `source_ref` 溯源链
- 知识写回（Skill/Tool/概念）必须过人工审核状态机，无自动直写
- 版本演进用指针重挂，不复制数据
- 入库 job 全程可取消，取消必须级联清理半成品
