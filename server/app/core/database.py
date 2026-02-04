from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import MONGODB_URL
from app.core.logger import add_log

client: AsyncIOMotorClient = None
db = None

async def connect_db():
    """Connect to MongoDB Atlas on startup."""
    global client, db
    try:
        add_log("Connecting to MongoDB Atlas...")
        client = AsyncIOMotorClient(MONGODB_URL)
        db = client.get_default_database()
        # Verify connection
        await client.admin.command('ping')
        add_log(f"MongoDB connected: {db.name}")
    except Exception as e:
        add_log(f"MongoDB connection failed: {str(e)}")
        raise

async def close_db():
    """Close MongoDB connection on shutdown."""
    global client
    if client:
        client.close()
        add_log("MongoDB connection closed")

def get_database():
    """Get database instance."""
    return db
