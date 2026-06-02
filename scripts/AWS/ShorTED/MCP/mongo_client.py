"""
Async MongoDB client for the ShorTED MCP Server.

Uses motor (async MongoDB driver) so it does not block the FastMCP
event loop. Connection is initialised once at import time and reused.
"""
from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGODB_URI, MONGODB_DB

_client = AsyncIOMotorClient(MONGODB_URI)
_db = _client[MONGODB_DB]

talks = _db["talks"]
snacks = _db["snacks"]
