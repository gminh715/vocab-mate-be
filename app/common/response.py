"""Standardized API response envelopes conforming to the platform-wide contract."""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")
M = TypeVar("M")


class BaseResponse(BaseModel, Generic[T]):
    """Standard success response envelope enclosing data payload.

    Attributes:
        success (bool): Indicates successful API response execution (always True).
        data (T): Strongly-typed payload data.
    """

    success: bool = True
    data: T


class ResponseWithMeta(BaseResponse[T], Generic[T, M]):
    """Response envelope enclosing data payload alongside pagination/cursor metadata.

    Attributes:
        success (bool): Indicates successful API response execution (always True).
        data (T): Strongly-typed payload data.
        meta (M): Strongly-typed pagination or query metadata.
    """

    meta: M


def api_response(data: T, meta: M | None = None) -> BaseResponse[T] | ResponseWithMeta[T, M]:
    """Wraps data payload and optional metadata into a standard envelope response.

    Args:
        data (T): Payload data to enclose.
        meta (M | None, optional): Optional pagination metadata. Defaults to None.

    Returns:
        BaseResponse[T] | ResponseWithMeta[T, M]: Formatted envelope model instance.

    Example:
        >>> resp = api_response({"item": "apple"})
        >>> resp.success
        True
        >>> resp.data
        {'item': 'apple'}
    """
    if meta is not None:
        return ResponseWithMeta(success=True, data=data, meta=meta)
    return BaseResponse(success=True, data=data)
