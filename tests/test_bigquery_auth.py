"""Tests for BigQuery authentication methods."""

import os
import tempfile
from unittest.mock import Mock, patch

import pytest
from omop_mcp.backends.bigquery import BigQueryBackend
from omop_mcp.config import OMOPConfig


class TestBigQueryAuthentication:
    """Test BigQuery authentication methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_project_id = "test-project"
        self.test_dataset_id = "test_dataset"

        # Mock config
        self.mock_config = Mock(spec=OMOPConfig)
        self.mock_config.bigquery_project_id = self.test_project_id
        self.mock_config.bigquery_dataset_id = self.test_dataset_id
        self.mock_config.bigquery_credentials_path = None

    @patch("omop_mcp.backends.bigquery.config")
    @patch("omop_mcp.backends.bigquery.bigquery")
    def test_service_account_authentication(self, mock_bigquery, mock_config):
        """Test service account authentication."""
        # Setup
        mock_config.bigquery_project_id = self.test_project_id
        mock_config.bigquery_dataset_id = self.test_dataset_id
        mock_config.bigquery_credentials_path = "/path/to/service-account.json"

        mock_client = Mock()
        mock_bigquery.Client.from_service_account_json.return_value = mock_client

        # Test
        backend = BigQueryBackend()

        with patch("os.path.exists", return_value=True):
            client = backend._get_client()

        # Verify
        mock_bigquery.Client.from_service_account_json.assert_called_once_with(
            "/path/to/service-account.json", project=self.test_project_id
        )
        assert client == mock_client

    @patch("omop_mcp.backends.bigquery.config")
    @patch("omop_mcp.backends.bigquery.bigquery")
    @patch("omop_mcp.backends.bigquery.google_auth_default")
    def test_adc_authentication_with_project(self, mock_auth_default, mock_bigquery, mock_config):
        """Test ADC authentication with project ID from config."""
        # Setup
        mock_config.bigquery_project_id = self.test_project_id
        mock_config.bigquery_dataset_id = self.test_dataset_id
        mock_config.bigquery_credentials_path = None

        mock_credentials = Mock()
        mock_detected_project = "detected-project"
        mock_auth_default.return_value = (mock_credentials, mock_detected_project)

        mock_client = Mock()
        mock_bigquery.Client.return_value = mock_client

        # Test
        backend = BigQueryBackend()
        client = backend._get_client()

        # Verify
        mock_auth_default.assert_called_once()
        mock_bigquery.Client.assert_called_once_with(project=self.test_project_id)
        assert client == mock_client

    @patch("omop_mcp.backends.bigquery.config")
    @patch("omop_mcp.backends.bigquery.bigquery")
    @patch("omop_mcp.backends.bigquery.google_auth_default")
    def test_adc_authentication_with_detected_project(
        self, mock_auth_default, mock_bigquery, mock_config
    ):
        """Test ADC authentication with project ID from ADC."""
        # Setup
        mock_config.bigquery_project_id = None  # No project in config
        mock_config.bigquery_dataset_id = self.test_dataset_id
        mock_config.bigquery_credentials_path = None

        mock_credentials = Mock()
        mock_detected_project = "detected-project"
        mock_auth_default.return_value = (mock_credentials, mock_detected_project)

        mock_client = Mock()
        mock_bigquery.Client.return_value = mock_client

        # Test
        backend = BigQueryBackend()
        client = backend._get_client()

        # Verify
        mock_auth_default.assert_called_once()
        mock_bigquery.Client.assert_called_once_with(project="detected-project")
        assert client == mock_client

    @patch("omop_mcp.backends.bigquery.config")
    @patch("omop_mcp.backends.bigquery.google_auth_default")
    def test_adc_authentication_failure(self, mock_auth_default, mock_config):
        """Test ADC authentication failure."""
        # Setup
        mock_config.bigquery_project_id = None
        mock_config.bigquery_dataset_id = self.test_dataset_id
        mock_config.bigquery_credentials_path = None

        mock_auth_default.side_effect = Exception("ADC not available")

        # Test
        backend = BigQueryBackend()

        with pytest.raises(
            ValueError, match="Failed to authenticate with Application Default Credentials"
        ):
            backend._get_client()

    @patch("omop_mcp.backends.bigquery.config")
    @patch("omop_mcp.backends.bigquery.google_auth_default")
    def test_no_project_id_available(self, mock_auth_default, mock_config):
        """Test when no project ID is available from config or ADC."""
        # Setup
        mock_config.bigquery_project_id = None
        mock_config.bigquery_dataset_id = self.test_dataset_id
        mock_config.bigquery_credentials_path = None

        mock_credentials = Mock()
        mock_auth_default.return_value = (mock_credentials, None)  # No detected project

        # Test
        backend = BigQueryBackend()

        with pytest.raises(
            ValueError, match="Failed to authenticate with Application Default Credentials"
        ):
            backend._get_client()

    @patch("omop_mcp.backends.bigquery.config")
    @patch("omop_mcp.backends.bigquery.bigquery")
    def test_service_account_file_not_exists(self, mock_bigquery, mock_config):
        """Test service account authentication when file doesn't exist."""
        # Setup
        mock_config.bigquery_project_id = self.test_project_id
        mock_config.bigquery_dataset_id = self.test_dataset_id
        mock_config.bigquery_credentials_path = "/path/to/nonexistent.json"

        mock_credentials = Mock()
        mock_detected_project = "detected-project"

        mock_client = Mock()
        mock_bigquery.Client.return_value = mock_client

        # Test
        backend = BigQueryBackend()

        with patch(
            "omop_mcp.backends.bigquery.google_auth_default",
            return_value=(mock_credentials, mock_detected_project),
        ):
            with patch("os.path.exists", return_value=False):
                client = backend._get_client()

        # Verify it falls back to ADC
        mock_bigquery.Client.assert_called_once_with(project=self.test_project_id)
        assert client == mock_client

    @patch("omop_mcp.backends.bigquery.config")
    @patch("omop_mcp.backends.bigquery.bigquery")
    def test_credentials_path_empty_string(self, mock_bigquery, mock_config):
        """Test when credentials path is empty string."""
        # Setup
        mock_config.bigquery_project_id = self.test_project_id
        mock_config.bigquery_dataset_id = self.test_dataset_id
        mock_config.bigquery_credentials_path = ""  # Empty string

        mock_credentials = Mock()
        mock_detected_project = "detected-project"

        mock_client = Mock()
        mock_bigquery.Client.return_value = mock_client

        # Test
        backend = BigQueryBackend()

        with patch(
            "omop_mcp.backends.bigquery.google_auth_default",
            return_value=(mock_credentials, mock_detected_project),
        ):
            client = backend._get_client()

        # Verify it falls back to ADC
        mock_bigquery.Client.assert_called_once_with(project=self.test_project_id)
        assert client == mock_client

    @patch("omop_mcp.backends.bigquery.config")
    @patch("omop_mcp.backends.bigquery.bigquery")
    async def test_validate_sql_uses_authentication(self, mock_bigquery, mock_config):
        """Test that validate_sql uses the authentication method."""
        # Setup
        mock_config.bigquery_project_id = self.test_project_id
        mock_config.bigquery_dataset_id = self.test_dataset_id
        mock_config.bigquery_credentials_path = None

        mock_client = Mock()
        mock_query_job = Mock()
        mock_query_job.total_bytes_processed = 1000000
        mock_client.query.return_value = mock_query_job

        mock_bigquery.Client.return_value = mock_client
        mock_bigquery.QueryJobConfig.return_value = Mock()

        # Test
        backend = BigQueryBackend()

        with patch(
            "omop_mcp.backends.bigquery.google_auth_default",
            return_value=(Mock(), "detected-project"),
        ):
            result = await backend.validate_sql("SELECT 1")

        # Verify authentication was used
        mock_bigquery.Client.assert_called_once_with(project=self.test_project_id)
        mock_client.query.assert_called_once()
        assert result.valid is True
        assert result.estimated_bytes == 1000000

    @patch("omop_mcp.backends.bigquery.config")
    @patch("omop_mcp.backends.bigquery.bigquery")
    async def test_execute_query_uses_authentication(self, mock_bigquery, mock_config):
        """Test that execute_query uses the authentication method."""
        # Setup
        mock_config.bigquery_project_id = self.test_project_id
        mock_config.bigquery_dataset_id = self.test_dataset_id
        mock_config.bigquery_credentials_path = None
        mock_config.query_timeout_sec = 30

        mock_client = Mock()
        mock_query_job = Mock()
        mock_results = [{"col1": "value1"}, {"col1": "value2"}]
        mock_query_job.result.return_value = mock_results
        mock_client.query.return_value = mock_query_job

        mock_bigquery.Client.return_value = mock_client

        # Test
        backend = BigQueryBackend()

        with patch(
            "omop_mcp.backends.bigquery.google_auth_default",
            return_value=(Mock(), "detected-project"),
        ):
            result = await backend.execute_query("SELECT 1")

        # Verify authentication was used
        mock_bigquery.Client.assert_called_once_with(project=self.test_project_id)
        mock_client.query.assert_called_once()
        assert result == mock_results


class TestBigQueryAuthenticationIntegration:
    """Integration tests for BigQuery authentication."""

    def test_authentication_priority_service_account_first(self):
        """Test that service account takes priority over ADC."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"type": "service_account", "project_id": "test-project"}')
            temp_file = f.name

        try:
            with patch("omop_mcp.backends.bigquery.config") as mock_config:
                mock_config.bigquery_project_id = "test-project"
                mock_config.bigquery_dataset_id = "test_dataset"
                mock_config.bigquery_credentials_path = temp_file

                backend = BigQueryBackend()

                with patch("omop_mcp.backends.bigquery.bigquery") as mock_bq:
                    mock_client = Mock()
                    mock_bq.Client.from_service_account_json.return_value = mock_client

                    client = backend._get_client()

                    # Verify service account method was called, not ADC
                    mock_bq.Client.from_service_account_json.assert_called_once()
                    mock_bq.Client.assert_not_called()
                    assert client == mock_client
        finally:
            os.unlink(temp_file)

    def test_authentication_priority_adc_fallback(self):
        """Test that ADC is used when service account file doesn't exist."""
        with patch("omop_mcp.backends.bigquery.config") as mock_config:
            mock_config.bigquery_project_id = "test-project"
            mock_config.bigquery_dataset_id = "test_dataset"
            mock_config.bigquery_credentials_path = "/nonexistent/path.json"

            backend = BigQueryBackend()

            with patch("omop_mcp.backends.bigquery.bigquery") as mock_bq:
                with patch("omop_mcp.backends.bigquery.google_auth_default") as mock_auth:
                    mock_client = Mock()
                    mock_bq.Client.return_value = mock_client
                    mock_auth.return_value = (Mock(), "detected-project")

                    client = backend._get_client()

                    # Verify ADC method was called, not service account
                    mock_bq.Client.from_service_account_json.assert_not_called()
                    mock_bq.Client.assert_called_once_with(project="test-project")
                    assert client == mock_client
