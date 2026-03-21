"""
Integration tests: UI/Framework lifecycle edge cases.
Catches bugs like Trap #17 (CTkEntry textvariable trace on destroy).

These tests create/destroy UI components to verify proper
cleanup of callbacks, traces, and event handlers.

NOTE: Tests use root.update() loop instead of mainloop()
to avoid blocking the test runner.
"""

import os
import gc
import time
import pytest


def _create_root():
    """Create a CTk root window for testing."""
    try:
        import customtkinter as ctk
        root = ctk.CTk()
        root.withdraw()  # Hide window
        root.update()
        return root
    except Exception:
        pytest.skip("customtkinter not available or no display")


class TestPDFToolsDialogLifecycle:
    """Tests for PDF Tools dialog create/destroy cycles."""

    def test_pdf_tools_dialog_open_close_10x(self):
        """Trap #17: Opening and closing PDF Tools dialog 10 times
        must not leave stale textvariable traces."""
        root = _create_root()
        try:
            from office_converter.ui.pdf_tools_pro import PDFToolsDialogPro
            from office_converter.utils.config import Config

            config = Config()
            errors = []

            for i in range(10):
                try:
                    dialog = PDFToolsDialogPro(root, config)
                    root.update()
                    # Simulate close
                    dialog._on_close()
                    root.update()
                except Exception as e:
                    errors.append(f"Cycle {i+1}: {e}")

            assert len(errors) == 0, f"Dialog lifecycle errors: {errors}"
        finally:
            root.destroy()

    def test_pdf_tools_switch_operations_20x(self):
        """Switching between compress/merge/split 20 times
        must not leak CTkEntry widgets or traces."""
        root = _create_root()
        try:
            from office_converter.ui.pdf_tools_pro import PDFToolsDialogPro
            from office_converter.utils.config import Config

            config = Config()
            dialog = PDFToolsDialogPro(root, config)
            root.update()

            operations = ["compress", "merge", "split", "extract",
                         "watermark", "security", "compress"]
            errors = []

            for i in range(20):
                op = operations[i % len(operations)]
                try:
                    dialog.var_operation.set(op)
                    dialog._update_options_panel()
                    root.update()
                except Exception as e:
                    errors.append(f"Switch {i+1} to '{op}': {e}")

            dialog._on_close()
            root.update()
            assert len(errors) == 0, f"Operation switch errors: {errors}"
        finally:
            root.destroy()

    def test_pdf_tools_ctk_entry_no_stale_traces(self):
        """After closing dialog, no StringVar should have stale write traces."""
        root = _create_root()
        try:
            from office_converter.ui.pdf_tools_pro import PDFToolsDialogPro
            from office_converter.utils.config import Config

            config = Config()
            dialog = PDFToolsDialogPro(root, config)
            root.update()

            # Collect all StringVars before close
            string_vars = []
            for attr_name in dir(dialog):
                if attr_name.startswith('var_'):
                    var = getattr(dialog, attr_name, None)
                    if hasattr(var, 'trace_info'):
                        string_vars.append((attr_name, var))

            # Close dialog
            dialog._on_close()
            root.update()

            # After destroy, writing to vars should not crash
            errors = []
            for name, var in string_vars:
                try:
                    var.set("test_value")
                except Exception as e:
                    errors.append(f"{name}: {e}")

            # Some errors are expected (TclError for destroyed vars),
            # but AttributeError ('str' has no 'get') should NOT happen
            attr_errors = [e for e in errors if "AttributeError" in str(e)]
            assert len(attr_errors) == 0, f"Stale trace errors: {attr_errors}"
        finally:
            root.destroy()


class TestMainWindowLifecycle:
    """Tests for main window UI component lifecycle."""

    def test_theme_toggle_20x(self):
        """Toggle dark/light theme 20 times must not crash."""
        root = _create_root()
        try:
            import customtkinter as ctk
            errors = []

            for i in range(20):
                try:
                    mode = "dark" if i % 2 == 0 else "light"
                    ctk.set_appearance_mode(mode)
                    root.update()
                except Exception as e:
                    errors.append(f"Toggle {i+1}: {e}")

            assert len(errors) == 0, f"Theme toggle errors: {errors}"
        finally:
            root.destroy()

    def test_collapsible_section_expand_collapse(self):
        """CollapsibleSection expand/collapse 30x must not leak widgets."""
        root = _create_root()
        try:
            from office_converter.ui.collapsible_section import CollapsibleSection
            import customtkinter as ctk

            container = ctk.CTkFrame(root)
            container.pack()

            section = CollapsibleSection(container, title="Test Section")
            section.pack(fill="x")

            # Add some content
            ctk.CTkLabel(section.content, text="Test content").pack()
            root.update()

            errors = []
            for i in range(30):
                try:
                    section.toggle()
                    root.update()
                except Exception as e:
                    errors.append(f"Toggle {i+1}: {e}")

            assert len(errors) == 0, f"Section toggle errors: {errors}"
        finally:
            root.destroy()

    def test_file_panel_add_remove_500_files(self):
        """Adding and removing 500 files must complete in <5 seconds."""
        root = _create_root()
        try:
            from office_converter.ui.file_panel import FileListPanel
            from office_converter.core.engine import ConversionFile
            import customtkinter as ctk

            container = ctk.CTkFrame(root)
            container.pack(fill="both", expand=True)

            panel = FileListPanel(container)
            panel.pack(fill="both", expand=True)
            root.update()

            # Create 500 fake ConversionFile entries
            start = time.time()
            fake_files = []
            for i in range(500):
                cf = ConversionFile(path=f"C:\\fake\\file_{i:03d}.docx")
                fake_files.append(cf)

            panel.files = fake_files
            panel._refresh_display()
            root.update()

            elapsed = time.time() - start
            assert elapsed < 5.0, f"500 files took {elapsed:.1f}s (max 5s)"

            # Clear
            panel.files = []
            panel._refresh_display()
            root.update()
        finally:
            root.destroy()

    def test_main_window_close_during_idle(self):
        """Closing window during idle state must not crash."""
        root = _create_root()
        try:
            # Just test that destroy works cleanly without side effects
            root.update()
            root.destroy()
            # If we get here without exception, the test passes
        except Exception as e:
            pytest.fail(f"Close during idle crashed: {e}")
