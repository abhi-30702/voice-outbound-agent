"""Unit tests for Retell AI client."""
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from app.dialing_worker.retell_client import RetellClient
from app.dialing_worker.errors import RetellAPIError


class TestRetellClientInit:
    """Tests for RetellClient initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        client = RetellClient(api_key="test-key")
        assert client.api_key == "test-key"
        assert client.base_url == "https://api.retellai.com"
        assert client.timeout == 30.0

    def test_init_with_custom_base_url(self):
        """Test initialization with custom base URL."""
        client = RetellClient(
            api_key="test-key",
            base_url="https://staging.retellai.com",
        )
        assert client.base_url == "https://staging.retellai.com"

    def test_init_with_custom_timeout(self):
        """Test initialization with custom timeout."""
        client = RetellClient(
            api_key="test-key",
            timeout=60.0,
        )
        assert client.timeout == 60.0


@pytest.mark.asyncio
class TestRetellClientCreateCall:
    """Tests for RetellClient.create_call() method."""

    async def test_create_call_success(self):
        """Test successful call creation."""
        mock_response_data = {
            "call_id": "call_123",
            "to_number": "+1234567890",
            "agent_id": "agent_456",
            "status": "initiated",
        }

        mock_http_response = MagicMock()
        mock_http_response.json.return_value = mock_response_data

        with patch("app.dialing_worker.retell_client.httpx.AsyncClient"):
            client = RetellClient(api_key="test-key")
            client.client = AsyncMock()
            client.client.post = AsyncMock(return_value=mock_http_response)

            result = await client.create_call(
                to_number="+1234567890",
                agent_id="agent_456",
            )

            assert result == mock_response_data
            client.client.post.assert_called_once()
            call_args = client.client.post.call_args
            assert call_args[0][0] == "/v1/call"
            assert call_args[1]["json"]["to_number"] == "+1234567890"
            assert call_args[1]["json"]["agent_id"] == "agent_456"

    async def test_create_call_with_dynamic_variables(self):
        """Test call creation with dynamic variables."""
        mock_response_data = {"call_id": "call_123"}
        mock_http_response = MagicMock()
        mock_http_response.json.return_value = mock_response_data

        with patch("app.dialing_worker.retell_client.httpx.AsyncClient"):
            client = RetellClient(api_key="test-key")
            client.client = AsyncMock()
            client.client.post = AsyncMock(return_value=mock_http_response)

            dynamic_vars = {"first_name": "John", "company": "Acme"}
            result = await client.create_call(
                to_number="+1234567890",
                agent_id="agent_456",
                dynamic_variables=dynamic_vars,
            )

            assert result == mock_response_data
            call_args = client.client.post.call_args
            assert call_args[1]["json"]["dynamic_variables"] == dynamic_vars

    async def test_create_call_429_retriable(self):
        """Test that 429 (rate limit) error is marked as retriable."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.json.return_value = {"message": "Rate limited"}
        mock_response.text = '{"message": "Rate limited"}'

        http_error = httpx.HTTPStatusError(
            "429 Too Many Requests",
            request=MagicMock(),
            response=mock_response,
        )

        with patch("app.dialing_worker.retell_client.httpx.AsyncClient"):
            client = RetellClient(api_key="test-key")
            client.client = AsyncMock()
            client.client.post = AsyncMock(side_effect=http_error)

            with pytest.raises(RetellAPIError) as exc_info:
                await client.create_call(
                    to_number="+1234567890",
                    agent_id="agent_456",
                )

            error = exc_info.value
            assert error.retriable is True
            assert error.status_code == 429

    async def test_create_call_500_retriable(self):
        """Test that 5xx errors are marked as retriable."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"message": "Internal server error"}
        mock_response.text = '{"message": "Internal server error"}'

        http_error = httpx.HTTPStatusError(
            "500 Internal Server Error",
            request=MagicMock(),
            response=mock_response,
        )

        with patch("app.dialing_worker.retell_client.httpx.AsyncClient"):
            client = RetellClient(api_key="test-key")
            client.client = AsyncMock()
            client.client.post = AsyncMock(side_effect=http_error)

            with pytest.raises(RetellAPIError) as exc_info:
                await client.create_call(
                    to_number="+1234567890",
                    agent_id="agent_456",
                )

            error = exc_info.value
            assert error.retriable is True
            assert error.status_code == 500

    async def test_create_call_502_retriable(self):
        """Test that 502 (bad gateway) is marked as retriable."""
        mock_response = MagicMock()
        mock_response.status_code = 502
        mock_response.json.return_value = {"message": "Bad gateway"}
        mock_response.text = '{"message": "Bad gateway"}'

        http_error = httpx.HTTPStatusError(
            "502 Bad Gateway",
            request=MagicMock(),
            response=mock_response,
        )

        with patch("app.dialing_worker.retell_client.httpx.AsyncClient"):
            client = RetellClient(api_key="test-key")
            client.client = AsyncMock()
            client.client.post = AsyncMock(side_effect=http_error)

            with pytest.raises(RetellAPIError) as exc_info:
                await client.create_call(
                    to_number="+1234567890",
                    agent_id="agent_456",
                )

            error = exc_info.value
            assert error.retriable is True

    async def test_create_call_503_retriable(self):
        """Test that 503 (service unavailable) is marked as retriable."""
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.json.return_value = {"message": "Service unavailable"}
        mock_response.text = '{"message": "Service unavailable"}'

        http_error = httpx.HTTPStatusError(
            "503 Service Unavailable",
            request=MagicMock(),
            response=mock_response,
        )

        with patch("app.dialing_worker.retell_client.httpx.AsyncClient"):
            client = RetellClient(api_key="test-key")
            client.client = AsyncMock()
            client.client.post = AsyncMock(side_effect=http_error)

            with pytest.raises(RetellAPIError) as exc_info:
                await client.create_call(
                    to_number="+1234567890",
                    agent_id="agent_456",
                )

            error = exc_info.value
            assert error.retriable is True

    async def test_create_call_504_retriable(self):
        """Test that 504 (gateway timeout) is marked as retriable."""
        mock_response = MagicMock()
        mock_response.status_code = 504
        mock_response.json.return_value = {"message": "Gateway timeout"}
        mock_response.text = '{"message": "Gateway timeout"}'

        http_error = httpx.HTTPStatusError(
            "504 Gateway Timeout",
            request=MagicMock(),
            response=mock_response,
        )

        with patch("app.dialing_worker.retell_client.httpx.AsyncClient"):
            client = RetellClient(api_key="test-key")
            client.client = AsyncMock()
            client.client.post = AsyncMock(side_effect=http_error)

            with pytest.raises(RetellAPIError) as exc_info:
                await client.create_call(
                    to_number="+1234567890",
                    agent_id="agent_456",
                )

            error = exc_info.value
            assert error.retriable is True

    async def test_create_call_400_not_retriable(self):
        """Test that 400 (bad request) is NOT retriable."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"message": "Invalid request"}
        mock_response.text = '{"message": "Invalid request"}'

        http_error = httpx.HTTPStatusError(
            "400 Bad Request",
            request=MagicMock(),
            response=mock_response,
        )

        with patch("app.dialing_worker.retell_client.httpx.AsyncClient"):
            client = RetellClient(api_key="test-key")
            client.client = AsyncMock()
            client.client.post = AsyncMock(side_effect=http_error)

            with pytest.raises(RetellAPIError) as exc_info:
                await client.create_call(
                    to_number="+1234567890",
                    agent_id="agent_456",
                )

            error = exc_info.value
            assert error.retriable is False
            assert error.status_code == 400

    async def test_create_call_401_not_retriable(self):
        """Test that 401 (unauthorized) is NOT retriable."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"message": "Unauthorized"}
        mock_response.text = '{"message": "Unauthorized"}'

        http_error = httpx.HTTPStatusError(
            "401 Unauthorized",
            request=MagicMock(),
            response=mock_response,
        )

        with patch("app.dialing_worker.retell_client.httpx.AsyncClient"):
            client = RetellClient(api_key="test-key")
            client.client = AsyncMock()
            client.client.post = AsyncMock(side_effect=http_error)

            with pytest.raises(RetellAPIError) as exc_info:
                await client.create_call(
                    to_number="+1234567890",
                    agent_id="agent_456",
                )

            error = exc_info.value
            assert error.retriable is False

    async def test_create_call_timeout_retriable(self):
        """Test that timeout errors are marked as retriable."""
        with patch("app.dialing_worker.retell_client.httpx.AsyncClient"):
            client = RetellClient(api_key="test-key")
            client.client = AsyncMock()
            client.client.post = AsyncMock(
                side_effect=httpx.TimeoutException("Request timeout")
            )

            with pytest.raises(RetellAPIError) as exc_info:
                await client.create_call(
                    to_number="+1234567890",
                    agent_id="agent_456",
                )

            error = exc_info.value
            assert error.retriable is True
            assert error.status_code is None

    async def test_create_call_network_error_retriable(self):
        """Test that network errors are marked as retriable."""
        with patch("app.dialing_worker.retell_client.httpx.AsyncClient"):
            client = RetellClient(api_key="test-key")
            client.client = AsyncMock()
            client.client.post = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )

            with pytest.raises(RetellAPIError) as exc_info:
                await client.create_call(
                    to_number="+1234567890",
                    agent_id="agent_456",
                )

            error = exc_info.value
            assert error.retriable is True
            assert error.status_code is None

    async def test_create_call_extra_kwargs(self):
        """Test that extra kwargs are passed to Retell API."""
        mock_response_data = {"call_id": "call_123"}
        mock_http_response = MagicMock()
        mock_http_response.json.return_value = mock_response_data

        with patch("app.dialing_worker.retell_client.httpx.AsyncClient"):
            client = RetellClient(api_key="test-key")
            client.client = AsyncMock()
            client.client.post = AsyncMock(return_value=mock_http_response)

            result = await client.create_call(
                to_number="+1234567890",
                agent_id="agent_456",
                language="en",
                recording_enabled=True,
            )

            assert result == mock_response_data
            call_args = client.client.post.call_args
            assert call_args[1]["json"]["language"] == "en"
            assert call_args[1]["json"]["recording_enabled"] is True
