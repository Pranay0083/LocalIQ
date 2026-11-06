from datetime import datetime, timezone
from typing import Annotated, Any, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from .config import settings

client = AsyncIOMotorClient(settings.mongo_url)
db = client[settings.db_name]


def _to_str_id(v: Any) -> Any:
    if isinstance(v, ObjectId):
        return str(v)
    return v


PyObjectId = Annotated[str, BeforeValidator(_to_str_id)]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: Optional[datetime] = None) -> str:
    return (dt or utcnow()).isoformat()


class BaseDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    id: Optional[PyObjectId] = Field(default=None, alias="_id")

    def to_mongo(self) -> dict:
        data = self.model_dump(by_alias=True, exclude_none=True)
        data.pop("_id", None)
        return data

    @classmethod
    def from_mongo(cls, doc: Optional[dict]):
        if not doc:
            return None
        return cls.model_validate(doc)


async def ensure_indexes():
    await db.users.create_index("email", unique=True)
    await db.login_attempts.create_index("identifier")
    await db.dossiers.create_index("locality_slug", unique=True)
    await db.reports.create_index([("user_id", 1), ("created_at", -1)])
    await db.reports.create_index([("user_id", 1), ("locality_slug", 1), ("persona_key", 1)])
    await db.jobs.create_index([("user_id", 1), ("created_at", -1)])
    await db.posts.create_index([("locality_slug", 1), ("created_at", -1)])
    await db.votes.create_index([("post_id", 1), ("user_id", 1)], unique=True)
    await db.chat_messages.create_index([("report_id", 1), ("created_at", 1)])
    await db.traces.create_index([("job_id", 1)])
    await db.orders.create_index("razorpay_order_id")
    await db.contrib_links.create_index("token", unique=True)
    await db.contrib_links.create_index([("created_by", 1), ("locality_slug", 1)])
    await db.posts.create_index([("link_token", 1), ("day", 1)])
