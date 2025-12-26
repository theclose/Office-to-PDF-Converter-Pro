import os
import sys
import shutil
import tempfile
import unittest
import time
import stat

# Add c:\Auto to sys.path to support 'import office_converter...'
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir) # c:\Auto\office_converter
parent_root = os.path.dirname(project_root) # c:\Auto
if parent_root not in sys.path:
    sys.path.insert(0, parent_root)

from office_converter.core.file_tools import (
    FileToolsEngine, DuplicateFinder,
    CaseRule, ReplaceRule, RemoveAccentsRule, SequenceRule, TrimRule, AddStringRule
)

class TestFileTools(unittest.TestCase):
    def setUp(self):
        # Create a temp directory
        self.test_dir = tempfile.mkdtemp()
        self.engine = FileToolsEngine()
        self.dup_finder = DuplicateFinder()
        
    def tearDown(self):
        # Cleanup
        def on_error(func, path, exc_info):
            import stat
            if not os.access(path, os.W_OK):
                os.chmod(path, stat.S_IWRITE)
                func(path)
        
        shutil.rmtree(self.test_dir, onerror=on_error)
        
        # Clean logs
        if os.path.exists("logs/transactions"):
            for f in os.listdir("logs/transactions"):
                if f.startswith("transaction_"):
                    try:
                        os.remove(os.path.join("logs/transactions", f))
                    except OSError:
                        pass

    def create_file(self, name, content="test content"):
        path = os.path.join(self.test_dir, name)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return path

    def test_rename_rules(self):
        # Setup files
        f1 = self.create_file("  Test FILE  .txt")
        f2 = self.create_file("tài liệu.doc")
        
        # 1. Trim + Lowercase
        self.engine.add_rule(TrimRule())
        self.engine.add_rule(CaseRule("lower"))
        
        previews = self.engine.preview([f1])
        self.assertEqual(previews[0].new_filename, "test file.txt")
        
        self.engine.clear_rules()
        
        # 2. Vietnamese Accents
        self.engine.add_rule(RemoveAccentsRule())
        previews = self.engine.preview([f2])
        self.assertEqual(previews[0].new_filename, "tai lieu.doc")

    def test_sequence_rule(self):
        files = [
            self.create_file("a.txt"),
            self.create_file("b.txt"),
            self.create_file("c.txt")
        ]
        
        # Rename to File_001.txt, File_002.txt ...
        self.engine.add_rule(ReplaceRule("a", "File", ignore_case=False)) # Just to clear name mostly
        # Actually better to use specific logic, but let's try Sequence
        
        # Let's clean names first strictly
        # We can't clear functionality easily with current rules without "Set Name", 
        # but we can Append/Prepend.
        # Let's just test Sequence appending
        
        self.engine.clear_rules()
        self.engine.add_rule(SequenceRule(start=1, padding=2, at_start=True))
        
        previews = self.engine.preview(files)
        # 01_a.txt, 02_b.txt
        self.assertEqual(previews[0].new_filename, "01_a.txt")
        self.assertEqual(previews[1].new_filename, "02_b.txt")

    def test_undo_system(self):
        f1 = self.create_file("old_name.txt")
        
        # Execute Rename
        self.engine.add_rule(ReplaceRule("old", "new"))
        self.engine.execute([f1])
        
        new_path = os.path.join(self.test_dir, "new_name.txt")
        self.assertTrue(os.path.exists(new_path))
        self.assertFalse(os.path.exists(f1))
        
        # Execute Undo
        self.engine.undo_last_transaction()
        
        self.assertTrue(os.path.exists(f1))
        self.assertFalse(os.path.exists(new_path))

    def test_duplicate_finder(self):
        # Create duplicates
        content_a = "content AAA"
        content_b = "content BBB"
        
        f1 = self.create_file("file1.txt", content_a)
        f2 = self.create_file("file2.txt", content_a) # Duplicate of 1
        f3 = self.create_file("file3.txt", content_b) # Different
        f4 = self.create_file("copy_file1.txt", content_a) # Duplicate of 1
        
        groups = self.dup_finder.find_duplicates([self.test_dir])
        
        # Should find 1 group with 3 files (f1, f2, f4)
        if len(groups) != 1:
            # Maybe size grouping didn't work?
            pass
            
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0].files), 3)
        self.assertEqual(groups[0].size, len(content_a))
        
        # Verify f3 is not in
        all_dupes = groups[0].files
        self.assertNotIn(f3, all_dupes)

    def test_empty_folder_cleaner(self):
        from office_converter.core.file_tools import EmptyFolderCleaner
        cleaner = EmptyFolderCleaner()
        
        # Structure:
        # temp/
        #   empty1/
        #   not_empty/file.txt
        #   nested/empty2/
        
        empty1 = os.path.join(self.test_dir, "empty1")
        os.makedirs(empty1)
        
        not_empty = os.path.join(self.test_dir, "not_empty")
        os.makedirs(not_empty)
        self.create_file("not_empty/file.txt")
        
        nested_empty = os.path.join(self.test_dir, "nested", "empty2")
        os.makedirs(nested_empty)
        
        # Find
        found = cleaner.find_empty_folders([self.test_dir])
        self.assertIn(empty1, found)
        self.assertIn(nested_empty, found)
        self.assertNotIn(not_empty, found)
        
        # Delete
        results = cleaner.delete_folders(found)
        self.assertTrue(all(r[1] for r in results))
        self.assertFalse(os.path.exists(empty1))
        self.assertFalse(os.path.exists(nested_empty))
        self.assertTrue(os.path.exists(not_empty))

    def test_attribute_manager(self):
        from office_converter.core.file_tools import AttributeManager
        mgr = AttributeManager()
        
        f1 = self.create_file("attrib_test.txt")
        
        # Change mtime to 1000 seconds ago
        new_mtime = time.time() - 1000
        ok, msg = mgr.set_dates(f1, modified=new_mtime)
        
        self.assertTrue(ok)
        curr_mtime = os.stat(f1).st_mtime
        self.assertAlmostEqual(curr_mtime, new_mtime, delta=2)
        
        # Test Read-only (chmod)
        ok, msg = mgr.set_attributes(f1, readonly=True)
        self.assertTrue(ok)
        
        # Verify read-only
        mode = os.stat(f1).st_mode
        self.assertFalse(mode & stat.S_IWRITE)
        
        # Revert
        mgr.set_attributes(f1, readonly=False)
        mode = os.stat(f1).st_mode
        self.assertTrue(mode & stat.S_IWRITE)

if __name__ == '__main__':
    unittest.main()
