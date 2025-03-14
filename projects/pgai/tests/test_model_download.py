import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner


def test_download_models():
    """Test that download-models command works correctly."""
    # Create a temporary directory for the test
    with patch("docling.utils.model_downloader.download_models") as mock_download:
        from pgai.cli import download_models
        from pgai.vectorizer.parsing import DOCLING_CACHE_DIR

        # Run the CLI command
        result = CliRunner().invoke(download_models)

        # Check that the command executed successfully
        assert result.exit_code == 0

        # Verify that download_models was called with the correct parameters
        mock_download.assert_called_once_with(
            progress=True,
            output_dir=DOCLING_CACHE_DIR,
        )


@pytest.mark.skip("Integration test")
def test_download_models_integration():
    """Integration test for the download-models command.

    This test actually downloads the models (to a temporary directory)
    and verifies that files were created.
    """

    # Create a temporary directory for the test
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Mock the DOCLING_CACHE_DIR to use our temporary directory
        with patch("pgai.vectorizer.parsing.DOCLING_CACHE_DIR", temp_path):
            from pgai.cli import download_models

            # Ensure directory is empty
            if temp_path.exists():
                for item in temp_path.iterdir():
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)

            # Run the CLI command
            result = CliRunner().invoke(download_models)

            # Check that the command executed successfully
            assert result.exit_code == 0

            # Verify that files were downloaded (directory should no longer be empty)
            assert any(
                temp_path.iterdir()
            ), "No files were downloaded to the models directory"
