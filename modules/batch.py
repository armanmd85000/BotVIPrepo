from pyrogram import Client, filters
from pyrogram.types import Message
import os
import asyncio
from modules import drm_handler
from modules.utils import progress_bar
from modules.vars import AUTH_USERS, OWNER, CREDIT

# Global dictionary to store batch states
batch_states = {}

async def batch_command(bot: Client, m: Message):
    # Check authorization
    if m.chat.id not in AUTH_USERS:
        await m.reply_text("❌ You are not authorized to use this command.")
        return

    chat_id = m.chat.id
    batch_states[chat_id] = {
        'files': [],
        'config': {}
    }

    await m.reply_text(
        "__🚀 Batch Upload Mode Activated__\n\n"
        "**Send me your `.txt` files one by one.**\n"
        "When finished, send **/done** to proceed.\n"
        "Send **/cancel** to abort."
    )

async def handle_batch_files(bot: Client, m: Message):
    chat_id = m.chat.id
    if chat_id not in batch_states:
        return

    if m.text and m.text.lower() == "/done":
        if not batch_states[chat_id]['files']:
            await m.reply_text("❌ No files uploaded. Batch cancelled.")
            del batch_states[chat_id]
            return
        await collect_batch_config(bot, m)
        return

    if m.text and m.text.lower() == "/cancel":
        await m.reply_text("❌ Batch process cancelled.")
        # Cleanup uploaded files
        for file_path in batch_states[chat_id]['files']:
            if os.path.exists(file_path):
                os.remove(file_path)
        del batch_states[chat_id]
        return

    if m.document and m.document.file_name.endswith('.txt'):
        dl_msg = await m.reply_text("📥 Downloading file...")
        try:
            file_path = await m.download(file_name=f"./downloads/{chat_id}/batch_{len(batch_states[chat_id]['files'])}.txt")
            batch_states[chat_id]['files'].append({
                'path': file_path,
                'name': m.document.file_name
            })
            await dl_msg.edit_text(f"✅ Added: `{m.document.file_name}`\nTotal files: {len(batch_states[chat_id]['files'])}\n\nSend next file or **/done**.")
        except Exception as e:
            await dl_msg.edit_text(f"❌ Failed to download: {e}")
    else:
        await m.reply_text("⚠️ Please send a valid `.txt` file or **/done**.")

async def collect_batch_config(bot: Client, m: Message):
    chat_id = m.chat.id
    state = batch_states[chat_id]

    # 1. Resolution
    editable = await m.reply_text("**🎞️ Enter Resolution**\n\n`360`, `480`, `720`, `1080`")
    try:
        input_msg = await bot.listen(chat_id, timeout=30)
        res_input = input_msg.text
        await input_msg.delete()
    except asyncio.TimeoutError:
        res_input = '480'

    # Set resolution map (reusing logic from main.py)
    res_map = {"144": "256x144", "240": "426x240", "360": "640x360", "480": "854x480", "720": "1280x720", "1080": "1920x1080"}
    state['config']['quality'] = res_input
    state['config']['res'] = res_map.get(res_input, "UN")

    # 2. Watermark
    await editable.edit("**1. Send Text For Watermark\n2. Send /d for no watermark**")
    try:
        input_msg = await bot.listen(chat_id, timeout=30)
        watermark = input_msg.text
        await input_msg.delete()
    except asyncio.TimeoutError:
        watermark = '/d'
    state['config']['watermark'] = watermark

    # 3. Credit
    await editable.edit(f"**1. Send Name For Caption Credit\n2. Send /d For default Credit**")
    try:
        input_msg = await bot.listen(chat_id, timeout=30)
        credit_input = input_msg.text
        await input_msg.delete()
    except asyncio.TimeoutError:
        credit_input = '/d'

    if credit_input == '/d':
        state['config']['credit'] = CREDIT
    elif "," in credit_input:
        state['config']['credit'], state['config']['prename'] = credit_input.split(",")
    else:
        state['config']['credit'] = credit_input

    # 4. PW Token
    await editable.edit(f"**1. Send PW Token For MPD urls\n 2. Send /d For Others**")
    try:
        input_msg = await bot.listen(chat_id, timeout=30)
        token = input_msg.text
        await input_msg.delete()
    except asyncio.TimeoutError:
        token = '/d'
    state['config']['pw_token'] = token

    # 5. Thumbnail
    await editable.edit("**1. Send Image For Thumbnail\n2. Send /d For default\n3. Send /skip For Skipping**")
    try:
        input_msg = await bot.listen(chat_id, timeout=30)
        if input_msg.photo:
            thumb_path = f"downloads/{chat_id}_batch_thumb.jpg"
            await bot.download_media(message=input_msg.photo, file_name=thumb_path)
            state['config']['thumb'] = thumb_path
        elif input_msg.text == "/skip":
            state['config']['thumb'] = "no"
        else:
            state['config']['thumb'] = "/d"
        await input_msg.delete()
    except Exception as e:
        print(f"Thumb Error: {e}")
        state['config']['thumb'] = "/d"

    # 6. Channel ID
    await editable.edit("__**📢 Provide Channel ID or /d**__")
    try:
        input_msg = await bot.listen(chat_id, timeout=30)
        channel_id = input_msg.text
        await input_msg.delete()
    except asyncio.TimeoutError:
        channel_id = '/d'

    if "/d" in channel_id:
        state['config']['channel_id'] = chat_id
    else:
        state['config']['channel_id'] = channel_id

    await editable.delete()
    await start_batch_processing(bot, m)

async def start_batch_processing(bot: Client, m: Message):
    chat_id = m.chat.id
    state = batch_states[chat_id]
    files = state['files']
    config = state['config']

    status_msg = await m.reply_text(f"🚀 Starting Batch Process... {len(files)} files queued.")

    for idx, file_data in enumerate(files):
        file_path = file_data['path']
        original_filename = file_data['name']
        batch_name = os.path.splitext(original_filename)[0].replace('_', ' ')

        # Read content
        try:
            with open(file_path, "r", encoding='utf-8') as f:
                content = f.read()
            lines = [line.strip() for line in content.split("\n") if line.strip()]

            # Extract links (Reuse parsing logic if possible, simplified here)
            links = []
            for line in lines:
                if "://" in line:
                    parts = line.split("://", 1)
                    if len(parts) == 2:
                        links.append([parts[0], parts[1]])

            if not links:
                await m.reply_text(f"⚠️ No links found in `{original_filename}`. Skipping.")
                continue

            start_index = 1
            # Ask start index ONLY for the first file
            if idx == 0:
                q_msg = await m.reply_text(f"**📂 File 1: `{original_filename}`**\nFound {len(links)} links.\n**Enter Start Index (1-{len(links)}):**")
                try:
                    input_msg = await bot.listen(chat_id, timeout=60)
                    start_index = int(input_msg.text)
                    await input_msg.delete()
                except Exception:
                    start_index = 1
                await q_msg.delete()

            # Call processing function (We need to refactor drm_handler to expose a process function)
            await m.reply_text(f"▶️ **Processing File {idx+1}/{len(files)}:** `{original_filename}`\nBatch Name: `{batch_name}`\nStart Index: {start_index}")

            # Here we invoke the processing logic.
            # We need to modify drm_handler.py to accept arguments instead of asking interactively.
            # Passing 'is_batch=True' to suppress interactive prompts inside.

            await drm_handler.process_batch_links(
                bot=bot,
                m=m,
                links=links,
                start_index=start_index,
                batch_name=batch_name,
                config=config
            )

        except Exception as e:
            await m.reply_text(f"❌ Error processing `{original_filename}`: {e}")
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

    await m.reply_text("✅ **Batch Processing Completed!**")
    del batch_states[chat_id]
