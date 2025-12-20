"""
Localization Module - Multi-language support.
"""

from typing import Dict

# === MULTI-LANGUAGE DICTIONARY ===
LANGUAGES: Dict[str, Dict[str, str]] = {
    "vi": {
        "name": "Tiếng Việt",
        # Main Window
        "app_title": "Office to PDF Converter Pro",
        "version": "Phiên bản",
        "file_list_title": "📁 Danh sách Files",
        "btn_add_file": "➕ Files",
        "btn_add_folder": "📁 Folder",
        "btn_clear": "🗑️",
        "btn_pdf_tools": "🛠️ PDF Tools",
        "btn_convert": "🚀 CHUYỂN ĐỔI SANG PDF",
        "btn_stop": "⏹️ Dừng",
        "btn_resume": "▶️ Tiếp tục",
        "btn_settings": "⚙️",
        # File Status
        "files_count": "{0} files",
        "no_files": "Chưa có file",
        "file_ready": "Sẵn sàng",
        "file_converting": "Đang xử lý...",
        "file_done": "✅ Xong",
        "file_error": "❌ Lỗi",
        # Preview
        "preview": "📄 Xem trước",
        "no_preview": "Chọn file để xem trước",
        "page": "Trang",
        # Options
        "options_title": "⚙️ Tùy chọn",
        "output_folder": "📂 Thư mục xuất",
        "output_same": "Cùng folder với file gốc",
        "output_custom": "Khác:",
        "quality_label": "📊 Chất lượng",
        "scan_mode": "🖼️ Chế độ Scan",
        "password_protect": "🔒 Mật khẩu",
        "page_range": "📄 Trang:",
        # Progress
        "progress_title": "📊 Tiến trình",
        "status_ready": "Sẵn sàng",
        "status_processing": "Đang xử lý...",
        "status_done": "Hoàn tất",
        "status_error": "Có lỗi",
        # Log
        "log_title": "📝 Log",
        "log_clear": "Xóa log",
        # PDF Tools Pro
        "pdf_tools_title": "🛠️ PDF Tools Pro",
        "tab_edit": "✏️ Chỉnh sửa",
        "tab_convert": "🔄 Chuyển đổi",
        "tab_optimize": "⚡ Tối ưu",
        "op_merge": "📎 Gộp PDF",
        "op_split": "✂️ Tách PDF",
        "op_extract": "📑 Trích xuất",
        "op_delete": "🗑️ Xóa trang",
        "op_rotate": "🔄 Xoay",
        "op_reverse": "🔃 Đảo ngược",
        "op_pdf_to_img": "🖼️ PDF → Ảnh",
        "op_img_to_pdf": "📄 Ảnh → PDF",
        "op_ocr": "🔍 OCR",
        "op_compress": "📦 Nén",
        "op_protect": "🔒 Mật khẩu",
        "op_watermark": "💧 Watermark",
        "btn_execute": "🚀 THỰC HIỆN",
        "btn_close": "Đóng",
        "quality_low": "🔹 Thấp (nhỏ nhất)",
        "quality_medium": "🔸 Trung bình",
        "quality_high": "🔶 Cao (chất lượng)",
        "rotation_angle": "Góc xoay:",
        "page_range_hint": "Số trang (vd: 1-5, 8, 10-12):",
        "watermark_text": "Text watermark:",
        "password_label": "Mật khẩu:",
        "dpi_label": "DPI:",
        "format_label": "Định dạng:",
        "no_options": "Không có tùy chọn",
        # Dialogs & Messages
        "warning": "Cảnh báo",
        "error": "Lỗi",
        "success": "Thành công",
        "confirm": "Xác nhận",
        "no_files_warning": "Chưa chọn file nào!",
        "need_2_files": "Cần ít nhất 2 file để gộp!",
        "processing": "Đang xử lý...",
        "complete": "✅ Hoàn thành",
        "failed": "❌ Thất bại",
        "drag_drop_hint": "📁 Drag & Drop: Kéo thả file hoạt động",
        "tesseract_not_found": "Tesseract chưa được cài đặt",
        # Settings
        "settings_title": "⚙️ Cài đặt",
        "language_label": "🌐 Ngôn ngữ",
        "theme_dark": "🌙 Dark",
        "theme_light": "☀️ Light",
        # Time
        "minute": "phút",
        "second": "giây",
        "elapsed": "⏱️ Đã chạy:",
        "remaining": "⏳ Còn lại:",
    },
    "en": {
        "name": "English",
        # Main Window
        "app_title": "Office to PDF Converter Pro",
        "version": "Version",
        "file_list_title": "📁 File List",
        "btn_add_file": "➕ Files",
        "btn_add_folder": "📁 Folder",
        "btn_clear": "🗑️",
        "btn_pdf_tools": "🛠️ PDF Tools",
        "btn_convert": "🚀 CONVERT TO PDF",
        "btn_stop": "⏹️ Stop",
        "btn_resume": "▶️ Resume",
        "btn_settings": "⚙️",
        # File Status
        "files_count": "{0} files",
        "no_files": "No files",
        "file_ready": "Ready",
        "file_converting": "Processing...",
        "file_done": "✅ Done",
        "file_error": "❌ Error",
        # Preview
        "preview": "📄 Preview",
        "no_preview": "Select file to preview",
        "page": "Page",
        # Options
        "options_title": "⚙️ Options",
        "output_folder": "📂 Output folder",
        "output_same": "Same folder as source",
        "output_custom": "Other:",
        "quality_label": "📊 Quality",
        "scan_mode": "🖼️ Scan mode",
        "password_protect": "🔒 Password",
        "page_range": "📄 Pages:",
        # Progress
        "progress_title": "📊 Progress",
        "status_ready": "Ready",
        "status_processing": "Processing...",
        "status_done": "Complete",
        "status_error": "Error",
        # Log
        "log_title": "📝 Log",
        "log_clear": "Clear log",
        # PDF Tools Pro
        "pdf_tools_title": "🛠️ PDF Tools Pro",
        "tab_edit": "✏️ Edit",
        "tab_convert": "🔄 Convert",
        "tab_optimize": "⚡ Optimize",
        "op_merge": "📎 Merge PDF",
        "op_split": "✂️ Split PDF",
        "op_extract": "📑 Extract",
        "op_delete": "🗑️ Delete pages",
        "op_rotate": "🔄 Rotate",
        "op_reverse": "🔃 Reverse",
        "op_pdf_to_img": "🖼️ PDF → Image",
        "op_img_to_pdf": "📄 Image → PDF",
        "op_ocr": "🔍 OCR",
        "op_compress": "📦 Compress",
        "op_protect": "🔒 Password",
        "op_watermark": "💧 Watermark",
        "btn_execute": "🚀 EXECUTE",
        "btn_close": "Close",
        "quality_low": "🔹 Low (smallest)",
        "quality_medium": "🔸 Medium",
        "quality_high": "🔶 High (quality)",
        "rotation_angle": "Rotation angle:",
        "page_range_hint": "Page range (e.g.: 1-5, 8, 10-12):",
        "watermark_text": "Watermark text:",
        "password_label": "Password:",
        "dpi_label": "DPI:",
        "format_label": "Format:",
        "no_options": "No options",
        # Dialogs & Messages
        "warning": "Warning",
        "error": "Error",
        "success": "Success",
        "confirm": "Confirm",
        "no_files_warning": "No files selected!",
        "need_2_files": "Need at least 2 files to merge!",
        "processing": "Processing...",
        "complete": "✅ Complete",
        "failed": "❌ Failed",
        "drag_drop_hint": "📁 Drag & Drop: Drop files to add",
        "tesseract_not_found": "Tesseract not installed",
        # Settings
        "settings_title": "⚙️ Settings",
        "language_label": "🌐 Language",
        "theme_dark": "🌙 Dark",
        "theme_light": "☀️ Light",
        # Time
        "minute": "min",
        "second": "sec",
        "elapsed": "⏱️ Elapsed:",
        "remaining": "⏳ Remaining:",
    },
    "zh": {
        "name": "简体中文",
        # Main Window
        "app_title": "Office转PDF专业版",
        "version": "版本",
        "file_list_title": "📁 文件列表",
        "btn_add_file": "➕ 文件",
        "btn_add_folder": "📁 文件夹",
        "btn_clear": "🗑️",
        "btn_pdf_tools": "🛠️ PDF工具",
        "btn_convert": "🚀 转换为PDF",
        "btn_stop": "⏹️ 停止",
        "btn_resume": "▶️ 继续",
        "btn_settings": "⚙️",
        # File Status
        "files_count": "{0} 个文件",
        "no_files": "暂无文件",
        "file_ready": "就绪",
        "file_converting": "处理中...",
        "file_done": "✅ 完成",
        "file_error": "❌ 错误",
        # Preview
        "preview": "📄 预览",
        "no_preview": "选择文件进行预览",
        "page": "页",
        # Options
        "options_title": "⚙️ 选项",
        "output_folder": "📂 输出文件夹",
        "output_same": "与源文件相同",
        "output_custom": "其他:",
        "quality_label": "📊 质量",
        "scan_mode": "🖼️ 扫描模式",
        "password_protect": "🔒 密码",
        "page_range": "📄 页面:",
        # Progress
        "progress_title": "📊 进度",
        "status_ready": "就绪",
        "status_processing": "处理中...",
        "status_done": "完成",
        "status_error": "错误",
        # Log
        "log_title": "📝 日志",
        "log_clear": "清除日志",
        # PDF Tools Pro
        "pdf_tools_title": "🛠️ PDF工具专业版",
        "tab_edit": "✏️ 编辑",
        "tab_convert": "🔄 转换",
        "tab_optimize": "⚡ 优化",
        "op_merge": "📎 合并PDF",
        "op_split": "✂️ 拆分PDF",
        "op_extract": "📑 提取",
        "op_delete": "🗑️ 删除页面",
        "op_rotate": "🔄 旋转",
        "op_reverse": "🔃 倒序",
        "op_pdf_to_img": "🖼️ PDF → 图片",
        "op_img_to_pdf": "📄 图片 → PDF",
        "op_ocr": "🔍 OCR",
        "op_compress": "📦 压缩",
        "op_protect": "🔒 密码",
        "op_watermark": "💧 水印",
        "btn_execute": "🚀 执行",
        "btn_close": "关闭",
        "quality_low": "🔹 低 (最小)",
        "quality_medium": "🔸 中",
        "quality_high": "🔶 高 (质量)",
        "rotation_angle": "旋转角度:",
        "page_range_hint": "页码范围 (例: 1-5, 8, 10-12):",
        "watermark_text": "水印文字:",
        "password_label": "密码:",
        "dpi_label": "DPI:",
        "format_label": "格式:",
        "no_options": "无选项",
        # Dialogs & Messages
        "warning": "警告",
        "error": "错误",
        "success": "成功",
        "confirm": "确认",
        "no_files_warning": "未选择文件！",
        "need_2_files": "至少需要2个文件才能合并！",
        "processing": "处理中...",
        "complete": "✅ 完成",
        "failed": "❌ 失败",
        "drag_drop_hint": "📁 拖放: 拖动文件添加",
        "tesseract_not_found": "Tesseract未安装",
        # Settings
        "settings_title": "⚙️ 设置",
        "language_label": "🌐 语言",
        "theme_dark": "🌙 深色",
        "theme_light": "☀️ 浅色",
        # Time
        "minute": "分",
        "second": "秒",
        "elapsed": "⏱️ 已用:",
        "remaining": "⏳ 剩余:",
    },
    "ja": {
        "name": "日本語",
        # Main Window
        "app_title": "Office→PDF変換ツール Pro",
        "version": "バージョン",
        "file_list_title": "📁 ファイルリスト",
        "btn_add_file": "➕ ファイル",
        "btn_add_folder": "📁 フォルダ",
        "btn_clear": "🗑️",
        "btn_pdf_tools": "🛠️ PDFツール",
        "btn_convert": "🚀 PDFに変換",
        "btn_stop": "⏹️ 停止",
        "btn_resume": "▶️ 続行",
        "btn_settings": "⚙️",
        # File Status
        "files_count": "{0} ファイル",
        "no_files": "ファイルなし",
        "file_ready": "準備完了",
        "file_converting": "処理中...",
        "file_done": "✅ 完了",
        "file_error": "❌ エラー",
        # Preview
        "preview": "📄 プレビュー",
        "no_preview": "プレビューするファイルを選択",
        "page": "ページ",
        # Options
        "options_title": "⚙️ オプション",
        "output_folder": "📂 出力フォルダ",
        "output_same": "元ファイルと同じ",
        "output_custom": "その他:",
        "quality_label": "📊 品質",
        "scan_mode": "🖼️ スキャンモード",
        "password_protect": "🔒 パスワード",
        "page_range": "📄 ページ:",
        # Progress
        "progress_title": "📊 進捗",
        "status_ready": "準備完了",
        "status_processing": "処理中...",
        "status_done": "完了",
        "status_error": "エラー",
        # Log
        "log_title": "📝 ログ",
        "log_clear": "ログをクリア",
        # PDF Tools Pro
        "pdf_tools_title": "🛠️ PDFツール Pro",
        "tab_edit": "✏️ 編集",
        "tab_convert": "🔄 変換",
        "tab_optimize": "⚡ 最適化",
        "op_merge": "📎 PDF結合",
        "op_split": "✂️ PDF分割",
        "op_extract": "📑 抽出",
        "op_delete": "🗑️ ページ削除",
        "op_rotate": "🔄 回転",
        "op_reverse": "🔃 逆順",
        "op_pdf_to_img": "🖼️ PDF → 画像",
        "op_img_to_pdf": "📄 画像 → PDF",
        "op_ocr": "🔍 OCR",
        "op_compress": "📦 圧縮",
        "op_protect": "🔒 パスワード",
        "op_watermark": "💧 透かし",
        "btn_execute": "🚀 実行",
        "btn_close": "閉じる",
        "quality_low": "🔹 低 (最小)",
        "quality_medium": "🔸 中",
        "quality_high": "🔶 高 (高品質)",
        "rotation_angle": "回転角度:",
        "page_range_hint": "ページ範囲 (例: 1-5, 8, 10-12):",
        "watermark_text": "透かしテキスト:",
        "password_label": "パスワード:",
        "dpi_label": "DPI:",
        "format_label": "フォーマット:",
        "no_options": "オプションなし",
        # Dialogs & Messages
        "warning": "警告",
        "error": "エラー",
        "success": "成功",
        "confirm": "確認",
        "no_files_warning": "ファイルが選択されていません！",
        "need_2_files": "結合には2つ以上のファイルが必要！",
        "processing": "処理中...",
        "complete": "✅ 完了",
        "failed": "❌ 失敗",
        "drag_drop_hint": "📁 ドラッグ&ドロップ: ファイルを追加",
        "tesseract_not_found": "Tesseractがインストールされていません",
        # Settings
        "settings_title": "⚙️ 設定",
        "language_label": "🌐 言語",
        "theme_dark": "🌙 ダーク",
        "theme_light": "☀️ ライト",
        # Time
        "minute": "分",
        "second": "秒",
        "elapsed": "⏱️ 経過:",
        "remaining": "⏳ 残り:",
    },
    "ko": {
        "name": "한국어",
        # Main Window
        "app_title": "Office→PDF 변환기 Pro",
        "version": "버전",
        "file_list_title": "📁 파일 목록",
        "btn_add_file": "➕ 파일",
        "btn_add_folder": "📁 폴더",
        "btn_clear": "🗑️",
        "btn_pdf_tools": "🛠️ PDF 도구",
        "btn_convert": "🚀 PDF로 변환",
        "btn_stop": "⏹️ 중지",
        "btn_resume": "▶️ 계속",
        "btn_settings": "⚙️",
        # File Status
        "files_count": "{0}개 파일",
        "no_files": "파일 없음",
        "file_ready": "준비됨",
        "file_converting": "처리 중...",
        "file_done": "✅ 완료",
        "file_error": "❌ 오류",
        # Preview
        "preview": "📄 미리보기",
        "no_preview": "미리보기할 파일 선택",
        "page": "페이지",
        # Options
        "options_title": "⚙️ 옵션",
        "output_folder": "📂 출력 폴더",
        "output_same": "원본과 동일한 폴더",
        "output_custom": "기타:",
        "quality_label": "📊 품질",
        "scan_mode": "🖼️ 스캔 모드",
        "password_protect": "🔒 비밀번호",
        "page_range": "📄 페이지:",
        # Progress
        "progress_title": "📊 진행률",
        "status_ready": "준비됨",
        "status_processing": "처리 중...",
        "status_done": "완료",
        "status_error": "오류",
        # Log
        "log_title": "📝 로그",
        "log_clear": "로그 지우기",
        # PDF Tools Pro
        "pdf_tools_title": "🛠️ PDF 도구 Pro",
        "tab_edit": "✏️ 편집",
        "tab_convert": "🔄 변환",
        "tab_optimize": "⚡ 최적화",
        "op_merge": "📎 PDF 병합",
        "op_split": "✂️ PDF 분할",
        "op_extract": "📑 추출",
        "op_delete": "🗑️ 페이지 삭제",
        "op_rotate": "🔄 회전",
        "op_reverse": "🔃 역순",
        "op_pdf_to_img": "🖼️ PDF → 이미지",
        "op_img_to_pdf": "📄 이미지 → PDF",
        "op_ocr": "🔍 OCR",
        "op_compress": "📦 압축",
        "op_protect": "🔒 비밀번호",
        "op_watermark": "💧 워터마크",
        "btn_execute": "🚀 실행",
        "btn_close": "닫기",
        "quality_low": "🔹 낮음 (최소)",
        "quality_medium": "🔸 보통",
        "quality_high": "🔶 높음 (고품질)",
        "rotation_angle": "회전 각도:",
        "page_range_hint": "페이지 범위 (예: 1-5, 8, 10-12):",
        "watermark_text": "워터마크 텍스트:",
        "password_label": "비밀번호:",
        "dpi_label": "DPI:",
        "format_label": "형식:",
        "no_options": "옵션 없음",
        # Dialogs & Messages
        "warning": "경고",
        "error": "오류",
        "success": "성공",
        "confirm": "확인",
        "no_files_warning": "파일이 선택되지 않았습니다!",
        "need_2_files": "병합하려면 2개 이상의 파일이 필요!",
        "processing": "처리 중...",
        "complete": "✅ 완료",
        "failed": "❌ 실패",
        "drag_drop_hint": "📁 드래그 앤 드롭: 파일 추가",
        "tesseract_not_found": "Tesseract가 설치되지 않음",
        # Settings
        "settings_title": "⚙️ 설정",
        "language_label": "🌐 언어",
        "theme_dark": "🌙 다크",
        "theme_light": "☀️ 라이트",
        # Time
        "minute": "분",
        "second": "초",
        "elapsed": "⏱️ 경과:",
        "remaining": "⏳ 남음:",
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
