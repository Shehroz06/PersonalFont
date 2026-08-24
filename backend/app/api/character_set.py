"""Exposes the character set's canonical order (spec §3) so a client can
show "write these characters, in this order" before any job exists yet —
GET /jobs/{id}/rewrite-list needs a completed job to filter down to just
the invalid ones, but a brand-new freeform-only submission (see
app.services.freeform_job) has no job to ask yet.

Single source of truth stays app.template_gen.character_set — this just
serializes it, rather than the frontend hardcoding its own copy that
could drift out of sync.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.schemas import RewriteCharacter
from app.template_gen.character_set import get_character_set

router = APIRouter(prefix="/api/character-set", tags=["character-set"])


@router.get("", response_model=list[RewriteCharacter])
def list_character_set() -> list[RewriteCharacter]:
    return [RewriteCharacter(character_id=spec.character_id, character=spec.character) for spec in get_character_set()]
