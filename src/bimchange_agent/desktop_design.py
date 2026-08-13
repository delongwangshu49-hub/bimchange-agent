"""Desktop localization and theme tokens for the product shell."""

from __future__ import annotations

from pathlib import Path
from typing import Any


SUPPORTED_LANGUAGES = ("zh_CN", "en")
SUPPORTED_THEMES = ("system", "light", "dark")


TEXT: dict[str, dict[str, str]] = {
    "zh_CN": {
        "window_title": "{app} — {version}",
        "product_descriptor": "确定性 IFC 版本审阅",
        "settings": "设置",
        "ai_toggle": "AI 解读",
        "ai_state_off": "AI 关闭 · 仅本地",
        "ai_state_on": "AI 开启 · 将发送受限记录",
        "step_select": "01  选择文件",
        "step_analyse": "02  分析变更",
        "step_review": "03  审阅报告",
        "home_eyebrow": "IFC REVISION REVIEW",
        "home_title": "比较两个 IFC 版本",
        "home_subtitle": "在本地生成可追溯的变更记录，并将每项结论回链到构件证据。",
        "preview_note": "工程预览 · 确定性结果优先 · AI 默认关闭",
        "source_title": "旧版本 IFC",
        "source_subtitle": "选择基线模型，或将 .ifc 文件拖到此处",
        "revised_title": "新版本 IFC",
        "revised_subtitle": "选择修订模型，或将 .ifc 文件拖到此处",
        "select_ifc": "选择 IFC 文件",
        "replace_ifc": "更换文件",
        "boundary": "支持边界：IFC4 · 单文件 ≤ 50 MiB · 每版 ≤ 5,000 个构件",
        "privacy_note": "IFC 比较在本机完成。启用 AI 时仅发送受限的规范化 Change Records。",
        "start_analysis": "开始分析",
        "report_eyebrow": "REVIEW WORKSPACE",
        "report_title": "变更审阅报告",
        "new_analysis": "新建比较",
        "metric_total": "受支持变更",
        "metric_added": "新增",
        "metric_deleted": "删除",
        "metric_modified": "属性修改",
        "metric_unsupported": "未支持",
        "filter_search": "搜索 GlobalId、实体、字段或值",
        "filter_all_types": "全部变更类型",
        "filter_all_entities": "全部实体类型",
        "filter_all_storeys": "全部楼层",
        "change_added": "新增",
        "change_deleted": "删除",
        "change_property_modified": "属性修改",
        "change_unsupported": "未支持",
        "results_count": "显示 {visible} / {total} 项变更",
        "table_type": "类型",
        "table_entity": "实体",
        "table_guid": "GlobalId",
        "table_storey": "楼层",
        "table_field": "字段",
        "table_old": "旧值",
        "table_new": "新值",
        "detail_title": "变更详情",
        "detail_empty": "选择表格中的一项变更以查看完整证据。",
        "detail_change": "变更类型",
        "detail_entity": "实体类型",
        "detail_guid": "GlobalId",
        "detail_storey": "楼层",
        "detail_field": "字段",
        "detail_old": "旧值",
        "detail_new": "新值",
        "detail_evidence": "证据位置",
        "ai_output_title": "AI 解读",
        "ai_disabled_report": "本次分析未启用 AI。确定性差分报告仍然完整可用。",
        "ai_generated_by": "由 {provider} · {model} 生成",
        "ai_summary_heading": "自然语言摘要",
        "ai_rational_heading": "简短理性分析",
        "ai_key_changes_heading": "重点变更",
        "ai_limitations_heading": "证据限制",
        "ai_no_key_changes": "没有可列出的重点变更。",
        "ai_no_limitations": "模型未补充其他限制；仍须遵守以下免责声明。",
        "ai_rational_unavailable": "AI 解读未成功生成，无法形成基于模型输出的理性分析。",
        "ai_disclaimer": "免责声明：AI 内容仅用于辅助阅读；确定性 Change Records 与原始证据才是权威数据源。本内容不能替代专业 BIM 协调、工程审查或结构安全评估。",
        "export_json": "导出 JSON",
        "export_html": "导出 HTML",
        "open_folder": "打开报告文件夹",
        "analysing": "正在分析…",
        "progress_compare": "正在检查并比较 IFC 文件…",
        "progress_ai": "确定性差分完成，正在请求 AI 解读…",
        "progress_report": "正在生成 HTML 报告…",
        "settings_title": "设置",
        "settings_general_tab": "常规",
        "settings_ai_tab": "AI",
        "appearance_title": "外观与语言",
        "theme": "主题",
        "theme_system": "跟随系统",
        "theme_light": "浅色",
        "theme_dark": "深色",
        "language": "界面语言",
        "language_zh": "简体中文",
        "language_en": "English",
        "settings_restart_note": "主题和语言保存后立即生效。",
        "ai_settings_title": "AI 服务商",
        "ai_enabled": "启用 AI 解读",
        "provider": "服务商",
        "planned": "计划支持",
        "base_url": "API Base URL",
        "model": "模型",
        "api_key": "API Key",
        "api_key_placeholder": "仅保存在本次运行内存中",
        "ai_privacy_note": "API Key 不会持久化。IFC 文件、绝对路径和文件名不会发送给服务商；规范化记录仍可能包含构件、楼层和属性信息。",
        "save": "保存",
        "cancel": "取消",
        "file_dialog": "选择 IFC 文件",
        "file_selection_failed": "文件选择失败",
        "drop_failed": "拖拽文件失败",
        "invalid_ifc": "请选择有效的 .ifc 文件",
        "settings_invalid": "设置无效",
        "ai_fields_required": "启用 AI 时必须填写模型和 API Key。",
        "analysis_running": "分析进行中",
        "analysis_running_body": "请等待当前分析完成。",
        "missing_files": "缺少文件",
        "missing_files_body": "请先选择旧版和新版 IFC 文件。",
        "same_file": "文件相同",
        "same_file_body": "旧版和新版选择了同一个文件。请分别选择两个 IFC 版本。",
        "missing_key": "缺少 API Key",
        "missing_key_body": "请先在设置中填写 API Key，或关闭主界面的 AI 解读开关。",
        "analysis_failed": "分析失败",
        "ai_failed": "AI 解读失败",
        "ai_failed_body": "本地确定性差分与报告已经完成，但 AI 解读未生成。请检查网络和设置后重新分析。",
        "ai_failed_reason": "本地确定性报告已完成。AI 解读失败：{reason}",
        "ai_error_configuration": "{provider} 设置无效。请检查模型、服务商和 API Key。",
        "ai_error_authentication": "{provider} 拒绝认证（HTTP {status}）。请检查 API Key 是否有效，并确认它有权访问所选模型。",
        "ai_error_endpoint_or_model": "{provider} 找不到端点或模型（HTTP {status}）。请恢复官方端点并检查模型名称。",
        "ai_error_rate_limit": "{provider} 达到速率或额度限制（HTTP {status}）。请稍后重试并检查账户额度。",
        "ai_error_provider_unavailable": "{provider} 服务暂时不可用（HTTP {status}）。本地报告不受影响，请稍后重试。",
        "ai_error_http_error": "{provider} 请求失败（HTTP {status}）。请检查服务商设置和所选模型。",
        "ai_error_network": "无法连接 {provider}。请检查网络、代理和防火墙。",
        "ai_error_timeout": "{provider} 在超时前没有返回结果。请稍后重试。",
        "ai_error_invalid_json": "{provider} 返回的内容不是有效 JSON。请重试或更换模型。",
        "ai_error_provider_response": "{provider} 返回了无法识别的响应结构。请确认模型支持结构化输出。",
        "export_unavailable": "无法导出",
        "export_unavailable_body": "当前没有可导出的报告文件。",
        "same_export": "无需导出",
        "same_export_body": "目标位置就是当前报告文件。",
        "export_failed": "导出失败",
        "export_json_title": "导出 JSON",
        "export_html_title": "导出 HTML",
        "open_failed": "无法打开文件夹",
        "open_failed_body": "系统未能打开本次报告目录。",
        "no_report_folder": "当前还没有生成报告。",
        "unexpected_title": "软件发生错误",
        "close_running": "请等待当前分析完成后再关闭软件。",
        "friendly_os_error": "无法读取输入文件或写入本地报告目录。请检查文件权限、磁盘空间，并确认文件未被其他程序锁定。",
        "friendly_format_error": "输入或分析产物格式无效：{error}",
        "friendly_unexpected": "发生未预期错误（{name}）。请重试；若问题持续，请在 GitHub Issues 反馈输入文件格式、大小和复现步骤，勿上传敏感模型。",
    },
    "en": {
        "window_title": "{app} — {version}",
        "product_descriptor": "Deterministic IFC revision review",
        "settings": "Settings",
        "ai_toggle": "AI explanation",
        "ai_state_off": "AI off · local only",
        "ai_state_on": "AI on · bounded records sent",
        "step_select": "01  Select files",
        "step_analyse": "02  Analyse changes",
        "step_review": "03  Review report",
        "home_eyebrow": "IFC REVISION REVIEW",
        "home_title": "Compare two IFC versions",
        "home_subtitle": "Create traceable local change records and link every conclusion to element evidence.",
        "preview_note": "Engineering preview · deterministic results first · AI off by default",
        "source_title": "Previous IFC",
        "source_subtitle": "Choose the baseline model or drop an .ifc file here",
        "revised_title": "Revised IFC",
        "revised_subtitle": "Choose the revised model or drop an .ifc file here",
        "select_ifc": "Choose IFC file",
        "replace_ifc": "Replace file",
        "boundary": "Supported boundary: IFC4 · ≤ 50 MiB per file · ≤ 5,000 elements per version",
        "privacy_note": "IFC comparison stays on this computer. AI receives only bounded normalized Change Records when enabled.",
        "start_analysis": "Start analysis",
        "report_eyebrow": "REVIEW WORKSPACE",
        "report_title": "Change review report",
        "new_analysis": "New comparison",
        "metric_total": "Supported changes",
        "metric_added": "Added",
        "metric_deleted": "Deleted",
        "metric_modified": "Property changes",
        "metric_unsupported": "Unsupported",
        "filter_search": "Search GlobalId, entity, field, or value",
        "filter_all_types": "All change types",
        "filter_all_entities": "All entity types",
        "filter_all_storeys": "All storeys",
        "change_added": "Added",
        "change_deleted": "Deleted",
        "change_property_modified": "Property modified",
        "change_unsupported": "Unsupported",
        "results_count": "Showing {visible} of {total} changes",
        "table_type": "Type",
        "table_entity": "Entity",
        "table_guid": "GlobalId",
        "table_storey": "Storey",
        "table_field": "Field",
        "table_old": "Previous value",
        "table_new": "Revised value",
        "detail_title": "Change details",
        "detail_empty": "Select a change in the table to inspect its complete evidence.",
        "detail_change": "Change type",
        "detail_entity": "Entity type",
        "detail_guid": "GlobalId",
        "detail_storey": "Storey",
        "detail_field": "Field",
        "detail_old": "Previous value",
        "detail_new": "Revised value",
        "detail_evidence": "Evidence selector",
        "ai_output_title": "AI explanation",
        "ai_disabled_report": "AI was not enabled for this analysis. The deterministic report remains fully available.",
        "ai_generated_by": "Generated by {provider} · {model}",
        "ai_summary_heading": "Natural-language summary",
        "ai_rational_heading": "Brief rational analysis",
        "ai_key_changes_heading": "Key changes",
        "ai_limitations_heading": "Evidence limitations",
        "ai_no_key_changes": "No key changes were provided.",
        "ai_no_limitations": "No additional limitation was supplied; the disclaimer below still applies.",
        "ai_rational_unavailable": "The AI explanation was not generated, so no model-based rational analysis is available.",
        "ai_disclaimer": "Disclaimer: AI content is reading assistance only. Deterministic Change Records and source evidence remain authoritative. This content does not replace professional BIM coordination, engineering review, or structural safety assessment.",
        "export_json": "Export JSON",
        "export_html": "Export HTML",
        "open_folder": "Open report folder",
        "analysing": "Analysing…",
        "progress_compare": "Checking and comparing IFC files…",
        "progress_ai": "Deterministic comparison complete. Requesting AI explanation…",
        "progress_report": "Generating HTML report…",
        "settings_title": "Settings",
        "settings_general_tab": "General",
        "settings_ai_tab": "AI",
        "appearance_title": "Appearance and language",
        "theme": "Theme",
        "theme_system": "Use system setting",
        "theme_light": "Light",
        "theme_dark": "Dark",
        "language": "Interface language",
        "language_zh": "简体中文",
        "language_en": "English",
        "settings_restart_note": "Theme and language apply immediately after saving.",
        "ai_settings_title": "AI provider",
        "ai_enabled": "Enable AI explanation",
        "provider": "Provider",
        "planned": "planned",
        "base_url": "API Base URL",
        "model": "Model",
        "api_key": "API Key",
        "api_key_placeholder": "Kept in memory for this session only",
        "ai_privacy_note": "The API key is never persisted. IFC files, absolute paths, and file names are not sent; normalized records may still contain element, storey, and property information.",
        "save": "Save",
        "cancel": "Cancel",
        "file_dialog": "Choose IFC file",
        "file_selection_failed": "File selection failed",
        "drop_failed": "File drop failed",
        "invalid_ifc": "Choose a valid .ifc file",
        "settings_invalid": "Invalid settings",
        "ai_fields_required": "A model and API key are required when AI is enabled.",
        "analysis_running": "Analysis in progress",
        "analysis_running_body": "Wait for the current analysis to finish.",
        "missing_files": "Files required",
        "missing_files_body": "Choose both a previous and a revised IFC file.",
        "same_file": "Same file selected",
        "same_file_body": "The previous and revised files are identical. Choose two IFC versions.",
        "missing_key": "API key required",
        "missing_key_body": "Add an API key in Settings or turn off AI explanation in the main window.",
        "analysis_failed": "Analysis failed",
        "ai_failed": "AI explanation failed",
        "ai_failed_body": "The local deterministic comparison and report are complete, but no AI explanation was generated. Check the network and settings before trying again.",
        "ai_failed_reason": "The local deterministic report is complete. AI explanation failed: {reason}",
        "ai_error_configuration": "The {provider} settings are invalid. Check the model, provider, and API key.",
        "ai_error_authentication": "{provider} rejected authentication (HTTP {status}). Check that the API key is valid and allowed to use the selected model.",
        "ai_error_endpoint_or_model": "{provider} could not find the endpoint or model (HTTP {status}). Restore the official endpoint and check the model name.",
        "ai_error_rate_limit": "{provider} reached a rate or quota limit (HTTP {status}). Retry later and check the account quota.",
        "ai_error_provider_unavailable": "{provider} is temporarily unavailable (HTTP {status}). The local report is unaffected; retry later.",
        "ai_error_http_error": "The {provider} request failed (HTTP {status}). Check the provider settings and selected model.",
        "ai_error_network": "Could not reach {provider}. Check the network, proxy, and firewall.",
        "ai_error_timeout": "{provider} did not return a result before the timeout. Retry later.",
        "ai_error_invalid_json": "{provider} returned content that was not valid JSON. Retry or select another model.",
        "ai_error_provider_response": "{provider} returned an unrecognized response structure. Confirm that the model supports structured output.",
        "export_unavailable": "Nothing to export",
        "export_unavailable_body": "No report file is currently available.",
        "same_export": "Already there",
        "same_export_body": "The selected destination is the current report file.",
        "export_failed": "Export failed",
        "export_json_title": "Export JSON",
        "export_html_title": "Export HTML",
        "open_failed": "Could not open folder",
        "open_failed_body": "The system could not open this report folder.",
        "no_report_folder": "No report has been generated yet.",
        "unexpected_title": "Application error",
        "close_running": "Wait for the current analysis to finish before closing the application.",
        "friendly_os_error": "The input file or local report directory could not be accessed. Check permissions, disk space, and whether another application has locked the file.",
        "friendly_format_error": "The input or analysis artifact is invalid: {error}",
        "friendly_unexpected": "An unexpected {name} error occurred. Try again; if it continues, report the input format, size, and reproduction steps in GitHub Issues without uploading sensitive models.",
    },
}


def text(language: str, key: str, **values: Any) -> str:
    """Return a localized desktop string with a safe language fallback."""

    catalog = TEXT.get(language, TEXT["zh_CN"])
    template = catalog.get(key, TEXT["en"].get(key, key))
    return template.format(**values)


def stylesheet(theme: str) -> str:
    """Return the earth-toned Swiss-inspired application stylesheet."""

    dark = theme == "dark"
    arrow_asset = (
        Path(__file__).resolve().parent
        / "resources"
        / "branding"
        / ("combo-chevron-dark.xpm" if dark else "combo-chevron-light.xpm")
    ).as_posix()
    palette = {
        "canvas": "#17191C" if dark else "#F2F1ED",
        "surface": "#202328" if dark else "#FBFAF7",
        "surface_alt": "#2A2E34" if dark else "#E9E7E1",
        "surface_soft": "#25292F" if dark else "#F6F4EF",
        "text": "#ECEDEF" if dark else "#202327",
        "muted": "#A9ADB3" if dark else "#6D7175",
        "border": "#3B4047" if dark else "#D4D2CC",
        "accent": "#B76849" if dark else "#8E4E36",
        "accent_hover": "#C97B5D" if dark else "#743E2B",
        "accent_soft": "#332925" if dark else "#EEE0D8",
        "success": "#7E9A88" if dark else "#4F6958",
        "danger": "#C17B78" if dark else "#914943",
        "warning": "#B48B73" if dark else "#7B5948",
        "selection": "#343941" if dark else "#E8E2DC",
    }
    return f"""
QWidget {{ background: {palette['canvas']}; color: {palette['text']}; font-family: \"Segoe UI Variable Text\", \"Segoe UI\", \"Microsoft YaHei UI\"; font-size: 14px; }}
QMainWindow, QDialog {{ background: {palette['canvas']}; }}
QLabel, QCheckBox {{ background: transparent; }}
#appHeader {{ background: {palette['surface']}; border-bottom: 1px solid {palette['border']}; }}
#brand {{ font-size: 20px; font-weight: 700; letter-spacing: 0.3px; }}
#productDescriptor, #pageSubtitle, #muted, #dropDetail, #resultCount {{ color: {palette['muted']}; }}
#stepRail {{ background: {palette['surface']}; border-bottom: 1px solid {palette['border']}; }}
#stepLabel {{ color: {palette['muted']}; font-size: 12px; font-weight: 600; }}
#stepLabel[active="true"] {{ color: {palette['accent']}; }}
#eyebrow {{ color: {palette['accent']}; font-size: 12px; font-weight: 700; letter-spacing: 1px; }}
#pageTitle {{ font-size: 30px; font-weight: 700; letter-spacing: -0.2px; }}
#sectionTitle {{ font-size: 17px; font-weight: 650; }}
#previewNote {{ color: {palette['warning']}; background: {palette['accent_soft']}; border: 1px solid {palette['border']}; border-radius: 9px; padding: 8px 12px; }}
#dropZone {{ background: {palette['surface']}; border: 1px solid {palette['border']}; border-radius: 12px; }}
#dropZone:hover {{ border-color: {palette['accent']}; }}
#dropZone[hasFile="true"] {{ border: 2px solid {palette['accent']}; background: {palette['accent_soft']}; }}
#dropIndex {{ color: {palette['accent']}; font-size: 12px; font-weight: 700; }}
#dropTitle {{ font-size: 19px; font-weight: 650; }}
#summaryCard {{ background: {palette['surface']}; border: 1px solid {palette['border']}; border-top: 3px solid {palette['border']}; border-radius: 10px; }}
#summaryCard[metricKind="added"] {{ border-top-color: {palette['success']}; }}
#summaryCard[metricKind="deleted"] {{ border-top-color: {palette['danger']}; }}
#summaryCard[metricKind="property_modified"] {{ border-top-color: {palette['accent']}; }}
#summaryValue {{ font-size: 25px; font-weight: 700; }}
#filterBar, #detailPanel, #aiPanel {{ background: {palette['surface']}; border: 1px solid {palette['border']}; border-radius: 10px; }}
#progressPanel {{ background: {palette['accent_soft']}; border-top: 1px solid {palette['border']}; }}
#aiStateLabel {{ color: {palette['muted']}; font-size: 12px; font-weight: 650; padding: 5px 8px; border-radius: 8px; }}
#aiStateLabel[enabledState="true"] {{ color: {palette['text']}; background: {palette['accent_soft']}; }}
QPushButton {{ background: {palette['surface']}; border: 1px solid {palette['border']}; border-radius: 8px; padding: 9px 16px; }}
QPushButton:hover {{ border-color: {palette['accent']}; background: {palette['surface_alt']}; }}
QPushButton:pressed {{ background: {palette['selection']}; }}
QPushButton:disabled {{ color: {palette['muted']}; background: {palette['surface_alt']}; }}
#primaryButton {{ min-width: 200px; color: {palette['surface']}; background: {palette['accent']}; border-color: {palette['accent']}; font-weight: 700; }}
#primaryButton:hover {{ background: {palette['accent_hover']}; }}
#primaryButton:disabled {{ color: {palette['muted']}; background: {palette['surface_alt']}; border-color: {palette['border']}; }}
QCheckBox {{ spacing: 8px; }}
QLineEdit, QComboBox, QTextBrowser, QTableWidget, QTabWidget::pane {{ background: {palette['surface']}; border: 1px solid {palette['border']}; border-radius: 8px; selection-background-color: {palette['selection']}; selection-color: {palette['text']}; }}
QLineEdit, QComboBox {{ min-height: 34px; padding: 0 10px; }}
QComboBox {{ padding-right: 34px; }}
QComboBox::drop-down {{ border: none; border-left: 1px solid {palette['border']}; border-top-right-radius: 8px; border-bottom-right-radius: 8px; width: 28px; }}
QComboBox::drop-down:hover {{ background: {palette['surface_alt']}; }}
QComboBox::down-arrow {{ image: url("{arrow_asset}"); width: 11px; height: 5px; }}
QComboBox QAbstractItemView {{ background: {palette['surface']}; color: {palette['text']}; selection-background-color: {palette['selection']}; }}
QTableWidget {{ gridline-color: {palette['border']}; alternate-background-color: {palette['surface_soft']}; }}
QHeaderView::section {{ background: {palette['surface_alt']}; border: none; border-bottom: 1px solid {palette['border']}; padding: 9px; font-weight: 650; }}
QTableWidget::item {{ padding: 7px; border-bottom: 1px solid {palette['border']}; }}
QTableWidget::item:selected {{ background: {palette['selection']}; color: {palette['text']}; }}
QTabBar::tab {{ background: transparent; color: {palette['muted']}; padding: 10px 18px; border-bottom: 2px solid transparent; font-weight: 600; }}
QTabBar::tab:selected {{ color: {palette['text']}; border-bottom-color: {palette['accent']}; }}
QProgressBar {{ border: 1px solid {palette['border']}; border-radius: 7px; background: {palette['surface']}; text-align: center; }}
QProgressBar::chunk {{ background: {palette['accent']}; }}
QSplitter::handle {{ background: {palette['border']}; width: 3px; height: 3px; margin: 4px; border-radius: 2px; }}
QSplitter::handle:hover {{ background: {palette['accent']}; }}
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 2px; }}
QScrollBar::handle {{ background: {palette['border']}; border-radius: 4px; min-width: 28px; min-height: 28px; }}
QScrollBar::handle:hover {{ background: {palette['muted']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; background: transparent; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QToolTip {{ color: {palette['text']}; background: {palette['surface']}; border: 1px solid {palette['border']}; }}
"""
