from motor.motor_asyncio import AsyncIOMotorClient
import certifi
from app.config.settings import MONGO_URI

# --- CONNECTION ---
client = AsyncIOMotorClient(MONGO_URI, tlsCAFile=certifi.where())
db = client["niachatbot_db"]

# --- COLLECTIONS ---
users_col = db["users"]
groups_col = db["groups"]
sudo_col = db["sudoers"]
chatbot_col = db["chatbot"]
riddles_col = db["riddles"]


# ==============================
# 👤 USER DATABASE
# ==============================

class UserDB:

    async def get_user(self, user_id: int):
        return await users_col.find_one({"user_id": user_id})

    async def create_user(self, user_id: int):
        user = {
            "user_id": user_id,
            "balance": 0,
            "inventory": [],
            "waifus": [],
            "created_at": int(__import__("time").time())
        }
        await users_col.insert_one(user)
        return user

    async def add_balance(self, user_id: int, amount: int):
        await users_col.update_one(
            {"user_id": user_id},
            {"$inc": {"balance": amount}},
            upsert=True
        )

    async def get_balance(self, user_id: int):
        user = await self.get_user(user_id)
        return user.get("balance", 0) if user else 0


# ==============================
# 👥 GROUP DATABASE
# ==============================

class GroupDB:

    async def get_group(self, group_id: int):
        return await groups_col.find_one({"group_id": group_id})

    async def set_welcome(self, group_id: int, status: bool):
        await groups_col.update_one(
            {"group_id": group_id},
            {"$set": {"welcome": status}},
            upsert=True
        )


# ==============================
# 🧠 CHATBOT MEMORY
# ==============================

class ChatbotDB:

    async def save_message(self, user_id: int, message: str):
        await chatbot_col.insert_one({
            "user_id": user_id,
            "message": message
        })

    async def get_history(self, user_id: int, limit: int = 10):
        cursor = chatbot_col.find({"user_id": user_id}).sort("_id", -1).limit(limit)
        return [doc async for doc in cursor]


# ==============================
# 🧩 RIDDLES SYSTEM
# ==============================

class RiddleDB:

    async def set_riddle(self, chat_id: int, question: str, answer: str):
        await riddles_col.update_one(
            {"chat_id": chat_id},
            {"$set": {"question": question, "answer": answer}},
            upsert=True
        )

    async def get_riddle(self, chat_id: int):
        return await riddles_col.find_one({"chat_id": chat_id})

    async def clear_riddle(self, chat_id: int):
        await riddles_col.delete_one({"chat_id": chat_id})


# ==============================
# 👑 SUDO USERS
# ==============================

class SudoDB:

    async def add_sudo(self, user_id: int):
        await sudo_col.update_one(
            {"user_id": user_id},
            {"$set": {"user_id": user_id}},
            upsert=True
        )

    async def is_sudo(self, user_id: int):
        return await sudo_col.find_one({"user_id": user_id}) is not None
