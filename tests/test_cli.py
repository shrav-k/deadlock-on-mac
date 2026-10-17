import contextlib
import io
import unittest

from deadlock_mac.cli import main


class CLIHelpTests(unittest.TestCase):
    def test_help_formats_all_command_descriptions(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as result:
            main(["--help"])
        self.assertEqual(result.exception.code, 0)
        self.assertIn("native-rendering", output.getvalue())
        self.assertIn("100%", output.getvalue())
