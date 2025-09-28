import os
import requests
import subprocess
from vars import OWNER, CREDIT, AUTH_USERS, TOTAL_USERS
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import PeerIdInvalid

# .....,.....,.......,...,.......,....., .....,.....,.......,...,.......,.....,

async def add_auth_user(client: Client, message: Message):
    if message.chat.id != OWNER:
        return
    try:
        new_user_id = int(message.command[1])
        if new_user_id in AUTH_USERS:
            await message.reply_text("**User ID is already authorized.**")
        else:
            AUTH_USERS.append(new_user_id)
            await message.reply_text(f"**User ID `{new_user_id}` added to authorized users.**")
            try:
                await client.send_message(
                    chat_id=new_user_id,
                    text="<b>Great! You are added in Premium Membership!</b>"
                )
            except PeerIdInvalid:
                await message.reply_text(
                    f"⚠️ Cannot send message to `{new_user_id}`. They must start the bot first."
                )
    except (IndexError, ValueError):
        await message.reply_text("**Please provide a valid user ID.**")

# .....,.....,.......,...,.......,....., .....,.....,.......,...,.......,.....,

async def list_auth_users(client: Client, message: Message):
    if message.chat.id != OWNER:
        return
    
    if AUTH_USERS:
        user_list = '\n'.join(map(str, AUTH_USERS))
        await message.reply_text(f"**Authorized Users:**\n{user_list}")
    else:
        await message.reply_text("**No authorized users yet.**")

# .....,.....,.......,...,.......,....., .....,.....,.......,...,.......,.....,

async def remove_auth_user(client: Client, message: Message):
    if message.chat.id != OWNER:
        return
    
    try:
        user_id_to_remove = int(message.command[1])
        if user_id_to_remove not in AUTH_USERS:
            await message.reply_text("**User ID is not in the authorized users list.**")
        else:
            AUTH_USERS.remove(user_id_to_remove)
            await message.reply_text(f"**User ID `{user_id_to_remove}` removed from authorized users.**")
            try:
                await client.send_message(
                    chat_id=user_id_to_remove,
                    text="<b>Oops! You are removed from Premium Membership!</b>"
                )
            except PeerIdInvalid:
                await message.reply_text(
                    f"⚠️ Cannot notify `{user_id_to_remove}` because they never started the bot."
                )
    except (IndexError, ValueError):
        await message.reply_text("**Please provide a valid user ID.**")
