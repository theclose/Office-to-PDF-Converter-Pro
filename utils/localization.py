"""
Localization Module - Multi-language support.
"""

from typing import Dict, Any

# === MULTI-LANGUAGE DICTIONARY ===
LANGUAGES: Dict[str, Dict[str, str]] = {
    "vi": {
        "name": "Tiếng Việt",
        "app_title": "Office to PDF Pro (by TungDo)",
        "file_list_title": "Danh sách file (Ctrl+O hoặc nút Thêm)",
        "btn_add_file": "➕ Thêm File",
        "btn_add_folder": "📁 Thêm Folder",
        "btn_clear": "🗑️ Xóa",
        "btn_convert": "🚀 Convert (Chọn/Hết)",
        "btn_stop": "⏹️ Dừng",
        "btn_resume": "▶️ Tiếp tục",
        "btn_dark": "🌙 Dark",
        "btn_light": "☀️ Light",
        "pdf_tools": "🛠️ PDF Tools:",
        "btn_merge": "📎 Gộp PDF",
        "btn_split": "✂️ Tách PDF",
        "btn_compress": "📦 Nén PDF",
        "btn_watermark": "💧 Watermark",
        "btn_pdf_to_img": "🖼️ PDF→Ảnh",
        "btn_img_to_pdf": "📄 Ảnh→PDF",
        "btn_rotate": "🔄 Xoay",
        "btn_extract": "📑 Trích",
        "btn_delete_pages": "🗑️ Xóa trang",
        "btn_reverse": "🔃 Đảo ngược",
        "output_folder": "📂 Xuất PDF vào:",
        "output_default": "(Cùng thư mục với file gốc)",
        "btn_select": "Chọn...",
        "btn_reset": "Reset",
        "options_title": "Tùy chọn xuất PDF",
        "all_sheets": "Toàn bộ các Sheet",
        "specific_sheets": "Chỉ xuất Sheet:",
        "sheet_hint": "(VD: 1-3, 5, 7-10)",
        "quality_label": "Chất lượng PDF:",
        "quality_high": "📄 Cao",
        "quality_min": "📦 Nhỏ nhất",
        "security_label": "Bảo mật & Metadata:",
        "password_label": "🔒 Đặt mật khẩu PDF:",
        "author_label": "👤 Author:",
        "title_label": "📝 Title:",
        "page_range": "📄 Trang:",
        "page_hint": "(VD: 1-3, 5, 7-10 | Để trống = tất cả)",
        "scan_mode": "🖼️ Chế độ Scan (không copy text)",
        "progress_title": "Tiến độ xử lý",
        "status_ready": "Sẵn sàng...",
        "log_title": "Chi tiết hoạt động (Log)",
        "complete_title": "Hoàn tất",
        "complete_msg": "✅ Đã chuyển đổi xong!",
        "btn_open_folder": "📂 Mở thư mục",
        "btn_exit": "❌ Thoát",
        "language": "🌐",
        "gift_msg": "💖 Thân tặng các em gái ATL xinh xắn, đáng yêu 🧸🎀",
        "file_count": "Đang có {0} files.",
        "processing": "Đang xử lý {0} file...",
        "total_time": "Tổng thời gian: {0}s",
        "all_done": "✅ TẤT CẢ HOÀN TẤT!",
        "processing_log": "Đang xử lý: {0}",
        "counting_pages": "...Đang đếm số trang...",
        "extracting_pages": "📄 Đã trích xuất trang: {0}",
        "password_set": "🔒 Đã đặt mật khẩu PDF.",
        "scan_switched": "🖼️ Đã chuyển sang chế độ Scan.",
        "complete_log": "✅ Hoàn thành.",
        "analyzing": "🔍 Đang phân tích hệ thống...",
        "quality_log": "📄 Chất lượng PDF: {0}",
        "sheet_mode_log": "ℹ️  Chế độ: Xuất Sheet {0}",
        "workbook_mode_log": "ℹ️  Chế độ: Xuất toàn bộ Workbook",
        "error_log": "❌ Lỗi: {0}",
        "empty_list_warning": "Danh sách trống! Vui lòng thêm file.",
        "warning_title": "Cảnh báo",
        "estimated_time": "Estimated time:",
        "minute": "phút",
        "second": "giây",
        "elapsed_time": "⏱️ Đã chạy:",
        "remaining_time": "⏳ Còn lại:",
    },
    "en": {
        "name": "English",
        "app_title": "Office to PDF Pro (by TungDo)",
        "file_list_title": "Files (Ctrl+O or Add button)",
        "btn_add_file": "➕ Add Files",
        "btn_add_folder": "📁 Add Folder",
        "btn_clear": "🗑️ Delete",
        "btn_convert": "🚀 Convert (Sel/All)",
        "btn_stop": "⏹️ Stop",
        "btn_resume": "▶️ Resume",
        "btn_dark": "🌙 Dark",
        "btn_light": "☀️ Light",
        "pdf_tools": "🛠️ PDF Tools:",
        "btn_merge": "📎 Merge PDF",
        "btn_split": "✂️ Split PDF",
        "btn_compress": "📦 Compress",
        "btn_watermark": "💧 Watermark",
        "btn_pdf_to_img": "🖼️ PDF→Img",
        "btn_img_to_pdf": "📄 Img→PDF",
        "btn_rotate": "🔄 Rotate",
        "btn_extract": "📑 Extract",
        "btn_delete_pages": "🗑️ Del Pages",
        "btn_reverse": "🔃 Reverse",
        "output_folder": "📂 Output to:",
        "output_default": "(Same folder as source)",
        "btn_select": "Select...",
        "btn_reset": "Reset",
        "options_title": "PDF Export Options",
        "all_sheets": "All Sheets",
        "specific_sheets": "Only Sheets:",
        "sheet_hint": "(e.g.: 1-3, 5, 7-10)",
        "quality_label": "PDF Quality:",
        "quality_high": "📄 High quality",
        "quality_min": "📦 Minimum size",
        "security_label": "Security & Metadata:",
        "password_label": "🔒 Set PDF password:",
        "author_label": "👤 Author:",
        "title_label": "📝 Title:",
        "page_range": "📄 Pages:",
        "page_hint": "(e.g.: 1-3, 5, 7-10 | Empty = all)",
        "scan_mode": "🖼️ Scan mode (no copy)",
        "progress_title": "Progress",
        "status_ready": "Ready...",
        "log_title": "Activity Log",
        "complete_title": "Complete",
        "complete_msg": "✅ Conversion complete!",
        "btn_open_folder": "📂 Open Folder",
        "btn_exit": "❌ Exit",
        "language": "🌐",
        "gift_msg": "💖 Made with love for ATL girls 🧸🎀",
        "file_count": "{0} files loaded.",
        "processing": "Processing {0} file(s)...",
        "total_time": "Total time: {0}s",
        "all_done": "✅ ALL COMPLETE!",
        "processing_log": "Processing: {0}",
        "counting_pages": "...Counting pages...",
        "extracting_pages": "📄 Extracted pages: {0}",
        "password_set": "🔒 PDF Password set.",
        "scan_switched": "🖼️ Switched to Scan mode.",
        "complete_log": "✅ Complete.",
        "analyzing": "🔍 Analyzing system...",
        "quality_log": "📄 PDF Quality: {0}",
        "sheet_mode_log": "ℹ️  Mode: Sheet {0}",
        "workbook_mode_log": "ℹ️  Mode: Workbook",
        "error_log": "❌ Error: {0}",
        "empty_list_warning": "List is empty! Please add files.",
        "warning_title": "Warning",
        "estimated_time": "Estimated time:",
        "minute": "min",
        "second": "sec",
        "elapsed_time": "⏱️ Elapsed:",
        "remaining_time": "⏳ Remaining:",
    },
    "zh": {
        "name": "简体中文",
        "app_title": "Office转PDF专业版 (by TungDo)",
        "file_list_title": "文件列表 (Ctrl+O 或 添加按钮)",
        "btn_add_file": "➕ 添加文件",
        "btn_add_folder": "📁 添加文件夹",
        "btn_clear": "🗑️ 删除",
        "btn_convert": "🚀 转换 (选中/全部)",
        "btn_stop": "⏹️ 停止",
        "btn_resume": "▶️ 继续",
        "btn_dark": "🌙 深色",
        "btn_light": "☀️ 浅色",
        "pdf_tools": "🛠️ PDF工具:",
        "btn_merge": "📎 合并PDF",
        "btn_split": "✂️ 拆分PDF",
        "btn_compress": "📦 压缩",
        "btn_watermark": "💧 水印",
        "btn_pdf_to_img": "🖼️ PDF→图",
        "btn_img_to_pdf": "📄 图→PDF",
        "btn_rotate": "🔄 旋转",
        "btn_extract": "📑 提取",
        "btn_delete_pages": "🗑️ 删页",
        "btn_reverse": "🔃 倒序",
        "output_folder": "📂 输出到:",
        "output_default": "(与源文件相同文件夹)",
        "btn_select": "选择...",
        "btn_reset": "重置",
        "options_title": "PDF导出选项",
        "all_sheets": "所有工作表",
        "specific_sheets": "指定工作表:",
        "sheet_hint": "(例如: 1-3, 5, 7-10)",
        "quality_label": "PDF质量:",
        "quality_high": "📄 高质量",
        "quality_min": "📦 最小",
        "security_label": "安全与元数据:",
        "password_label": "🔒 设置PDF密码:",
        "author_label": "👤 作者:",
        "title_label": "📝 标题:",
        "page_range": "📄 页面:",
        "page_hint": "(例如: 1-3, 5, 7-10 | 留空=全部)",
        "scan_mode": "🖼️ 扫描模式 (无法复制)",
        "progress_title": "处理进度",
        "status_ready": "准备就绪...",
        "log_title": "活动日志",
        "complete_title": "完成",
        "complete_msg": "✅ 转换完成!",
        "btn_open_folder": "📂 打开文件夹",
        "btn_exit": "❌ 退出",
        "language": "🌐",
        "gift_msg": "💖 献给ATL可爱的女孩们 🧸🎀",
        "file_count": "已加载 {0} 个文件.",
        "processing": "正在处理 {0} 个文件...",
        "total_time": "总时间: {0}秒",
        "all_done": "✅ 全部完成!",
        "processing_log": "正在处理: {0}",
        "counting_pages": "...正在计算页数...",
        "extracting_pages": "📄 已提取页面: {0}",
        "password_set": "🔒 PDF密码已设置.",
        "scan_switched": "🖼️ 已切换到扫描模式.",
        "complete_log": "✅ 完成.",
        "analyzing": "🔍 正在分析系统...",
        "quality_log": "📄 PDF质量: {0}",
        "sheet_mode_log": "ℹ️  模式: 工作表 {0}",
        "workbook_mode_log": "ℹ️  模式: 整个工作簿",
        "error_log": "❌ 错误: {0}",
        "empty_list_warning": "列表为空！请添加文件。",
        "warning_title": "警告",
        "estimated_time": "预计时间:",
        "minute": "分",
        "second": "秒",
        "elapsed_time": "⏱️ 已用:",
        "remaining_time": "⏳ 剩余:",
    }
}

# Current language (default to Vietnamese)
_current_lang = "vi"


def set_language(lang_code: str):
    """Set the current language."""
    global _current_lang
    if lang_code in LANGUAGES:
        _current_lang = lang_code


def get_current_language() -> str:
    """Get current language code."""
    return _current_lang


def get_text(key: str, lang: str = None) -> str:
    """
    Get translated text for a key.
    
    Args:
        key: Translation key
        lang: Language code (optional, uses current if not specified)
        
    Returns:
        Translated string or key if not found
    """
    lang = lang or _current_lang
    if lang in LANGUAGES and key in LANGUAGES[lang]:
        return LANGUAGES[lang][key]
    # Fallback to English
    if key in LANGUAGES.get("en", {}):
        return LANGUAGES["en"][key]
    return key


def get_language_names() -> Dict[str, str]:
    """Get dictionary of language code -> display name."""
    return {code: data["name"] for code, data in LANGUAGES.items()}
