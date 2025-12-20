"""
Office to PDF Converter Pro - Auto Update Checker
Version 4.0.0

Checks GitHub releases for new versions.
"""

import os
import sys
import json
import threading
import webbrowser
from typing import Optional, Callable
from dataclasses import dataclass
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# Add parent path
ui_dir = os.path.dirname(os.path.abspath(__file__))
package_dir = os.path.dirname(ui_dir)
if package_dir not in sys.path:
    sys.path.insert(0, package_dir)

from office_converter import __version__


@dataclass
class UpdateInfo:
    """Information about an available update."""
    version: str
    download_url: str
    release_notes: str
    published_at: str
    is_prerelease: bool = False


class UpdateChecker:
    """Check for application updates from GitHub releases."""

    # GitHub repository info
    GITHUB_OWNER = "vntimejsc-code"
    GITHUB_REPO = "Office-to-PDF-Converter-Pro"
    API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"

    def __init__(self, current_version: Optional[str] = None):
        self.current_version = current_version or __version__
        self._update_info: Optional[UpdateInfo] = None

    def check_async(self, callback: Callable[[Optional[UpdateInfo]], None]):
        """Check for updates asynchronously."""
        thread = threading.Thread(target=self._check_thread, args=(callback,), daemon=True)
        thread.start()

    def _check_thread(self, callback: Callable[[Optional[UpdateInfo]], None]):
        """Background thread for update check."""
        try:
            update_info = self.check()
            callback(update_info)
        except Exception:
            # Silent fail - don't bother user with update check errors
            callback(None)

    def check(self) -> Optional[UpdateInfo]:
        """Check for updates synchronously."""
        try:
            # Create request with headers
            request = Request(
                self.API_URL,
                headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": f"OfficeToPDF/{self.current_version}"
                }
            )

            # Fetch release info
            with urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode())

            # Parse version
            latest_version = data.get("tag_name", "").lstrip("v")

            if not latest_version:
                return None

            # Compare versions
            if self._is_newer(latest_version, self.current_version):
                # Find download URL for .exe
                download_url = ""
                for asset in data.get("assets", []):
                    if asset.get("name", "").endswith(".exe"):
                        download_url = asset.get("browser_download_url", "")
                        break

                if not download_url:
                    download_url = data.get("html_url", "")

                self._update_info = UpdateInfo(
                    version=latest_version,
                    download_url=download_url,
                    release_notes=data.get("body", ""),
                    published_at=data.get("published_at", ""),
                    is_prerelease=data.get("prerelease", False)
                )
                return self._update_info

            return None

        except HTTPError as e:
            # 404 = no releases yet, not an error
            if e.code == 404:
                return None
            # Other HTTP errors - log but don't show to user
            return None
        except (URLError, json.JSONDecodeError):
            # Network/parsing errors - silent fail
            return None
        except Exception:
            # Any other error - silent fail
            return None

    def _is_newer(self, latest: str, current: str) -> bool:
        """Compare version strings."""
        try:
            latest_parts = [int(x) for x in latest.split(".")[:3]]
            current_parts = [int(x) for x in current.split(".")[:3]]

            # Pad to same length
            while len(latest_parts) < 3:
                latest_parts.append(0)
            while len(current_parts) < 3:
                current_parts.append(0)

            return latest_parts > current_parts
        except ValueError:
            return False

    @staticmethod
    def open_download(url: str):
        """Open download URL in browser."""
        webbrowser.open(url)


def show_update_dialog(parent, update_info: UpdateInfo):
    """Show update available dialog using CustomTkinter."""
    try:
        import customtkinter as ctk

        dialog = ctk.CTkToplevel(parent)
        dialog.title("🎉 Có bản cập nhật mới!")
        dialog.geometry("450x350")
        dialog.transient(parent)
        dialog.grab_set()

        # Center dialog
        dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 450) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 350) // 2
        dialog.geometry(f"+{x}+{y}")

        # Content
        ctk.CTkLabel(
            dialog,
            text="🎉 Phiên bản mới có sẵn!",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(pady=20)

        version_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        version_frame.pack(pady=10)

        ctk.CTkLabel(
            version_frame,
            text=f"Phiên bản hiện tại: v{__version__}",
            text_color="gray"
        ).pack()

        ctk.CTkLabel(
            version_frame,
            text=f"Phiên bản mới: v{update_info.version}",
            font=ctk.CTkFont(weight="bold"),
            text_color="#22C55E"
        ).pack()

        # Release notes
        if update_info.release_notes:
            notes_label = ctk.CTkLabel(
                dialog,
                text="📝 Ghi chú phát hành:",
                anchor="w"
            )
            notes_label.pack(fill="x", padx=30, pady=(15, 5))

            notes_text = ctk.CTkTextbox(dialog, height=100)
            notes_text.pack(fill="x", padx=30)
            notes_text.insert("1.0", update_info.release_notes[:500])
            notes_text.configure(state="disabled")

        # Buttons
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=20)

        def download():
            UpdateChecker.open_download(update_info.download_url)
            dialog.destroy()

        ctk.CTkButton(
            btn_frame,
            text="⬇️ Tải về ngay",
            command=download,
            fg_color="#22C55E",
            hover_color="#16A34A",
            width=150
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            btn_frame,
            text="Để sau",
            command=dialog.destroy,
            fg_color="transparent",
            border_width=2,
            width=100
        ).pack(side="left", padx=10)

    except ImportError:
        # Fallback to tkinter messagebox
        from tkinter import messagebox
        if messagebox.askyesno(
            "Cập nhật có sẵn",
            f"Phiên bản mới v{update_info.version} có sẵn!\n\n"
            f"Bạn có muốn tải về không?"
        ):
            UpdateChecker.open_download(update_info.download_url)


def check_for_updates_on_startup(parent, show_if_none: bool = False):
    """Check for updates and show dialog if available."""
    def on_result(update_info: Optional[UpdateInfo]):
        if update_info:
            parent.after(0, lambda: show_update_dialog(parent, update_info))
        elif show_if_none:
            parent.after(0, lambda: _show_no_update_message(parent))

    checker = UpdateChecker()
    checker.check_async(on_result)


def _show_no_update_message(parent):
    """Show message when no update is available."""
    try:
        from tkinter import messagebox
        messagebox.showinfo(
            "Cập nhật",
            f"Bạn đang sử dụng phiên bản mới nhất (v{__version__})"
        )
    except Exception:
        pass


# Test
if __name__ == "__main__":
    print(f"Current version: {__version__}")

    checker = UpdateChecker()
    update = checker.check()

    if update:
        print(f"✅ Update available: v{update.version}")
        print(f"   Download: {update.download_url}")
    else:
        print("✓ You have the latest version")
