from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ._common import (
    _MAX_CHECK_TERMS,
    _MAX_CHECK_TEXT_CHARS,
    _MAX_PROMPT_CHARS,
    _MAX_RUBRIC_CHARS,
    _PUBLIC_ID_PATTERN,
)


class ExpectedCheck(BaseModel):
    id: str = Field(pattern=_PUBLIC_ID_PATTERN)
    label: str = Field(min_length=1, max_length=_MAX_CHECK_TEXT_CHARS)
    keywords: list[str] = Field(default_factory=list, max_length=_MAX_CHECK_TERMS)
    forbidden: list[str] = Field(default_factory=list, max_length=_MAX_CHECK_TERMS)
    weight: float = Field(default=1.0, gt=0, le=5.0)

    model_config = ConfigDict(extra="forbid")

    @field_validator("keywords", "forbidden")
    @classmethod
    def _clean_terms(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item and item.strip()]
        for item in cleaned:
            if len(item) > _MAX_CHECK_TEXT_CHARS:
                raise ValueError(f"check term exceeds {_MAX_CHECK_TEXT_CHARS} characters")
        return cleaned


class ExamItem(BaseModel):
    id: str = Field(pattern=_PUBLIC_ID_PATTERN)
    competency: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,119}$")
    prompt: str = Field(min_length=1, max_length=_MAX_PROMPT_CHARS)
    held_out_prompt: str = Field(min_length=1, max_length=_MAX_PROMPT_CHARS)
    rubric: str = Field(min_length=1, max_length=_MAX_RUBRIC_CHARS)
    expected_checks: list[ExpectedCheck] = Field(min_length=1, max_length=20)
    difficulty: Literal["intro", "standard", "adversarial"] = "standard"
    counterfactual_group: str | None = None

    model_config = ConfigDict(extra="forbid")


class ExamPack(BaseModel):
    schema_: Literal["assay.exam_pack.v1"] = Field(default="assay.exam_pack.v1", alias="schema")
    id: str = Field(pattern=_PUBLIC_ID_PATTERN)
    name: str = Field(min_length=1, max_length=160)
    simulator_model: str = Field(min_length=1, max_length=120)
    items: list[ExamItem] = Field(min_length=1, max_length=100)

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True, extra="forbid")


class ExamPackFileExport(BaseModel):
    pack_id: str
    directory: str
    files: dict[str, str]
    row_count: int
    suggested_commands: list[str]
