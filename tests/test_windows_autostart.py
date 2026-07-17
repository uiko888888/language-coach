from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


class WindowsAutostartTests(unittest.TestCase):
    def test_task_recovers_and_ignores_parallel_instances(self):
        text = (SCRIPTS / "install_windows_autostart.ps1").read_text(encoding="utf-8")
        self.assertIn("-AtLogOn", text)
        self.assertIn('Delay = "PT30S"', text)
        self.assertIn("-StartWhenAvailable", text)
        self.assertIn("-MultipleInstances IgnoreNew", text)
        self.assertIn("-RestartCount 3", text)
        self.assertIn("LANGUAGE_COACH_PYTHON", text)
        self.assertIn("Start-ScheduledTask", text)
        self.assertIn("/api/health", text)
        self.assertNotIn("C:\\Users\\", text)

    def test_uninstaller_only_removes_named_task(self):
        text = (SCRIPTS / "uninstall_windows_autostart.ps1").read_text(encoding="utf-8")
        self.assertIn('taskName = "Language Coach - Daily Content"', text)
        self.assertIn("Unregister-ScheduledTask", text)
        self.assertNotIn("Stop-Process", text)
        self.assertNotIn("Get-Process", text)


if __name__ == "__main__":
    unittest.main()
