import os
import aiohttp
import uuid
import asyncio
import posixpath
from urllib.parse import urlparse, urlunparse
from pyrogram import Client, filters
from pyrogram.types import Message

async def check_url(session, url):
    """
    Checks if a URL is reachable using HEAD request asynchronously.
    """
    try:
        async with session.head(url, timeout=5) as response:
            return response.status == 200
    except:
        return False

def generate_custom_m3u8(video_url, audio_url):
    """
    Generates the content of a Master Playlist linking video and audio.
    """
    content = "#EXTM3U\n"
    content += "#EXT-X-VERSION:3\n"
    content += f'#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="audio",NAME="English",DEFAULT=YES,AUTOSELECT=YES,URI="{audio_url}"\n'
    content += f'#EXT-X-STREAM-INF:BANDWIDTH=5000000,RESOLUTION=1920x1080,AUDIO="audio"\n'
    content += f"{video_url}\n"
    return content

async def process_single_link(session, broken_link):
    """
    Converts a single video-only link to a master playlist link.
    Returns:
      - (str) master_link if a server-side playlist exists
      - (dict) {'filename': str, 'content': str} if a custom playlist was generated
      - None if failed
    """
    broken_link = broken_link.strip()
    if not broken_link:
        return None
    if "m3u8" not in broken_link:
        return None

    try:
        parsed_url = urlparse(broken_link)
        path = parsed_url.path

        # Expecting ...-video.m3u8 or just .m3u8
        if not path.endswith('.m3u8'):
            return None

        # 1. Check for server-side master playlist
        base_path = posixpath.dirname(path)
        candidates = ['playlist.m3u8', 'master.m3u8']

        for candidate in candidates:
            new_path = f"{base_path}/{candidate}"
            new_url = urlunparse((
                parsed_url.scheme,
                parsed_url.netloc,
                new_path,
                parsed_url.params,
                parsed_url.query,
                parsed_url.fragment
            ))

            if await check_url(session, new_url):
                return new_url

        # 2. If server-side playlist not found, try to construct Audio URL and generate custom M3U8
        if "video" in path:
            audio_path = path.replace("video", "audio")
            audio_url = urlunparse((
                parsed_url.scheme,
                parsed_url.netloc,
                audio_path,
                parsed_url.params,
                parsed_url.query,
                parsed_url.fragment
            ))

            # Use the original video link as the video source
            video_url = broken_link

            m3u8_content = generate_custom_m3u8(video_url, audio_url)

            # Create a filename based on the unique part of the path (usually a UUID)
            # Try to grab the last directory component as ID
            try:
                name_id = base_path.split('/')[-1]
            except:
                name_id = uuid.uuid4().hex[:8]

            return {
                'filename': f"mindvalley_{name_id}.m3u8",
                'content': m3u8_content
            }

        return None
    except:
        return None

async def mindvalley_handler(bot: Client, m: Message):
    """
    Handles the /mindvalley command.
    """
    user_id = m.chat.id
    text_input = ""

    if len(m.command) > 1:
        text_input = m.text.split(None, 1)[1]
    elif m.reply_to_message and m.reply_to_message.text:
        text_input = m.reply_to_message.text
    else:
        await m.reply_text(
            "**🚀 Mindvalley Link Fixer**\n\n"
            "**Instructions:**\n"
            "1. Paste one or more `...-video.m3u8` links.\n"
            "2. I will try to find the Master Playlist.\n"
            "3. If that fails, I will generate a **Custom .m3u8 File** for you.\n\n"
            "__Waiting for links...__"
        )
        try:
            input_msg: Message = await bot.listen(user_id, timeout=300)
            text_input = input_msg.text
        except Exception:
            return

    if not text_input:
        return

    status_msg = await m.reply_text("🔄 **Processing Links...**")

    lines = text_input.split()
    results = []

    async with aiohttp.ClientSession() as session:
        tasks = []
        for line in lines:
            if "m3u8" in line:
                tasks.append(process_single_link(session, line))

        processed_data = await asyncio.gather(*tasks)

    valid_links = []
    files_to_send = []

    for data in processed_data:
        if isinstance(data, str):
            valid_links.append(data)
        elif isinstance(data, dict):
            files_to_send.append(data)

    if not valid_links and not files_to_send:
        await status_msg.edit_text("❌ No valid links found or could not generate playlists.")
        return

    await status_msg.delete()

    # 1. Send text links if any found
    if valid_links:
        output_text = "\n".join(valid_links)
        if len(output_text) < 4000:
            await m.reply_text(f"✅ **Found Master Links:**\n\n```\n{output_text}\n```")
        else:
            unique_id = uuid.uuid4().hex[:8]
            filename = f"Mindvalley_Masters_{unique_id}.txt"
            try:
                with open(filename, "w") as f:
                    f.write(output_text)
                await m.reply_document(document=filename, caption=f"📄 {len(valid_links)} Master Links")
            finally:
                if os.path.exists(filename):
                    os.remove(filename)

    # 2. Send generated custom files
    if files_to_send:
        await m.reply_text(f"⚠️ **Could not find Master Links for {len(files_to_send)} videos.**\nGenerated custom .m3u8 files instead. Download these and use them in your player/downloader.")

        for file_data in files_to_send:
            fname = file_data['filename']
            content = file_data['content']
            try:
                with open(fname, "w") as f:
                    f.write(content)
                await m.reply_document(document=fname, caption=f"📄 {fname}")
            finally:
                if os.path.exists(fname):
                    os.remove(fname)
            # Add small delay to avoid flood wait
            await asyncio.sleep(0.5)
