from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field
from pydantic_extra_types.country import CountryAlpha3

from app.core.enum import OtpPurpose


class AuthBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class TokenData(AuthBase):
    user_id: UUID
    session_id: UUID
    organization_id: UUID | None


class Token(AuthBase):
    access_token: str
    token_type: str = "bearer"


class ReactivateAccount(AuthBase):
    email: EmailStr


class EmailVerify(AuthBase):
    email: EmailStr
    otp_code: str
    otp_purpose: OtpPurpose


class ResendOtp(AuthBase):
    email: EmailStr
    otp_purpose: OtpPurpose


class SignUp(AuthBase):
    organization_name: str
    organization_country: CountryAlpha3


class EmailSignUp(SignUp):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class GoogleSignUp(SignUp):
    pass


class EmailLogin(AuthBase):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class SignUpResponse(BaseModel):
    pass


class OtpResendResponse(BaseModel):
    pass


class LogoutResponse(BaseModel):
    pass
