"""Async HTTP client wrapper for Retell AI API."""
import json
from typing import Any, Optional

import httpx

from app.dialing_worker.errors import RetellAPIError


class RetellClient:
    """Async HTTP client for Retell AI API.

    Handles request/response, error classification (retriable vs permanent),
    and exponential backoff retry logic.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.retellai.com",
        timeout: float = 30.0,
    ):
        """Initialize RetellClient.

        Args:
            api_key: Retell AI API key
            base_url: Base URL for Retell API (default: production endpoint)
            timeout: HTTP request timeout in seconds
        """
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )

    async def create_call(
        self,
        to_number: str,
        agent_id: str,
        dynamic_variables: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create an outbound call via Retell AI.

        Args:
            to_number: Destination phone number (E.164 format)
            agent_id: Retell AI agent ID
            dynamic_variables: Optional dynamic variables for the agent
            **kwargs: Additional parameters to pass to Retell API

        Returns:
            Call creation response from Retell API (contains call_id, etc.)

        Raises:
            RetellAPIError: If API request fails
                - retriable=True for 429, 5xx, timeout
                - retriable=False for 4xx (except 429)
        """
        payload = {
            "to_number": to_number,
            "agent_id": agent_id,
        }
        if dynamic_variables:
            payload["dynamic_variables"] = dynamic_variables
        payload.update(kwargs)

        try:
            response = await self.client.post(
                "/v1/call",
                json=payload,
            )
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException as e:
            raise RetellAPIError(
                message=f"Retell API timeout: {str(e)}",
                retriable=True,
                status_code=None,
            ) from e
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            # Determine if error is retriable
            retriable = status_code in (429, 500, 502, 503, 504)

            try:
                error_body = e.response.json()
                error_msg = error_body.get("message", str(error_body))
            except (json.JSONDecodeError, ValueError):
                error_msg = e.response.text or str(e)

            raise RetellAPIError(
                message=f"Retell API error ({status_code}): {error_msg}",
                retriable=retriable,
                status_code=status_code,
            ) from e
        except httpx.RequestError as e:
            # Network errors (connection refused, DNS failure, etc.) are retriable
            raise RetellAPIError(
                message=f"Retell API request failed: {str(e)}",
                retriable=True,
                status_code=None,
            ) from e

    async def create_agent(self, payload: dict) -> dict[str, Any]:
        """Create an agent via Retell AI.

        Args:
            payload: Agent configuration payload

        Returns:
            Agent creation response from Retell API (contains agent_id, etc.)

        Raises:
            RetellAPIError: If API request fails
                - retriable=True for 429, 5xx, timeout
                - retriable=False for 4xx (except 429)
        """
        try:
            response = await self.client.post("/v2/create-agent", json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException as e:
            raise RetellAPIError(
                message=f"Retell API timeout: {str(e)}",
                retriable=True,
                status_code=None,
            ) from e
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            retriable = status_code in (429, 500, 502, 503, 504)
            try:
                error_body = e.response.json()
                error_msg = error_body.get("message", str(error_body))
            except (json.JSONDecodeError, ValueError):
                error_msg = e.response.text or str(e)
            raise RetellAPIError(
                message=f"Retell API error ({status_code}): {error_msg}",
                retriable=retriable,
                status_code=status_code,
            ) from e
        except httpx.RequestError as e:
            raise RetellAPIError(
                message=f"Retell API request failed: {str(e)}",
                retriable=True,
                status_code=None,
            ) from e

    async def update_agent(self, agent_id: str, payload: dict) -> dict[str, Any]:
        """Update an agent via Retell AI.

        Args:
            agent_id: Retell AI agent ID
            payload: Agent configuration payload (fields to update)

        Returns:
            Agent update response from Retell API

        Raises:
            RetellAPIError: If API request fails
                - retriable=True for 429, 5xx, timeout
                - retriable=False for 4xx (except 429)
        """
        try:
            response = await self.client.patch(
                f"/v2/update-agent/{agent_id}", json=payload
            )
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException as e:
            raise RetellAPIError(
                message=f"Retell API timeout: {str(e)}",
                retriable=True,
                status_code=None,
            ) from e
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            retriable = status_code in (429, 500, 502, 503, 504)
            try:
                error_body = e.response.json()
                error_msg = error_body.get("message", str(error_body))
            except (json.JSONDecodeError, ValueError):
                error_msg = e.response.text or str(e)
            raise RetellAPIError(
                message=f"Retell API error ({status_code}): {error_msg}",
                retriable=retriable,
                status_code=status_code,
            ) from e
        except httpx.RequestError as e:
            raise RetellAPIError(
                message=f"Retell API request failed: {str(e)}",
                retriable=True,
                status_code=None,
            ) from e

    async def close(self) -> None:
        """Close the HTTP client connection."""
        await self.client.aclose()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
