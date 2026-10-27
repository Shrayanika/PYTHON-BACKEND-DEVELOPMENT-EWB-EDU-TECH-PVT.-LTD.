"""Pydantic models: request validation and response shapes."""
import re
from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

PHONE_RE = re.compile(r"^\+?[0-9][0-9\s\-]{6,18}[0-9]$")


class StudentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    date_of_birth: date
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    course: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = Field(None, max_length=255)
    enrollment_date: Optional[date] = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be blank")
        return v

    @field_validator("date_of_birth")
    @classmethod
    def dob_in_past(cls, v: date) -> date:
        if v >= date.today():
            raise ValueError("date_of_birth must be in the past")
        return v

    @field_validator("phone")
    @classmethod
    def phone_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not PHONE_RE.match(v):
            raise ValueError("phone must be 8-20 digits, optionally starting with + (spaces/dashes allowed)")
        return v


class StudentCreate(StudentBase):
    @model_validator(mode="after")
    def need_contact(self):
        if not self.email and not self.phone:
            raise ValueError("provide at least one contact: email or phone")
        return self


class StudentUpdate(BaseModel):
    """All fields optional so PUT/PATCH can send only what changes."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    date_of_birth: Optional[date] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    course: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = Field(None, max_length=255)
    enrollment_date: Optional[date] = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("name must not be blank")
        return v

    @field_validator("date_of_birth")
    @classmethod
    def dob_in_past(cls, v: Optional[date]) -> Optional[date]:
        if v is not None and v >= date.today():
            raise ValueError("date_of_birth must be in the past")
        return v

    @field_validator("phone")
    @classmethod
    def phone_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not PHONE_RE.match(v):
            raise ValueError("phone must be 8-20 digits, optionally starting with + (spaces/dashes allowed)")
        return v

    @model_validator(mode="after")
    def required_not_null(self):
        # name and date_of_birth are NOT NULL in the DB: they may be omitted but not set to null
        for f in ("name", "date_of_birth"):
            if f in self.model_fields_set and getattr(self, f) is None:
                raise ValueError(f"{f} cannot be null")
        return self


class StudentOut(StudentBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)


class AskResponse(BaseModel):
    question: str
    answer: str
    intent: str
    records_used: int
    model: str
