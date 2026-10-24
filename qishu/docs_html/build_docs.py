"""Rebuild the offline atlas from tracked source and reachable Git history.

Run from any directory: python -B qishu/docs_html/build_docs.py
No network, package installation, or application startup is required.
"""
from pathlib import Path
from collections import defaultdict, Counter
import subprocess, json, re, hashlib, datetime

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent.parent

def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args]).decode('utf-8', 'replace')

def dump(path, value, prefix='window.ATLAS='):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(prefix + json.dumps(value, ensure_ascii=False, separators=(',', ':')) + ';\n', encoding='utf-8')

# Explicit editorial taxonomy. Membership is evidence-driven; not a runtime registry.
MODULES = [
 ('assistant','内置助手与操作目录','全局助手把页面上下文转换成操作请求，操作目录负责发现与分派；权限只缩小调用者已有能力，不能替代原 HTTP/service 授权。','assistant|operations|operation_catalog',
  ['全局侧栏与页面上下文','内置文档问答','操作发现与参数描述','知识库、FAQ 与文档管理','模型、MCP 与 Skill 管理','只读、确认与自动写入等级','试运行、跳转与页面刷新'],
  ['internal/types/assistant.go','internal/agent/operations/catalog.go','internal/agent/tools/operations.go','internal/router/operations.go']),
 ('collaboration','多智能体协作','协作组、成员、任务与事件持久化，由 runtime 租约和父子执行绑定推动；子智能体消息是数据，不构成新的用户授权。','collaboration',
  ['创建子任务与成员','发消息、追加任务与中断','持久邮箱与事件交付','运行租约与重启恢复','父子授权继承与 MCP 边界','协作状态与前端任务视图'],
  ['internal/agent/collaboration/runtime.go','internal/agent/collaboration/store.go','internal/application/service/agent_collaboration.go','internal/agent/tools/collaboration.go']),
 ('automation','定时运行与通知','定时任务保存触发配置并由数据库竞争领取；每次执行重新检查拥有者、模型与授权，运行结果通过站内通知交付。','automation|notification',
  ['触发时间与时区校验','任务创建、编辑、暂停与恢复','调度领取与并发执行','模型配置与历史结果携带','运行授权与人工确认','手动运行、取消与历史','站内通知与已读状态'],
  ['internal/router/routes_automation.go','internal/application/service/automation_scheduler.go','internal/application/service/automation_runner.go','internal/automation/trigger.go']),
 ('background','后台活动与异步 Shell','ActivityRegistry 与 NoticeInbox 提供统一的活动、结果通知和取消契约；Shell 后台执行、Agent 等待和前端活动面板共享这些边界。','background|shell_job',
  ['活动登记与作用域','结果收件箱与已见游标','异步 Shell 任务','状态查询与取消','执行保活与关闭回收'],
  ['internal/types/interfaces/background.go','internal/application/service/background_work.go','internal/background/lifecycle.go','internal/agent/background.go']),
 ('images','图片知识与多模态检索','图片资源、来源文档、图像向量与视觉重排共同组成图片检索路径；按开关和模型能力启用，不等同于普通文本向量检索。','gallery|image_vector|image_embedding|multimodal_embedding|image_preprocess|image_pipeline|image_multimodal|knowledge_image|knowledgebase_search_image|knowledgebase_image',
  ['图片图库与来源筛选','图片向量索引与召回','多模态 Embedding 配置','视觉重排与模型上下文','OCR 前有界预处理'],
  ['internal/application/service/knowledge_image_reader.go','internal/application/service/knowledgebase_search_image.go','internal/application/service/image_multimodal.go']),
 ('knowledge','知识库与文档','知识库、文档、FAQ、标签、目录和分块构成知识底座。入库与编辑需同时考虑数据库、索引和文件资源。','knowledge|chunk|faq|tag|folder|question',
  ['知识库创建、配置与复制','文件、URL、文本与图片入库','目录上传与文档归档','解析进度、取消与重新解析','FAQ 导入、编辑与批量操作','标签与自动标注','分块编辑、差异与历史版本','原文、图片与来源定位','文档删除、迁移与清空'],
  ['internal/application/service/knowledge_create.go','internal/application/service/knowledge_process.go','internal/application/service/knowledgebase.go','internal/application/service/chunk.go']),
 ('rag','检索与 RAG','知识问答按有效知识范围和开关组装管线，纯聊天分支不执行检索。重排、上下文构造与引用必须共同维护。','chat_pipeline|retriev|rerank|knowledge.search|knowledge-chat',
  ['关键词与向量混合检索','并行检索与共享知识范围','查询理解与扩展','实体与图谱检索','重排、去重、上下文扩展','Web 搜索与正文补充','流式生成与引用还原','FAQ 优先与 Wiki 增强','结构化数据分析'],
  ['internal/application/service/session_knowledge_qa.go','internal/application/service/chat_pipeline/search_parallel.go','internal/application/service/chat_pipeline/rerank.go','internal/application/service/chat_pipeline/into_chat_message.go']),
 ('agent','Agent 引擎与配置','自定义 Agent 配置经能力过滤后生成本次执行的工具表，ReAct 循环在模型、工具结果和会话控制之间推进。','agent|react|todo',
  ['Agent 创建、复制与类型预设','工具白名单与能力过滤','ReAct 多轮执行','上下文预算与历史压缩','推理等级与输出预算','运行中追加指令','停止、分叉与回退','内置与共享 Agent','工具事件、Token 与执行追踪'],
  ['internal/application/service/agent_service.go','internal/application/service/session_agent_qa.go','internal/agent/engine.go','internal/agent/act.go']),
 ('tools','工具系统与模型协议','内置工具实现 Tool 接口，通过 ToolRegistry 注册。请求级 modelcontext 负责模型临时句柄和持久标识之间的编解码。','internal/agent/tools|modelcontext',
  ['知识搜索、文档读取与列表','Wiki 与图谱工具','数据库查询与数据分析','网页搜索与抓取','记忆检索与任务清单','工具参数编解码','重复工具名拒绝与输出限额','工具结果与引用证据'],
  ['internal/agent/tools/registry.go','internal/types/agent.go','internal/modelcontext/registry.go','internal/modelcontext/tool_policy.go']),
 ('skills','Skills 安装与执行','Skill 元数据、目录与安装状态决定模型可见能力；执行环境与会话沙箱关联，安装流程和运行流程需分别阅读。','skill|clawhub|skillhub',
  ['Skill 元数据与 frontmatter','Skill 目录注册与查询','ZIP、Git 与外部市场安装','安装引导、追问与停止','安装事件与转录','技能文件读取与编辑','技能镜像与环境变量','会话技能加载'],
  ['internal/agent/skills/manager.go','internal/agent/skills/loader.go','internal/agent/skills/tenant_source.go','internal/application/service/agent_service.go']),
 ('sandbox','沙箱、终端与桌面','命名空间配置决定会话执行后端；标准 Web 和 Lite 本地主机执行存在不同前提，不可把本地能力视为普遍可用。','sandbox|shell|localsandbox|project_dir|checkpoint',
  ['工作空间沙箱配置','Docker、E2B 与 Cube 后端','Lite 主机沙箱','Shell 执行与文件操作','交互终端 WebSocket','图形桌面与活动保活','快照、分叉与回退','项目目录与执行审批','环境变量、网络策略和超时'],
  ['internal/sandbox/tenant_resolver.go','internal/sandbox/session_manager.go','internal/agent/approval/gate.go','internal/handler/session/sandbox_terminal_ws.go']),
 ('browser','本地浏览器能力','BrowserSkill 连接用户浏览器；连接状态、会话归属、工具描述和事件展示共同构成浏览器使用体验。','browserskill|browser_source|browserconnection|browserTool|local-browser',
  ['浏览器配对与连接','Agent 浏览器工具','连接状态与来源偏好','实时事件与任务预览','会话内浏览器控制'],
  ['internal/browserskill','internal/agent/tools/browserskill.go','internal/handler/session/browserskill.go','frontend/src/stores/browserConnection.ts']),
 ('mcp','MCP 客户端与服务端','连接外部工具和向外发布知识是两种方向。客户端管理连接、OAuth 与工具暴露；服务端管理端点、范围、令牌和限流。','mcp',
  ['外部 MCP 服务配置','OAuth 授权与连接管理','工具元数据与按需发现','工具审批与执行','内置 MCP 端点发布','端点令牌、范围与速率限制','旧 Python MCP 服务'],
  ['internal/mcp','internal/mcpserver','internal/router/routes_mcp_endpoint.go','internal/agent/tools/registry.go']),
 ('wiki','Wiki 知识组织','Wiki 从文档知识中生成页面，并维护页面修订、引用、关联和问题修复。入库是异步任务，不等同于一次模型调用。','wiki',
  ['文档到 Wiki 的异步入库','页面、目录与分类','页面检索与引用','页面编辑、修订和回滚','问题标记与修复 Agent','批量去重与后续任务','源文档删除与 Wiki 撤回'],
  ['internal/application/service/wiki_ingest.go','internal/application/service/wiki_ingest_batch.go','internal/application/service/wiki_page.go','internal/agent/tools/wiki_route_resolver.go']),
 ('memory','长期记忆','个人记忆从调用者身份派生，受空间、用户与 Agent 开关约束；记忆召回、管理和整合是不同操作。','memory',
  ['个人记忆开关','记忆确认与拒绝','记忆条目与主题管理','对话中的记忆召回','Agent 记忆搜索','整合、清空与导出'],
  ['internal/application/service/memory','internal/router/routes_memory.go','internal/application/service/chat_pipeline/memory_recall.go']),
 ('session','会话、消息与产物','Session 是用户会话资源；消息、附件与产物都需要会话归属和持久化证据，流式输出同时受到停止与续流控制。','session|message|stream|artifact|attachment|suggestion',
  ['会话创建、列表与置顶','消息历史与搜索','SSE 续流与停止','上传附件与临时文档','建议问题与反馈事件','生成标题','产物收集、下载与删除','跨会话产物库','分叉、回退和运行中消息'],
  ['internal/handler/session/qa.go','internal/handler/session/stream.go','internal/application/service/session.go','internal/application/service/artifact_collector.go']),
 ('identity','认证、空间与组织权限','认证身份、空间角色、资源所有权、组织共享、API Key 能力与知识范围需要逐层核对，任一层不能替代另一层。','auth|tenant|principal|organization|share|access|rbac|invitation|user_resource|favorite',
  ['登录、注册与刷新令牌','OIDC 登录与状态校验','空间与成员管理','邀请与组织加入','Owner/Admin/Contributor/Viewer','资源创建者权限','知识库与 Agent 共享','API Key 能力与范围','个人收藏与管理员操作','审计日志'],
  ['internal/middleware/auth.go','internal/application/access/README.md','internal/router/rbac.go','internal/types/principal.go']),
 ('models','模型接入与目录','模型协议、厂商、凭证和元数据集中管理，聊天、Embedding 与 Rerank 使用各自边界。新增厂商需复用现有目录与注册机制。','model|embedding|ollama|reranking',
  ['聊天、Embedding、Rerank 模型','厂商与模型元数据目录','凭证字段管理','有效模型配置解析','模型调试与复制','流式协议适配','模型调用限流','生成目录与行为校验'],
  ['internal/models','internal/application/service/model.go','internal/application/service/model_catalog.go','config/models.json.example']),
 ('parser','文档解析与来源坐标','Go 引擎注册表先解析显式引擎和简单格式，其余可经 gRPC 转交 Python docreader；解析文本、图片与来源信息由 Go 侧组织持久化。','docreader|docparser|sourceloc|textconv|parser|source_locator',
  ['解析引擎发现与选择','简单文本本地解析','Anydoc 进程内解析','PDF、Office、图片与 XMind','网页、EPUB 与 MHTML','OCR 与外部解析服务','流式解析与图片传输','来源块与坐标定位','解析并发与格式修复'],
  ['internal/infrastructure/docparser/engine_registry.go','docreader/main.py','docreader/parser/parser.py','docreader/proto/docreader.proto']),
 ('datasource','数据源同步','连接器注册表隔离平台实现，数据源服务处理调度、差异、进度与入库，平台接口不应散落在通用知识服务中。','datasource|sync_log|sync_task|connector',
  ['连接器注册与可用资源','飞书、Confluence 与钉钉','GitLab、Notion、语雀与 IMA','RSS 订阅','手动与定时同步','增量差异与删除同步','同步日志、失败与重试'],
  ['internal/datasource/connector.go','internal/application/service/datasource_service.go','internal/datasource/README.md']),
 ('channels','渠道、嵌入与客户端','IM 回调采用平台签名；嵌入页采用发布令牌及 Origin/CSP 约束；SDK、CLI 和小程序复用 API 契约。','internal/im/|internal/handler/im|embed|wecom|telegram|wechat|feishu|slack|dingtalk|qqbot|yunzhijia|mattermost|^cli/|^client/|^miniprogram/|^packages/',
  ['企业微信、飞书与钉钉渠道','Slack、Telegram 与其他 IM','Web 嵌入发布与域名约束','渠道回复语言','Go SDK 与命令行客户端','小程序与集成包'],
  ['internal/im','internal/embedpolicy','internal/router/routes_agent.go','cli/AGENTS.md','client/README.md']),
 ('storage','文件资源与存储','持久资源引用和物理路径分离；下载先解析权限定位器，再由 storage/filetransport 读取并输出。','storage|filetransport|file.go|file_|resource.go|resource_|presign|download',
  ['多存储后端与空间配置','本地及对象存储','资源注册与文件绑定','签名 URL 与预览','Range、HEAD 与下载响应','产物与共享文件授权','删除后的文件清理'],
  ['internal/application/service/file','internal/application/access/files.go','internal/filetransport','internal/storageurl']),
 ('tasks','任务队列与运行治理','Redis/Asynq 与 Lite 执行器共用 TaskEnqueuer。重试、取消、死信、任务作用域和 worker pool 是运行语义的一部分。','task|asynq|worker|dead_letter|pending_ops|scheduler',
  ['解析与后处理任务','Wiki、同步与维护队列','Worker pool 并发配置','任务检查与进度','取消、重试与死信','任务资源作用域','Lite 进程内执行器'],
  ['internal/router/task.go','internal/router/sync_task.go','internal/types/interfaces/task_enqueuer.go','internal/router/task_inspector.go']),
 ('platform','配置、部署与运维','标准服务、Lite 与桌面共用主体源码，通过配置和构建条件改变基础设施。迁移、健康检查与关停均影响运行可靠性。','^cmd/|^config/|^deploy/|^docker/|^helm/|migration|container|runtime|config.go|system_setting|evaluation|tracing|logger|ratelimit|security|ssrf|Makefile|compose|github/workflows',
  ['依赖注入与启动','标准、Lite 与桌面模式','配置与提示词模板','数据库迁移','Docker Compose 与 Helm','健康检查与优雅关停','Langfuse 与日志','系统设置、限流与出站安全','评估任务与结果'],
  ['cmd/server/main.go','internal/container/container.go','internal/database/migration.go','config/config.yaml','.github/workflows/app.yml']),
 ('frontend','前端页面与交互','Vue 页面经 API 适配层访问后端，Pinia 维护共享状态；路由守卫、认证刷新、SSE 和资源缓存需要联合阅读。','^frontend/',
  ['路由与登录守卫','空间切换与请求头','知识管理界面','聊天、工具与引用展示','Agent 编辑与工具箱','Wiki 与产物阅读','终端与桌面面板','国际化、主题与缓存'],
  ['frontend/src/main.ts','frontend/src/router/index.ts','frontend/src/utils/request.ts','frontend/src/stores/auth.ts']),
 ('other','其他基础设施与开发支持','未匹配主业务域的源码、测试、脚本和辅助模块保留在此，避免扫描遗漏被静默隐藏。','.*',
  ['公共类型与错误','工具函数与辅助脚本','测试夹具与第三方适配','文档与开发支持'], ['internal/types','internal/utils','scripts','tests']),
]

def module_for(path):
    # Strong ownership wins before filename keywords; fallback is deliberately visible.
    for mid,_,_,pattern,_,_ in MODULES[:5]:
        if re.search(pattern,path,re.I): return mid
    strong=[('frontend/','frontend'),('internal/agent/tools/','tools'),('internal/modelcontext/','tools'),('internal/agent/skills/','skills'),('internal/sandbox/','sandbox'),('internal/localsandbox/','sandbox'),('internal/browserskill/','browser'),('internal/mcpserver/','mcp'),('internal/mcp/','mcp'),('internal/im/','channels'),('internal/datasource/','datasource'),('internal/application/access/','identity'),('internal/application/service/chat_pipeline/','rag'),('internal/application/repository/retriever/','rag'),('internal/models/','models'),('docreader/','parser'),('internal/infrastructure/docparser/','parser')]
    for prefix, mid in strong:
        if path.startswith(prefix): return mid
    for mid,_,_,pattern,_,_ in MODULES[:-1]:
        if re.search(pattern,path,re.I): return mid
    return 'other'

WORDS={'KnowledgeBase':'知识库','Knowledge':'文档知识','Document':'文档','Chunk':'分块','Session':'会话','Message':'消息','Agent':'智能体','Model':'模型','Tenant':'空间','Organization':'组织','User':'用户','Memory':'记忆','Wiki':'Wiki','Page':'页面','Skill':'技能','Sandbox':'沙箱','Artifact':'产物','File':'文件','Source':'来源','Tag':'标签','Folder':'目录','Question':'问题','DataSource':'数据源','Sync':'同步','Resource':'资源','Member':'成员','Invitation':'邀请','Token':'令牌','Config':'配置','Settings':'设置','History':'历史','Share':'共享','Tool':'工具','Endpoint':'端点','Catalog':'目录','Credentials':'凭证','Provider':'厂商','Event':'事件','Task':'任务','Image':'图片','Summary':'摘要','Role':'角色','Permission':'权限','Topic':'主题','Attachment':'附件','Result':'结果','Storage':'存储','Favorite':'收藏','Evaluation':'评估','Stream':'流','Browser':'浏览器','Graph':'图谱','APIKey':'API 密钥','Key':'密钥','FAQ':'FAQ','MCP':'MCP','URL':'URL','QA':'问答'}
VERBS={'Get':'获取','List':'列出','Create':'创建','Update':'更新','Delete':'删除','Batch':'批量','Search':'搜索','Read':'读取','Write':'写入','Resolve':'解析','Process':'处理','Register':'注册','New':'构造','Set':'设置','Load':'加载','Save':'保存','Clear':'清空','Copy':'复制','Move':'移动','Rename':'重命名','Upload':'上传','Download':'下载','Import':'导入','Export':'导出','Enable':'启用','Disable':'禁用','Install':'安装','Reinstall':'重新安装','Validate':'校验','Check':'检查','Generate':'生成','Parse':'解析','Reparse':'重新解析','Run':'执行','Execute':'执行','Cancel':'取消','Stop':'停止','Retry':'重试','Fork':'分叉','Rewind':'回退','Pin':'置顶','Unpin':'取消置顶','Confirm':'确认','Reject':'拒绝','Join':'加入','Leave':'退出','Accept':'接受','Invite':'邀请','Preview':'预览','Debug':'调试','Enqueue':'入队','Start':'启动','Restore':'恢复','Refresh':'刷新','Promote':'提升','Revoke':'撤销','Record':'记录','Handle':'处理','Build':'构建','Count':'统计','Has':'检查存在','Is':'判断','Find':'查找','Merge':'合并','Normalize':'规范化','Apply':'应用','Detect':'检测','Format':'格式化','Render':'渲染','Ensure':'确保','With':'附加','Require':'要求','Register':'注册','Issue':'签发','Report':'报告','Steer':'引导','Connect':'连接','Disconnect':'断开','Initialize':'初始化','Bind':'绑定','Collect':'收集','Cleanup':'清理','Extract':'提取','Subscribe':'订阅'}

def label(name):
    s=name
    for k,v in sorted({**WORDS,**VERBS}.items(),key=lambda kv:-len(kv[0])): s=s.replace(k,v+'·')
    return s.strip('·')

EXTS={'.go','.py','.ts','.tsx','.js','.mjs','.vue','.sh','.ps1','.sql','.proto','.yaml','.yml','.toml','.json','.md','.mod','.css','.scss','.less','.html','.txt','.rb','.nsi','.plist','.service'}
SKIP={'frontend/package-lock.json','website-docs/package-lock.json','docreader/uv.lock','go.sum'}

def extract_symbols(text,path):
    out=[]; lines=text.splitlines()
    for n,line in enumerate(lines,1):
        match=None; receiver=''; kind='函数'
        if path.endswith('.go'):
            match=re.match(r'^func\s+(?:\(([^)]*)\)\s+)?(\w+)\s*(?:\[[^]]*\])?\(',line)
            if match: receiver=match.group(1) or ''; name=match.group(2)
            else:
                match=re.match(r'^type\s+(\w+)\s+(interface|struct)\b',line)
                if match: name=match.group(1);kind='接口' if match.group(2)=='interface' else '类型'
        elif path.endswith('.py'):
            match=re.match(r'^\s*(?:async\s+)?(def|class)\s+(\w+)\b',line)
            if match: name=match.group(2);kind='类型' if match.group(1)=='class' else '函数'
        else:
            match=re.search(r'^(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(|^(?:export\s+)?(?:const|class|interface|type)\s+(\w+)',line)
            if match: name=match.group(1) or match.group(2);kind='声明'
        if not match: continue
        comments=[];j=n-2
        while j>=0 and len(comments)<16:
            st=lines[j].strip()
            if st.startswith(('//','#','*','/*')): comments.insert(0,st.lstrip('/#* ').rstrip('*/ '));j-=1
            else: break
        out.append({'name':name,'line':n,'kind':kind,'receiver':receiver,'comment':'\n'.join(comments),'signature':line.strip()})
    return out

def parse_routes(path,text):
    routes=[];groups={'r':'/api/v1'};lines=text.splitlines()
    # A bounded lexical index. Source expression stays visible for audit.
    for idx,line in enumerate(lines):
        if line.startswith('func '):
            signature=' '.join(lines[idx:idx+12]).split('{',1)[0]
            groups={'r':'' if re.search(r'r\s+\*gin\.Engine',signature) else '/api/v1'}
        if re.search(r'r\s*:=\s*gin\.(New|Default)\(',line):groups['r']=''
        gm=re.search(r'(\w+)\s*:=.*?(\w+)\.Group\("([^"]*)"',line)
        if gm: groups[gm[1]]=groups.get(gm[2],'/api/v1')+gm[3]
        alias=re.search(r'(\w+)\s*:=\s*(\w+)\.With\(',line)
        if alias and alias[2] in groups: groups[alias[1]]=groups[alias[2]]
        rm=re.search(r'(\w+)\.(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS|Any)\("([^"]*)"\s*,(.*)',line)
        if rm:
            var,method,suffix,rest=rm.groups()
            if 'HandleFunc' in line: continue
            expr=line.strip();handlers=re.findall(r'(\w+)\.(\w+)',rest)
            handler='.'.join(handlers[-1]) if handlers else ''
            comments=[];j=idx-1
            while j>=0 and lines[j].strip().startswith('//'):
                comments.insert(0,lines[j].strip()[2:].strip());j-=1
            routes.append({'method':method,'path':groups.get(var,'')+suffix,'resolved':var in groups,'handler':handler,'source':path,'line':idx+1,'expression':expr,'comment':'\n'.join(comments),'module':route_module(groups.get(var,'')+suffix,path),'guards':re.findall(r'g\.(\w+)\(',rest)})
        # Explicit API-key route wrapper with potentially multiline handler chain.
        wrap=re.search(r'g\.apiKeyRoute\(r,\s*http\.Method(\w+),\s*"([^"]+)"',line)
        if wrap:
            expr=' '.join(lines[idx:idx+4]).split('\n')[0];hm=re.findall(r'(\w+)\.(\w+)',expr)
            candidates=[h for h in hm if h[0] not in ('g','http')]
            routes.append({'method':wrap[1].upper(),'path':'/api/v1'+wrap[2],'resolved':True,'handler':'.'.join(candidates[-1]) if candidates else '', 'source':path,'line':idx+1,'expression':expr,'comment':'','module':route_module(wrap[2],path),'guards':re.findall(r'g\.(\w+)\(',expr)})
    return routes

def route_module(url,path):
    for token,mid in [('background-work','background'),('collaboration','collaboration'),('automation','automation'),('notification','automation'),('gallery','images'),('image-search','images')]:
        if token in url.lower(): return mid
    mapping=[('sandbox','sandbox'),('skill','skills'),('local-browser','browser'),('mcp','mcp'),('wiki','wiki'),('memory','memory'),('knowledge-chat','rag'),('knowledge-search','rag'),('agent-chat','agent'),('agent','agent'),('session','session'),('message','session'),('artifact','session'),('model','models'),('datasource','datasource'),('embed','channels'),('im/','channels'),('auth','identity'),('tenant','identity'),('organization','identity'),('invitation','identity'),('favorite','identity'),('audit','identity'),('storage','storage'),('file','storage'),('task','tasks'),('knowledge','knowledge'),('chunk','knowledge'),('faq','knowledge'),('tag','knowledge'),('initialization','knowledge'),('evaluation','platform')]
    for token,mid in mapping:
        if token in url.lower(): return mid
    return module_for(path)

print('Collecting tracked text sources...',flush=True)
files=[];source_map={};all_tracked=git('ls-files','-z').split('\0');symbols=[];routes=[];excluded=[]
for path in all_tracked:
    if not path or path.startswith(('qishu/','website-docs/homepage/public/','docs/images/')):continue
    p=ROOT/path
    if p.suffix.lower() not in EXTS and p.name not in ('Makefile','Dockerfile','README','LICENSE','VERSION') and not p.name.startswith(('.env','Dockerfile')) and not p.name.endswith('.example'):excluded.append(path);continue
    if path in SKIP:excluded.append(path);continue
    try:
        raw=p.read_bytes()
        if len(raw)>1800000 or b'\0' in raw:excluded.append(path);continue
        content=raw.decode('utf-8')
    except (OSError,UnicodeError):excluded.append(path);continue
    key=hashlib.sha256(path.encode()).hexdigest()[:16]
    syms=extract_symbols(content,path)
    item={'id':key,'path':path,'module':module_for(path),'lines':len(content.splitlines()),'bytes':len(raw),'test':bool(re.search(r'(_test\.go|\.test\.|/tests/|test_[^/]+\.py|/testdata/)',path)),'symbols':syms,'sha256':hashlib.sha256(raw).hexdigest()}
    files.append(item);source_map[path]=item
    for sym in syms: symbols.append({**sym,'zhName':label(sym['name']),'file':path,'module':item['module'],'test':item['test']})
    dump(OUT/'sources'/f'{key}.js', {'path':path,'text':content},'window.SOURCE_CACHE['+json.dumps(key)+']=')
    if path.startswith('internal/router/') and path.endswith('.go') and not item['test']:routes.extend(parse_routes(path,content))

# Swagger annotations are an independent cross-check, not silently merged with guesses.
swagger=[]
for path,item in source_map.items():
    if not path.startswith('internal/handler/') or not path.endswith('.go') or item['test']:continue
    text=(ROOT/path).read_text(encoding='utf-8')
    for n,line in enumerate(text.splitlines(),1):
        m=re.search(r'@Router\s+(\S+)\s+\[(\w+)\]',line)
        if m:swagger.append({'path':m[1],'method':m[2].upper(),'source':path,'line':n})

refs=defaultdict(list);wanted={s['name'] for s in symbols if len(s['name'])>3 and not s['test']}
for path,item in source_map.items():
    if item['test'] or not path.endswith(('.go','.py','.ts','.vue','.mjs')):continue
    text=(ROOT/path).read_text(encoding='utf-8')
    for word in set(re.findall(r'\b[A-Za-z_]\w*\b',text)) & wanted:
        if len(refs[word])<40:refs[word].append(path)

def src(path,name=None):
    candidates=[s for s in symbols if s['file']==path and (not name or s['name']==name)]
    return {'file':path,'line':candidates[0]['line'] if candidates else 1,'symbol':name or ''}

CHAINS=[
 {'id':'startup','title':'01 · 从启动到接收请求','intro':'启动入口装配依赖，然后注册 HTTP 路由和后台任务；退出时先排空 HTTP，再清理资源。','steps':[
  ('cmd/server/main.go','main','设置运行模式，建立 DI 容器，绑定监听器。'),('internal/container/container.go','BuildContainer','通过 dig 注册配置、基础设施、仓储、服务、工具及处理器。'),('internal/config/config.go','LoadConfig','读取部署配置，注意环境变量与配置文件之间的覆盖规则。'),('internal/router/router.go','NewRouter','组装认证、跨域、业务路由与公开端点。'),('internal/router/task.go','RunAsynqServer','标准模式注册后台任务处理器；Lite 对应 RegisterSyncHandlers。'),('cmd/server/main.go','main','接收关停信号，在预算内排空请求并释放资源。')]},
 {'id':'ingest','title':'02 · 一份文档如何成为可检索知识','intro':'HTTP 上传只是入库的开始。任务携带目标资源，解析、切分、存储与索引在后台完成。','steps':[
  ('internal/application/service/knowledge_create.go','CreateKnowledgeFromFile','验证知识库与存储配置，保存文件和知识记录。'),('internal/application/service/knowledge_create.go','CreateKnowledgeFromFile','构造 TypeDocumentProcess 并通过 TaskEnqueuer 入队。'),('internal/router/task.go','RunAsynqServer','将文档任务分派给 KnowledgeService.ProcessDocument。'),('internal/application/service/knowledge_process.go','ProcessDocument','加载任务目标、检查状态和作用域，执行本次解析。'),('internal/infrastructure/docparser/engine_registry.go','NewReader','显式本地引擎、简单格式或远程 docreader 之间选择。'),('docreader/main.py','DocReaderServicer','远程路径解析文本、图片和来源块，Go 侧负责图片持久化。'),('internal/application/service/knowledge_process.go',None,'建立父子分块与索引，BatchIndex 写入检索引擎。'),('internal/application/service/knowledge_process.go','enqueueKnowledgePostProcessTask','继续摘要、问题和 Wiki 等按配置启用的后处理。')]},
 {'id':'rag','title':'03 · 用户提问到带引用的回答','intro':'有效检索范围决定 RAG 或纯聊天。以下展示 RAG 主路径，历史、Web 和数据分析为条件阶段。','steps':[
  ('internal/router/routes_chat.go','RegisterChatRoutes','POST /api/v1/knowledge-chat/:session_id，先通过角色与 API Key 能力检查。'),('internal/handler/session/qa.go','KnowledgeQA','解析请求，检查会话归属、Agent/知识选择与附件。'),('internal/application/service/session_knowledge_qa.go','KnowledgeQA','生成 ChatManage 并按有效范围组装 PipelineBuilder。'),('internal/application/service/chat_pipeline/query_understand.go',None,'查询理解，为检索建立查询意图。'),('internal/application/service/chat_pipeline/search_parallel.go',None,'并行检索知识来源；共享范围必须在检索及结果消费时维护。'),('internal/application/service/chat_pipeline/rerank.go',None,'重排候选结果，随后合并与 FilterTopK。'),('internal/application/service/chat_pipeline/into_chat_message.go',None,'把结果、历史和附件转换成模型上下文。'),('internal/application/service/chat_pipeline/chat_completion_stream.go',None,'流式生成并还原引用，经会话输出链路送达前端。')]},
 {'id':'agent','title':'04 · Agent 一轮工具执行','intro':'工具列表不是目录中的全部工具，而是配置、权限、知识能力和运行环境过滤后的本次可用集合。','steps':[
  ('internal/handler/session/qa.go','AgentQA','验证请求和共享 Agent 权限，持有会话执行资源。'),('internal/application/service/session_agent_qa.go','AgentQA','装配模型、历史、知识范围与事件总线。'),('internal/application/service/agent_service.go','CreateAgentEngine','构建工具表，接入 MCP、沙箱、技能和浏览器。'),('internal/application/service/agent_service.go','registerTools','归一化工具白名单，依据向量/图谱/Wiki 能力与开关过滤。'),('internal/agent/engine.go','Execute','构造系统提示词和上下文，开始 ReAct 循环。'),('internal/modelcontext/registry.go',None,'模型调用前编码，工具执行前还原临时句柄。'),('internal/agent/act.go',None,'执行工具并收集结果；观察结果后继续迭代或输出最终答案。'),('internal/application/service/artifact_collector.go',None,'根据执行结果收集生成文件，绑定到消息产物。')]},
 {'id':'sharing','title':'05 · 共享知识的授权与执行','intro':'调用者和资源拥有者可能属于不同空间。必须先得到精确资源授权，再切换执行上下文。','steps':[
  ('internal/middleware/auth.go',None,'认证创建调用者身份，不从资源的 tenant_id 推断调用者。'),('internal/router/rbac.go',None,'角色、创建者和 API Key 能力共同控制 HTTP 入场。'),('internal/application/access/knowledgebase.go','ResolveKB','解析本空间、组织共享或只读共享 Agent 的知识访问。'),('internal/application/access/context.go',None,'携带绑定 KB、资源拥有空间和调用者的权限授予。'),('internal/application/access/files.go',None,'文件另需精确的持久资源绑定；知识可读不意味着任意路径可读。'),('internal/filetransport',None,'经授权定位器打开文件并提供流式、Range 或下载响应。')]},
 {'id':'wiki','title':'06 · 文档到 Wiki 的异步组织','intro':'页面生成、引用维护和删除撤回通过 Wiki 任务协调。重试与幂等关系决定一致性。','steps':[
  ('internal/application/service/wiki_ingest.go','EnqueueWikiIngest','持久化待处理操作并触发 Wiki 入库任务。'),('internal/application/service/wiki_ingest_batch.go',None,'按知识库组织批量处理。'),('internal/application/service/wiki_ingest_taxonomy.go',None,'处理页面分类和目录。'),('internal/application/service/wiki_ingest_cite.go',None,'处理源文档引用及引用解析。'),('internal/application/service/wiki_page.go',None,'持久化页面并维护修订。'),('internal/application/service/wiki_ingest.go','EnqueueWikiRetract','源文档删除时排入撤回操作，清理关联知识。')]}
]
CHAINS.extend([
 {'id':'assistant','title':'07 · 内置助手如何调用业务操作','intro':'助手先发现目录中的操作，再按调用者角色和有效访问等级分派；目录参数不是额外的权限。','steps':[
  ('internal/types/assistant.go','EffectiveAccessLevel','把请求的访问等级限制在工作空间允许的上限内。'),('internal/agent/operations/catalog.go',None,'建立可发现的操作目录和参数描述。'),('internal/agent/tools/operations.go','Execute','find_operations 与 run_operation 使用目录发现和执行操作；同名 Execute 需核对 receiver。'),('internal/agent/approval/grants.go','WithGrants','按运行或会话作用域复用已记住的批准，失效时重新确认。'),('internal/router/operations.go',None,'把操作接回现有处理器，业务授权继续生效。')]},
 {'id':'collaboration','title':'08 · 子智能体从委派到交付','intro':'持久协作由 runtime 调度，不等于在模型输出中声明一个子任务。','steps':[
  ('internal/agent/tools/collaboration.go',None,'把委派、消息、等待和中断请求交给协作 binding。'),('internal/agent/collaboration/runtime.go','Spawn','登记组内任务和成员，保留幂等键与资源范围。'),('internal/agent/collaboration/runtime.go','Tick','领取待执行任务，续租与恢复在 runtime 内处理。'),('internal/application/service/agent_collaboration.go',None,'在服务层装配子执行模型、继承范围和工具能力。'),('internal/agent/collaboration.go','appendCollaborationEvents','把持久事件封装为带标签的数据，避免冒充人类指令。')]},
 {'id':'automation','title':'09 · 定时任务如何变成一次 Agent 运行','intro':'HTTP 管理、数据库领取与 Agent 执行分别负责配置、调度和实际操作。','steps':[
  ('internal/router/routes_automation.go','RegisterAutomationRoutes','注册任务、运行记录、授权与通知接口。'),('internal/automation/trigger.go',None,'验证触发器、时间与时区。'),('internal/application/service/automation_scheduler.go','Start','周期检查到期任务；数据库条件更新负责竞争领取。'),('internal/application/service/automation_runner.go','execute','重新核对拥有者与授权，运行到完成、失败或等待人工处理。'),('internal/application/service/automation.go',None,'持久化任务及运行结果，供历史和通知读取。')]},
 {'id':'background','title':'10 · Shell 后台执行与结果回流','intro':'统一后台活动契约让 Shell 任务和 Agent 共享状态、取消及通知语义。','steps':[
  ('internal/types/interfaces/background.go',None,'阅读 ActivityRegistry 与 NoticeInbox 契约。'),('internal/application/service/shell_job_service.go',None,'启动和管理异步 Shell 作业。'),('internal/application/service/background_work.go','NewBackgroundWork','把活动登记与结果收件箱连接到服务层。'),('internal/agent/background.go','injectBackground','把新通知注入 Agent 上下文，并维护已见状态。'),('internal/handler/session/background_http.go',None,'向前端提供会话内后台工作查询与取消。')]}
])
chains=[]
for c in CHAINS:
    chains.append({**c,'steps':[{'title':name or Path(path).name,'note':note,**src(path,name)} for path,name,note in c['steps']]})

EXTENSIONS=[
 {'title':'内置工具扩展','tag':'最接近业务代码','body':'先在 internal/types/agent.go 核对 Tool 接口；在 internal/agent/tools 实现 Name、Description、Parameters 和 Execute。工具经 ToolRegistry 注册，重复名称采用 first-wins。再在 agent_service.registerTools 中加入能力前提与可用范围，检查默认工具和预设，以及前端 Agent 编辑器的工具分类。','files':['internal/types/agent.go','internal/agent/tools/registry.go','internal/application/service/agent_service.go','config/agent_type_presets.yaml'],'checks':['参数非法、无权限及空结果的行为','共享 Agent 只读及 Wiki 写权限','工具名、默认列表与前端选项一致','工具输出限制与模型句柄解码']},
 {'title':'MCP 扩展','tag':'连接外部工具服务','body':'MCP 客户端由 internal/mcp 管理连接和 OAuth；Agent 服务注册已启用服务，ToolRegistry.PrepareMCPTools 准备按需发现。外部工具的任意 id/url 字段不应被猜测为应用持久身份。内置 MCP Server 则是向外发布知识，入口与客户端扩展不同。','files':['internal/mcp','internal/mcpserver','internal/agent/tools/registry.go','internal/modelcontext/mcp.go'],'checks':['启用服务、工具筛选和审批策略','OAuth 刷新和连接失败','动态参数保持不透明','端点知识范围与速率限制']},
 {'title':'Skill 扩展','tag':'说明文件 + 执行环境','body':'Skill 不仅是提示词。loader 读取 SKILL.md/frontmatter，tenant_source 提供空间安装来源，manager 组织可用技能。安装写入技能镜像的流程与会话读取/执行流程不同；只有安装就绪且运行环境可用时才应向模型提供技能。','files':['internal/agent/skills/skill.go','internal/agent/skills/loader.go','internal/agent/skills/manager.go','internal/agent/skills/tenant_source.go','internal/application/service/agent_service.go'],'checks':['元数据、路径与嵌套目录','安装状态和失败后的可见性','依赖、环境变量及网络策略','会话持久化与文件权限']},
 {'title':'沙箱后端扩展','tag':'执行能力适配','body':'先核对 sandbox.Manager 与租户 resolver 的已有契约，再按命名配置接入后端。会话工作目录、文件原语、终端/桌面和快照支持不能默认存在，应依据实际能力暴露。Lite 主机后端有独立的启用条件和审批边界。','files':['internal/sandbox/manager.go','internal/sandbox/tenant_resolver.go','internal/sandbox/session_manager.go','internal/agent/approval/gate.go'],'checks':['会话绑定、资源回收与超时','文件路径和环境隔离','终端/桌面票据及所有权','fork/rewind 的快照与失败恢复']},
 {'title':'浏览器扩展与工具呈现','tag':'用户已有浏览器','body':'BrowserSkill 连接能力经 agent_service 注册浏览器工具；session handler 负责连接查询和会话相关操作。改动应同时审视后端配对/连接、工具策略、前端连接状态与事件展示，不要把浏览器会话当成沙箱桌面。','files':['internal/browserskill','internal/agent/tools/browserskill.go','internal/handler/session/browserskill.go','frontend/src/stores/browserConnection.ts'],'checks':['配对来源和会话作用域','断线、取消与暂停','前端工具事件展示','用户接管后恢复执行']},
 {'title':'模型与上下文扩展','tag':'协议与证据边界','body':'模型厂商应接入现有 providers/catalog/runtime，而不是在业务服务中直接新增 HTTP 接口。模型调用中的短句柄由 Registry 统一编解码；工具来源可寻址和当前引用可用是不同状态。Langfuse 观察边界，不能再实现另一套句柄表。','files':['internal/models','internal/modelcontext/README.md','internal/modelcontext/registry.go','internal/modelcontext/tool_policy.go'],'checks':['目录生成与协议行为校验','完整及流式响应解码','未解析句柄在执行前拒绝','引用依据属于当前执行']}
]

EXTENSIONS.extend([
 {'title':'操作目录与内置助手','tag':'复用既有 HTTP 业务','body':'在 operations.Catalog 注册实际业务操作，再通过 find_operations/run_operation 暴露；助手访问等级只缩小角色能力。写操作需要声明确认与破坏性语义，最终沿用现有 handler/service 授权，不直接给模型数据库入口。','files':['internal/agent/operations/catalog.go','internal/agent/operations/spec.go','internal/agent/tools/operations.go','internal/router/operations.go'],'checks':['只读角色与空间上限','参数投影与目标身份','确认前后目标变化','执行后页面刷新及数据变更事件']},
 {'title':'统一权限、批准与 HITL','tag':'运行模式与持久交互','body':'运行模式、策略、批准存储和 HITL broker 共同决定一次工具调用能否执行。复用 session/run grant 的作用域与有效性检查；持久提示的答复、取消和恢复需经过 broker，不能仅凭模型消息视为已批准。','files':['internal/types/run_mode.go','internal/agent/policy','internal/agent/approval/grants.go','internal/agent/hitl/broker.go'],'checks':['角色上限与批准继承','授权撤销和过期','重启后的待答提示','无人值守运行遇到确认时的停留状态']},
 {'title':'多智能体协作','tag':'持久任务与租约','body':'协作 runtime 管理 Spawn、Send、Wait 与 Interrupt，service 装配子执行的范围和能力。子消息以 agent_message/runtime_event 进入父上下文，仍属于数据。新增协作能力要维护组内身份、持久事件游标、租约恢复及交付边界。','files':['internal/agent/collaboration/runtime.go','internal/agent/collaboration/store.go','internal/application/service/agent_collaboration.go','internal/agent/collaboration.go'],'checks':['重复委派和任务幂等','父子权限及 MCP 能力继承','租约超时与重启恢复','消息转义、停止与结果交付']},
 {'title':'定时任务与后台活动','tag':'后台不绕过权限','body':'Automation 负责时间触发和持久运行，BackgroundWork 统一活动与通知。新增触发器先复用 trigger 校验；新增后台执行器复用 ActivityRegistry/NoticeInbox。每轮重新验证拥有者与运行授权，不把曾经成功的运行当成永久许可。','files':['internal/automation/trigger.go','internal/application/service/automation_scheduler.go','internal/application/service/automation_runner.go','internal/types/interfaces/background.go'],'checks':['时区和触发边界','多实例重复领取','账号停用与授权变化','运行取消、通知已读及关闭回收']}
])

print('Collecting all reachable commits and file-level deltas...',flush=True)
raw=git('log','--date-order','--format=%x1e%H%x1f%P%x1f%aI%x1f%cI%x1f%an%x1f%s%x1f%b%x1d','--numstat','--no-renames','HEAD')
commits=[]
TYPE_ZH={'fix':'修复','feat':'功能新增','docs':'文档更新','refactor':'重构','perf':'性能优化','test':'测试调整','chore':'维护','build':'构建调整','ci':'持续集成','style':'格式调整','revert':'回退','merge':'合并'}
PHRASES={'upgrade':'升级','update':'更新','add':'增加','support':'支持','fix':'修复','remove':'移除','refactor':'重构','improve':'改进','prevent':'防止','avoid':'避免','ensure':'确保','handle':'处理','implement':'实现','enable':'启用','disable':'禁用','restore':'恢复','resolve':'解析/解决','cleanup':'清理','clean up':'清理','optimize':'优化','correct':'纠正','use':'使用','switch':'切换','replace':'替换','migrate':'迁移','rename':'重命名','reduce':'减少','limit':'限制','sanitize':'清理校验','validate':'校验','preserve':'保留','align':'对齐','expose':'开放','allow':'允许','reject':'拒绝','guard':'保护','wire':'接入','routing':'路由','streaming':'流式输出','stream':'流','authentication':'认证','authorization':'授权','permission':'权限','permissions':'权限','knowledge base':'知识库','knowledge':'知识','document':'文档','documents':'文档','chunk':'分块','chunks':'分块','session':'会话','sessions':'会话','agent':'智能体','agents':'智能体','model':'模型','models':'模型','tool':'工具','tools':'工具','sandbox':'沙箱','browser':'浏览器','memory':'记忆','history':'历史','output':'输出','input':'输入','token':'令牌','tokens':'令牌','embedding':'向量化','retrieval':'检索','search':'搜索','file':'文件','files':'文件','upload':'上传','download':'下载','image':'图片','images':'图片','config':'配置','configuration':'配置','cache':'缓存','error':'错误','errors':'错误','timeout':'超时','retry':'重试','retries':'重试','database':'数据库','storage':'存储','tenant':'空间','workspace':'工作空间','shared':'共享','scope':'范围','scoped':'限定范围','frontend':'前端','backend':'后端','api':'API','test':'测试','tests':'测试','read':'读取','write':'写入','delete':'删除','parser':'解析器','parsing':'解析','sources':'来源','source':'来源','citation':'引用','citations':'引用','metadata':'元数据','index':'索引','queue':'队列','task':'任务','tasks':'任务','worker':'工作进程','concurrency':'并发','batch':'批量','page':'页面','pages':'页面','prompt':'提示词','prompts':'提示词','security':'安全','network':'网络','endpoint':'端点','response':'响应','request':'请求','button':'按钮','display':'显示','handling':'处理','behavior':'行为','failed':'失败','failure':'失败','default':'默认','missing':'缺失','empty':'空值','invalid':'无效','stale':'过期','duplicate':'重复','local':'本地','remote':'远程','boundary':'边界','boundaries':'边界','leak':'泄露','leaks':'泄露','credentials':'凭证','OAuth':'OAuth','anydoc':'Anydoc','login':'登录','logout':'登出','refresh':'刷新','language':'语言','locale':'区域语言','i18n':'国际化','deployment':'部署','build':'构建','docker':'Docker','release':'发布','lint':'静态检查','format':'格式','version':'版本','settings':'设置','connection':'连接','cancel':'取消','cleanup':'清理','fork':'分叉','rewind':'回退','steer':'引导','artifacts':'产物','artifact':'产物','enablement':'启用条件'}
PHRASES.update({'assistant':'内置助手','collaboration':'协作','durable':'持久化','background':'后台','automation':'定时任务','automations':'定时任务','notification':'通知','notifications':'通知','grant':'授权记录','grants':'授权记录','permission model':'权限模型','run modes':'运行模式','human-in-the-loop':'人工介入','multi-agent':'多智能体','multi-KB':'多知识库','embedding dimensions':'向量维度','event loop':'事件循环','offload':'移出','metadata lookups':'元数据查询','sign-in form':'登录表单','reclaim':'回收','memory':'内存/记忆','multipart uploads':'分段上传','skip conflict strategy':'跳过冲突策略'})

def chinese_gloss(subject):
    text=re.sub(r'^\w+(?:\([^)]*\))?!?:\s*','',subject)
    if re.search(r'[\u4e00-\u9fff]',text):return text,'提交原文含中文'
    # Reviewable phrase overrides improve recurring title syntax without
    # pretending that lexical replacement is a full historical translation.
    for phrase,zh in {'parse assets once':'一次性解析附件资源',' to ':' 至 ',' and ':' 并 '}.items():
        text=re.sub(re.escape(phrase),zh,text,flags=re.I)
    for word,zh in sorted(PHRASES.items(),key=lambda kv:-len(kv[0])):
        text=re.sub(r'(?<![\w])'+re.escape(word)+r'(?![\w])',zh,text,flags=re.I)
    return text,'术语译解（自动，原文为准）'
for record in raw.split('\x1e')[1:]:
    if '\x1d' not in record:continue
    header,stat=record.split('\x1d',1);parts=header.split('\x1f',6)
    if len(parts)!=7:continue
    sha,parents,authored,committed,author,subject,body=parts
    changes=[]
    for line in stat.splitlines():
        m=re.match(r'^(\d+|-)\t(\d+|-)\t(.+)$',line)
        if m:changes.append({'path':m[3],'added':None if m[1]=='-' else int(m[1]),'removed':None if m[2]=='-' else int(m[2]),'module':module_for(m[3])})
    m=re.match(r'^(\w+)(?:\(([^)]*)\))?!?:',subject);kind=m[1].lower() if m else ('merge' if subject.startswith('Merge') else 'chore')
    gloss,level=chinese_gloss(subject)
    domains=Counter(c['module'] for c in changes).most_common(3);names={x[0]:x[1] for x in MODULES}
    summary=f"本次属于{TYPE_ZH.get(kind,'代码调整')}；"+('主要涉及'+ '、'.join(names[k] for k,_ in domains)+'。' if domains else '该提交未显示文件级行数差异（合并提交不代表无改动）。')
    commits.append({'sha':sha,'parents':parents.split(),'date':committed,'authorDate':authored,'author':author,'subject':subject,'body':body.strip(),'kind':kind,'scope':m[2] if m else '', 'zh':gloss,'translation':level,'summary':summary,'changes':changes,'added':sum(c['added'] or 0 for c in changes),'removed':sum(c['removed'] or 0 for c in changes)})
commits.sort(key=lambda c:c['date'],reverse=True)

modules=[]
topic_notes=json.loads((OUT/'topic_notes.json').read_text(encoding='utf-8'))
for mid,title,description,pattern,features,entry in MODULES:
    members=[f for f in files if f['module']==mid]
    assert len(topic_notes[mid])==len(features),(mid,len(topic_notes[mid]),len(features))
    modules.append({'id':mid,'title':title,'description':description,'features':features,'featureNotes':topic_notes[mid],'entry':[src(p) for p in entry if p in source_map or any(f['path'].startswith(p+'/') for f in files)],'files':len(members),'tests':sum(f['test'] for f in members),'routes':sum(r['module']==mid for r in routes)})

revision=git('rev-parse','HEAD').strip()
data={'meta':{'revision':revision,'branch':git('branch','--show-current').strip(),'built':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec='seconds'),'fileCount':len(files),'trackedCount':sum(bool(p) for p in all_tracked),'symbolCount':len(symbols),'routeCount':len(routes),'swaggerCount':len(swagger),'commitCount':len(commits),'testCount':sum(f['test'] for f in files),'sourceBytes':sum(f['bytes'] for f in files),'excluded':excluded,'methodology':'源码快照与词法扫描，不是编译器调用图；业务导航为人工组织，路由、声明、注释与提交差异为自动索引。'},'modules':modules,'files':files,'routes':routes,'swagger':swagger,'symbols':symbols,'references':refs,'chains':chains,'extensions':EXTENSIONS}
dump(OUT/'data.js',data)
dump(OUT/'history.js',commits,'window.HISTORY=')
manifest={'revision':revision,'files':[{k:f[k] for k in ('id','path','sha256','bytes','lines')} for f in files],'counts':data['meta']}
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(data['meta'],ensure_ascii=False,indent=2)[:1100],flush=True)
