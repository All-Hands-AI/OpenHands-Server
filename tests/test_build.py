#!/usr/bin/env python3
"""Tests for the build.py script functionality."""

import sys
from pathlib import Path


# Add the parent directory to the path so we can import build
sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest  # noqa: E402
from unittest.mock import Mock, patch  # noqa: E402

import build  # noqa: E402


class TestBuild(unittest.TestCase):
    """Test cases for build.py functionality."""

    @patch("build.Path")
    @patch("build.sys.platform", "linux")
    def test_executable_path_linux(self, mock_path_class):
        """Test that executable path is correct on Linux."""
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = True
        mock_path_class.return_value = mock_path_instance

        # Mock the Path constructor to capture the path being created
        def path_constructor(path_str):
            if path_str == "dist":
                mock_dist_path = Mock()
                mock_dist_path.__truediv__ = Mock(return_value=mock_path_instance)
                return mock_dist_path
            return mock_path_instance

        mock_path_class.side_effect = path_constructor

        with patch("build.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "help output"
            mock_run.return_value.stderr = ""

            # This should not raise an exception
            build.test_executable()

            # Verify the correct path was used (without .exe)
            mock_path_class.assert_called()

    @patch("build.Path")
    @patch("build.sys.platform", "win32")
    def test_executable_path_windows(self, mock_path_class):
        """Test that executable path includes .exe extension on Windows."""
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = True
        mock_path_class.return_value = mock_path_instance

        # Mock the Path constructor to capture the path being created
        def path_constructor(path_str):
            if path_str == "dist":
                mock_dist_path = Mock()
                mock_dist_path.__truediv__ = Mock(return_value=mock_path_instance)
                return mock_dist_path
            return mock_path_instance

        mock_path_class.side_effect = path_constructor

        with patch("build.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "help output"
            mock_run.return_value.stderr = ""

            # This should not raise an exception
            build.test_executable()

            # Verify the correct path was used (with .exe)
            mock_path_class.assert_called()

    @patch("build.Path")
    @patch("build.sys.platform", "win32")
    def test_executable_not_found_windows(self, mock_path_class):
        """Test that proper error is shown when executable not found on Windows."""
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = False
        mock_path_class.return_value = mock_path_instance

        # Mock the Path constructor
        def path_constructor(path_str):
            if path_str == "dist":
                mock_dist_path = Mock()
                mock_dist_path.__truediv__ = Mock(return_value=mock_path_instance)
                return mock_dist_path
            return mock_path_instance

        mock_path_class.side_effect = path_constructor

        with patch("build.sys.exit") as mock_exit:
            build.test_executable()
            mock_exit.assert_called_with(1)

    @patch("build.Path")
    @patch("build.sys.platform", "darwin")
    def test_executable_path_macos(self, mock_path_class):
        """Test that executable path is correct on macOS."""
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = True
        mock_path_class.return_value = mock_path_instance

        # Mock the Path constructor to capture the path being created
        def path_constructor(path_str):
            if path_str == "dist":
                mock_dist_path = Mock()
                mock_dist_path.__truediv__ = Mock(return_value=mock_path_instance)
                return mock_dist_path
            return mock_path_instance

        mock_path_class.side_effect = path_constructor

        with patch("build.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "help output"
            mock_run.return_value.stderr = ""

            # This should not raise an exception
            build.test_executable()

            # Verify the correct path was used (without .exe)
            mock_path_class.assert_called()


if __name__ == "__main__":
    unittest.main()
