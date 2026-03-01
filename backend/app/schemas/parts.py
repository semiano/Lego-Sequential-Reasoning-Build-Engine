from pydantic import BaseModel


class PartDetailOut(BaseModel):
    part_id: str
    name: str | None
    raw_header: str | None
    file_path: str | None
    exists: bool
