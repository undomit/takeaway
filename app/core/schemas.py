"""Shared request primitives, independent of feature modules."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

PositiveId = Annotated[int, Field(ge=1, le=9223372036854775807)]
JsonId = Annotated[PositiveId, Field(strict=True)]


class NoQueryParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")
