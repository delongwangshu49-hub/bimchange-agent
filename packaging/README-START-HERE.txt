BIMChange-Agent 1.0.0 — Windows x64 / 正式版
=================================================

Distribution status / 分发状态
-----------------------------
If a NOT-FOR-DISTRIBUTION notice accompanies this directory, it is a local
validation build only. Application version 1.0.0 does not itself authorize
public redistribution. Follow the release checklist before sharing binaries.
若本目录附带 NOT-FOR-DISTRIBUTION 声明，则仅为本地验证包。
应用版本 1.0.0 本身不代表已获公开分发许可；分享二进制前须通过发布清单。

Getting started / 开始使用
--------------------------
1. Extract the entire portable ZIP before running BIMChange-Agent.exe.
   将便携 ZIP 完整解压后运行 BIMChange-Agent.exe。
2. Select or drop the previous IFC and revised IFC, then start analysis.
   选择或拖入旧版与新版 IFC，然后开始分析。
3. Keep AI off for local-only comparison and 3D review.
   保持 AI 关闭即可完全本地比较并查看三维。
4. Filter records, inspect evidence, select Spatial context to locate the
   actual colored mesh; use focus, fit context, orbit/pan/zoom and fading.
   筛选记录、查看证据，在“局部三维”查看构件原形着色；
   支持定位构件、查看周围、旋转/平移/缩放和周围淡化。
5. Export JSON or standalone HTML when needed; HTML contains the report,
   not the interactive 3D scene. Check project-derived data before sharing.
   按需导出 JSON 或独立 HTML；HTML 为报告，不包含交互三维。
   分享前检查项目派生数据。

Support / 支持边界
-------------------
Exact IFC4; <=50 MiB per file; <=5,000 IfcElement per revision;
>=50% shared GlobalIds on the smaller side.
仅精确 IFC4；单文件 <=50 MiB；每版 <=5,000 个构件；
较小一侧 GlobalId 重合率 >=50%。

Addition/deletion/property values, controlled translation, rectangular
extrusion dimensions, topology-preserving tessellation, four direct
relationship families. No arbitrary geometry-diff or IFC2X3 claim.
新增/删除/属性值、受控平移、矩形拉伸尺寸、拓扑不变网格及四类直接关系；
不承诺任意几何差分或 IFC2X3 支持。

3D: one target plus at most two unchanged neighbors, same direct storey,
within 6 m. Missing or ambiguous geometry/context is unavailable.
Black XY grid is a visual reference, not building axes or an actual floor.
三维：一个目标及同一直接楼层、6 米内最多两个未变化邻居。
缺失或歧义几何/上下文会提示不可用。黑底 XY 网格是视觉参考，
不是建筑轴网或实际楼板。不存在完整 BIM 查看器或 Revit 集成。

AI and privacy / AI 与隐私
--------------------------
AI is optional, off by default: DeepSeek, OpenAI, Anthropic, Google Gemini.
Enabled AI receives up to 200 normalized records plus counts; values may
include project identifiers, storeys, properties and geometry coordinates.
IFC/GLB files and input file names/paths are not uploaded.
The API key goes to the provider for authentication, not into the model
prompt or reports; it remains only in application session memory.
AI errors do not invalidate the local deterministic report.
AI 可选且默认关闭，支持四类服务商；开启后发送最多 200 条规范化记录
及汇总，可能含项目标识、楼层、属性和坐标。不上传 IFC/GLB 和输入
文件名/路径。API Key 用于服务商认证，不放入模型提示或报告，
应用仅在当前会话内存保留。AI 失败不影响本地确定性报告。

Working reports use LocalAppData. 3D uses temporary local meshes and a
session-restricted loopback server. Normal close cleans its session;
crashes may leave temporary files. Export only to the path you choose.
工作报告保存在 LocalAppData；三维使用临时网格与会话受限回环服务。
正常关闭清理会话，崩溃可能残留临时文件。导出写入用户所选路径。

Unsigned builds may trigger SmartScreen. Download published builds only
from the official project and verify SHA-256. Do not upload private IFC,
keys or unredacted reports to public issues.
未签名构建可能触发 SmartScreen。仅从官方项目下载公开构建并核对
SHA-256；请勿公开上传私人 IFC、密钥或未经脱敏的报告。

Project: https://github.com/delongwangshu49-hub/bimchange-agent
Related project by the same author / 同作者相关项目:
https://github.com/delongwangshu49-hub/ifc-clashtrace
