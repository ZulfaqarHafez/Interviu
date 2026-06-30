from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ._common import utc_now


class ProductReviewer(BaseModel):
    key: str
    name: str
    status: Literal["pass", "warn", "wait"]
    label: str
    summary: str
    evidence: list[str] = Field(default_factory=list)
    next_step: str | None = None
    sprite: str = "candidate-audit"


class ProductReview(BaseModel):
    schema_: Literal["assay.product_review.v1"] = Field(default="assay.product_review.v1", alias="schema")
    run_id: str
    generated_at: datetime = Field(default_factory=utc_now)
    reviewers: list[ProductReviewer]

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)
