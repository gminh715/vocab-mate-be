"""Authentication request and response schemas."""

from pydantic import BaseModel, EmailStr, Field

from app.modules.users.schemas import PublicUserDto


class RegisterDto(BaseModel):
    """Payload for registering a new user account.

    Attributes:
        email (EmailStr): User's unique email address.
        password (str): Account password, minimum 8 characters.
        displayName (str): Public display name.
        preferredLanguage (str): Preferred interface language (``vi`` or ``en``).

    Example:
        >>> data = RegisterDto(
        ...     email="john@example.com",
        ...     password="strongPassword123",
        ...     displayName="John Doe",
        ...     preferredLanguage="vi",
        ... )
        >>> data.email
        'john@example.com'
    """

    email: EmailStr
    password: str = Field(min_length=8, max_length=100)
    displayName: str = Field(min_length=1, max_length=100)
    preferredLanguage: str = Field("vi", pattern="^(vi|en)$")


class LoginDto(BaseModel):
    """Payload for authenticating with email and password.

    Attributes:
        email (EmailStr): User's registered email address.
        password (str): User's password.

    Example:
        >>> data = LoginDto(email="john@example.com", password="secret")
        >>> data.email
        'john@example.com'
    """

    email: EmailStr
    password: str = Field(min_length=1)


class ChangePasswordDto(BaseModel):
    """Payload for updating an authenticated user's password.

    Attributes:
        currentPassword (str): Current active password.
        newPassword (str): New password, minimum 8 characters.

    Example:
        >>> data = ChangePasswordDto(
        ...     currentPassword="oldSecret123",
        ...     newPassword="newSecret456",
        ... )
        >>> len(data.newPassword)
        12
    """

    currentPassword: str = Field(min_length=1)
    newPassword: str = Field(min_length=8, max_length=100)


class AuthDataDto(BaseModel):
    """Authentication response data containing user info and access token.

    Attributes:
        user (PublicUserDto): The authenticated user profile.
        accessToken (str): Short-lived JWT bearer token.
    """

    user: PublicUserDto
    accessToken: str


class AccessTokenDataDto(BaseModel):
    """Response payload for token refresh operation.

    Attributes:
        accessToken (str): Refreshed short-lived JWT bearer token.
    """

    accessToken: str


class MessageDataDto(BaseModel):
    """Generic message response payload.

    Attributes:
        message (str): Descriptive status or confirmation message.
    """

    message: str
