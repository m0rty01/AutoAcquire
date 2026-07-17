import os
import uuid
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(Path(__file__).parent / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


def clean(doc: dict) -> dict:
    """Strip Mongo _id so documents are JSON serializable."""
    if doc is None:
        return None
    doc.pop("_id", None)
    return doc


async def audit(organization_id, actor_type, actor_id, entity_type, entity_id,
                action, previous_value=None, new_value=None, metadata=None):
    await db.audit_events.insert_one({
        "id": new_id(),
        "organization_id": organization_id,
        "actor_type": actor_type,
        "actor_id": actor_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "action": action,
        "previous_value": previous_value,
        "new_value": new_value,
        "metadata": metadata or {},
        "created_at": now_iso(),
    })


async def emit_event(organization_id, event_type, entity_type, entity_id, payload=None):
    await db.domain_events.insert_one({
        "id": new_id(),
        "organization_id": organization_id,
        "event_type": event_type,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "payload": payload or {},
        "processing_status": "recorded",
        "retry_count": 0,
        "created_at": now_iso(),
    })


async def notify(organization_id, recipient_type, recipient_id, channel, template, payload):
    """Simulated notification: stored + logged (no real email in MVP)."""
    doc = {
        "id": new_id(),
        "organization_id": organization_id,
        "recipient_type": recipient_type,
        "recipient_id": recipient_id,
        "channel": channel,
        "template": template,
        "payload": payload,
        "status": "sent",
        "sent_at": now_iso(),
        "created_at": now_iso(),
    }
    await db.notifications.insert_one(doc)
    print(f"[EMAIL SIMULATED] to={recipient_id} template={template} payload={payload}")
    return doc
