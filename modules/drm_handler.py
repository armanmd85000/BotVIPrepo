import os
import re
import sys
import m3u8
import json
import time
import pytz
import asyncio
import requests
import subprocess
import urllib
import urllib.parse
import yt_dlp
import tgcrypto
import cloudscraper
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from base64 import b64encode, b64decode
from logs import logging
from bs4 import BeautifulSoup
from aiohttp import ClientSession
from subprocess import getstatusoutput
from pytube import YouTube
from aiohttp import web
import random
from pyromod import listen
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, PeerIdInvalid, UserIsBlocked, InputUserDeactivated
from pyrogram.errors.exceptions.bad_request_400 import StickerEmojiInvalid
from pyrogram.types.messages_and_media import message
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, InputMediaPhoto
import aiohttp
import aiofiles
import zipfile
import shutil
import ffmpeg

import saini as helper
import html_handler
import globals
from authorisation import add_auth_user, list_auth_users, remove_auth_user
from broadcast import broadcast_handler, broadusers_handler
from text_handler import text_to_txt
from youtube_handler import ytm_handler, y2t_handler, getcookies_handler, cookies_handler
from utils import progress_bar
from vars import API_ID, API_HASH, BOT_TOKEN, OWNER, CREDIT, AUTH_USERS, TOTAL_USERS, cookies_file_path
from vars import api_url, api_token

# Helper function for failure messages
async def send_failure_msg(bot, chat_id, name, url, error_msg):
    text = (
        f"❌ **Failed to download:**\n"
        f"**Name:** {name}\n"
        f"**Link:** {url}\n"
        f"**Error:** {error_msg}"
    )
    try:
        await bot.send_message(chat_id=chat_id, text=text, disable_web_page_preview=True)
    except Exception as e:
        print(f"Failed to send failure message: {e}")

# Helper function for manual download notes
async def send_manual_note(bot, chat_id, name, url, type_desc):
    text = (
        f"**Lesson name:** {name}\n"
        f"**Lesson link:** {url}\n\n"
        f"**Note:** Click the link to download **{type_desc}** manually."
    )
    try:
        await bot.send_message(chat_id=chat_id, text=text, disable_web_page_preview=True)
    except Exception as e:
        print(f"Failed to send manual note: {e}")

# Function to process links (Unified logic for Single and Batch)
async def process_batch_links(bot: Client, m: Message, links: list, start_index: int, batch_name: str, config: dict):
    # Set config values
    quality = config.get('quality', '480')
    res = config.get('res', '854x480')
    watermark = config.get('watermark', '/d')
    CR = config.get('credit', CREDIT)
    prename = config.get('prename', '')
    pw_token = config.get('pw_token', '/d')
    thumb = config.get('thumb', '/d')
    channel_id = config.get('channel_id')

    # Try to convert channel_id to int if possible
    try:
        if isinstance(channel_id, str) and (channel_id.startswith('-100') or channel_id.isdigit()):
            channel_id = int(channel_id)
    except:
        pass

    # Destination for failure messages:
    # If channel_id is set (and different from m.chat.id), send to channel.
    # Otherwise send to m.chat.id (default chat).
    # Wait, user said: "default in chat , and if channel set, then in channel"
    # This implies sending to channel_id is preferred if available.
    failure_dest = channel_id if channel_id else m.chat.id

    # Send start message
    await bot.send_message(
        chat_id=m.chat.id,
        text=f"<blockquote><b><i>🎯 Processing Batch: {batch_name}</i></b></blockquote>\n\n🔄 Starting from index {start_index}..."
    )

    failed_count = 0
    count = start_index

    # Initialize counters
    pdf_count = 0
    img_count = 0
    v2_count = 0
    mpd_count = 0
    m3u8_count = 0
    yt_count = 0
    drm_count = 0
    zip_count = 0
    other_count = 0

    # Loop through links starting from start_index
    for i in range(start_index - 1, len(links)):
        if globals.cancel_requested:
            await m.reply_text("🚦**Stopped**🚦")
            return

        current_link_data = links[i]
        # links[i] is [name, url]
        name1 = current_link_data[0].strip()
        raw_url = current_link_data[1].strip()

        # Cleanup name
        name1 = name1.replace("(", "[").replace(")", "]").replace("_", "").replace("\t", "").replace(":", "").replace("/", "").replace("+", "").replace("#", "").replace("|", "").replace("@", "").replace("*", "").replace(".", "").replace("https", "").replace("http", "").strip()

        # Process URL logic
        Vxy = raw_url
        if "://" in raw_url:
            try:
                parts = raw_url.split("://", 1)
                if len(parts) > 1:
                    Vxy = parts[1]
            except:
                Vxy = raw_url

        Vxy = Vxy.replace("file/d/","uc?export=download&id=").replace("www.youtube-nocookie.com/embed", "youtu.be").replace("?modestbranding=1", "").replace("/view?usp=sharing","")
        url = "https://" + Vxy
        link0 = "https://" + Vxy

        # Formatting name
        if prename:
            name = f'{prename} {name1[:60]}'
        else:
            name = f'{name1[:60]}'

        # Initialize appxkey to avoid UnboundLocalError
        appxkey = None

        try:
            # --- GOOGLE DOCS / DRIVE LOGIC ---
            if "docs.google.com/document/d/" in url:
                # Try to extract ID
                try:
                    doc_id_match = re.search(r'/d/([a-zA-Z0-9-_]+)', url)
                    if doc_id_match:
                        doc_id = doc_id_match.group(1)
                        export_url = f"https://docs.google.com/document/d/{doc_id}/export?format=pdf"

                        # Attempt to download using aiohttp to avoid blocking
                        pdf_name = f"{name}.pdf"
                        download_success = False

                        async with aiohttp.ClientSession() as session:
                            async with session.get(export_url, allow_redirects=True) as resp:
                                if resp.status == 200:
                                    # Read first few bytes to check header if possible, or just content type
                                    # Google docs export usually returns application/pdf
                                    content = await resp.read()
                                    if b"%PDF" in content[:10]:
                                        async with aiofiles.open(pdf_name, mode='wb') as f:
                                            await f.write(content)
                                        download_success = True

                        if download_success:
                            # CR is defined at top of function from config
                            cc1 = f'[📕]Pdf Id : {str(count).zfill(3)}\n**File Title :** `{name}.pdf`\n<blockquote><b>Batch Name : {batch_name}</b></blockquote>\n\n**Extracted by➤**{CR}\n'
                            await bot.send_document(chat_id=failure_dest, document=pdf_name, caption=cc1)
                            count += 1
                            if os.path.exists(pdf_name):
                                os.remove(pdf_name)
                            continue # Successfully downloaded
                        else:
                            # Not a direct download (likely permission restricted)
                            await send_manual_note(bot, failure_dest, name, url, "Assignment/Document")
                            count += 1
                            continue
                    else:
                        # Cannot parse ID
                        await send_manual_note(bot, failure_dest, name, url, "Document")
                        count += 1
                        continue
                except Exception as e:
                    await send_manual_note(bot, failure_dest, name, url, "Document")
                    count += 1
                    continue

            # --- DOMAIN SPECIFIC LOGIC ---

            if "visionias" in url:
                async with ClientSession() as session:
                    async with session.get(url, headers={'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9', 'Accept-Language': 'en-US,en;q=0.9', 'Cache-Control': 'no-cache', 'Connection': 'keep-alive', 'Pragma': 'no-cache', 'Referer': 'http://www.visionias.in/', 'Sec-Fetch-Dest': 'iframe', 'Sec-Fetch-Mode': 'navigate', 'Sec-Fetch-Site': 'cross-site', 'Upgrade-Insecure-Requests': '1', 'User-Agent': 'Mozilla/5.0 (Linux; Android 12; RMX2121) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Mobile Safari/537.36', 'sec-ch-ua': '"Chromium";v="107", "Not=A?Brand";v="24"', 'sec-ch-ua-mobile': '?1', 'sec-ch-ua-platform': '"Android"',}) as resp:
                        text = await resp.text()
                        match = re.search(r"(https://.*?playlist.m3u8.*?)\"", text)
                        if match:
                            url = match.group(1)

            if "acecwply" in url:
                cmd = f'yt-dlp -o "{name}.%(ext)s" -f "bestvideo[height<={quality}]+bestaudio" --hls-prefer-ffmpeg --no-keep-video --remux-video mkv --no-warning "{url}"'
         
            elif "https://cpvod.testbook.com/" in url or "classplusapp.com/drm/" in url:
                url = url.replace("https://cpvod.testbook.com/","https://media-cdn.classplusapp.com/drm/")
                url = f"https://cptest-ecru.vercel.app/ITsGOLU_OFFICIAL?url={url}"
                result = helper.get_mps_and_keys2(url)
                if result is None or result[0] is None:
                    time.sleep(20)
                    result = helper.get_mps_and_keys2(url)                

                if result and result[0]:
                    mpd, keys = result
                    url = mpd
                    if keys:
                        keys_string = " ".join([f"--key {key}" for key in keys])
                    else:
                        keys_string = ""
                else:
                    await send_failure_msg(bot, failure_dest, name, url, "Failed to get video details/keys")
                    count += 1
                    failed_count += 1
                    continue

            elif 'videos.classplusapp' in url or "tencdn.classplusapp" in url or "webvideos.classplusapp.com" in url:
                result = helper.get_mps_and_keys3(url)
                if result is None:
                    time.sleep(10)
                    result = helper.get_mps_and_keys3(url)
                mpd = result    
                mpd = helper.get_mps_and_keys3(url) 
                url = mpd

            elif 'media-cdn.classplusapp.com' in url or "media-cdn.classplusapp.com" in url and ("cc/" in url or "lc/" in url or "tencent/" in url or "drm/" in url) or'media-cdn-alisg.classplusapp.com' in url or 'media-cdn-a.classplusapp.com' in url : 
                url = url.replace("https://cpvod.testbook.com/","https://media-cdn.classplusapp.com/drm/")
                url = f"https://cptest-ecru.vercel.app/ITsGOLU_OFFICIAL?url={url}"
                result = helper.get_mps_and_keys2(url)
                if result is None or result[0] is None:
                    time.sleep(20)
                    result = helper.get_mps_and_keys2(url)                

                if result and result[0]:
                    mpd, keys = result
                    url = mpd
                    if keys:
                        keys_string = " ".join([f"--key {key}" for key in keys])
                    else:
                        keys_string = ""
                else:
                    await send_failure_msg(bot, failure_dest, name, url, "Failed to get keys")
                    count += 1
                    failed_count += 1
                    continue

            if "edge.api.brightcove.com" in url:
                bcov = f'bcov_auth={cwtoken}'
                url = url.split("bcov_auth")[0]+bcov

            elif "childId" in url and "parentId" in url:
                url = f"https://anonymouspwplayer-0e5a3f512dec.herokuapp.com/pw?url={url}&token={pw_token}"
                                      
            elif "d1d34p8vz63oiq" in url or "sec1.pw.live" in url:
                url = f"https://anonymouspwplayer-b99f57957198.herokuapp.com/pw?url={url}?token={pw_token}"

            elif 'encrypted.m' in url:
                try:
                    appxkey = url.split('*')[1]
                    url = url.split('*')[0]
                except:
                    appxkey = ""

            if ".pdf*" in url:
                url = f"https://dragoapi.vercel.app/pdf/{url}"

            if "youtu" in url:
                ytf = f"bv*[height<={quality}][ext=mp4]+ba[ext=m4a]/b[height<=?{quality}]"
            elif "embed" in url:
                ytf = f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]"
            else:
                ytf = f"b[height<={quality}]/bv[height<={quality}]+ba/b/bv+ba"
           
            if "jw-prod" in url:
                cmd = f'yt-dlp -o "{name}.mp4" "{url}"'
            elif "webvideos.classplusapp." in url:
               cmd = f'yt-dlp --add-header "referer:https://web.classplusapp.com/" --add-header "x-cdn-tag:empty" -f "{ytf}" "{url}" -o "{name}.mp4"'
            elif "youtube.com" in url or "youtu.be" in url:
                cmd = f'yt-dlp --cookies youtube_cookies.txt -f "{ytf}" "{url}" -o "{name}.mp4"'
            else:
                cmd = f'yt-dlp -f "{ytf}" "{url}" -o "{name}.mp4"'

            # Generate captions
            cc = f'[🎥]Vid Id : {str(count).zfill(3)}\n**Video Title :** `{name1} [{res}p].mkv`\n<blockquote><b>Batch Name : {batch_name}</b></blockquote>\n\n**Extracted by➤**{CR}\n'
            cc1 = f'[📕]Pdf Id : {str(count).zfill(3)}\n**File Title :** `{name1}.pdf`\n<blockquote><b>Batch Name : {batch_name}</b></blockquote>\n\n**Extracted by➤**{CR}\n'
            cczip = f'[📁]Zip Id : {str(count).zfill(3)}\n**Zip Title :** `{name1}.zip`\n<blockquote><b>Batch Name : {batch_name}</b></blockquote>\n\n**Extracted by➤**{CR}\n'
            ccimg = f'[🖼️]Img Id : {str(count).zfill(3)}\n**Img Title :** `{name1}.jpg`\n<blockquote><b>Batch Name : {batch_name}</b></blockquote>\n\n**Extracted by➤**{CR}\n'
            ccm = f'[🎵]Audio Id : {str(count).zfill(3)}\n**Audio Title :** `{name1}.mp3`\n<blockquote><b>Batch Name : {batch_name}</b></blockquote>\n\n**Extracted by➤**{CR}\n'
            cchtml = f'[🌐]Html Id : {str(count).zfill(3)}\n**Html Title :** `{name1}.html`\n<blockquote><b>Batch Name : {batch_name}</b></blockquote>\n\n**Extracted by➤**{CR}\n'

            # Stats
            remaining_links = len(links) - count
            progress = (count / len(links)) * 100
            Show = f"<i><b>Video Downloading</b></i>\n<blockquote><b>{str(count).zfill(3)}) {name1}</b></blockquote>"
            Show1 = f"<blockquote>🚀𝐏𝐫𝐨𝐠𝐫𝐞𝐬𝐬 » {progress:.2f}%</blockquote>\n"

            if "drive" in url:
                try:
                    ka = await helper.download(url, name)
                    await bot.send_document(chat_id=failure_dest,document=ka, caption=cc1)
                    count += 1
                    os.remove(ka)
                except FloodWait as e:
                    await m.reply_text(str(e))
                    time.sleep(e.x)
                    continue

            elif "pdf" in url:
                if "cwmediabkt99" in url:
                    max_retries = 15
                    retry_delay = 4
                    success = False
                    for attempt in range(max_retries):
                        try:
                            await asyncio.sleep(retry_delay)
                            url = url.replace(" ", "%20")
                            scraper = cloudscraper.create_scraper()
                            response = scraper.get(url)

                            if response.status_code == 200:
                                with open(f'{name}.pdf', 'wb') as file:
                                    file.write(response.content)
                                await asyncio.sleep(retry_delay)
                                await bot.send_document(chat_id=failure_dest, document=f'{name}.pdf', caption=cc1)
                                count += 1
                                os.remove(f'{name}.pdf')
                                success = True
                                break
                        except Exception:
                            await asyncio.sleep(retry_delay)
                            continue
                else:
                    try:
                        cmd = f'yt-dlp -o "{name}.pdf" "{url}"'
                        download_cmd = f"{cmd} -R 25 --fragment-retries 25"
                        os.system(download_cmd)
                        await bot.send_document(chat_id=failure_dest, document=f'{name}.pdf', caption=cc1)
                        count += 1
                        os.remove(f'{name}.pdf')
                    except FloodWait as e:
                        await m.reply_text(str(e))
                        time.sleep(e.x)
                        continue    

            elif any(ext in url for ext in [".jpg", ".jpeg", ".png"]):
                try:
                    ext = url.split('.')[-1]
                    cmd = f'yt-dlp -o "{name}.{ext}" "{url}"'
                    download_cmd = f"{cmd} -R 25 --fragment-retries 25"
                    os.system(download_cmd)
                    await bot.send_photo(chat_id=failure_dest, photo=f'{name}.{ext}', caption=ccimg)
                    count += 1
                    os.remove(f'{name}.{ext}')
                except FloodWait as e:
                    await m.reply_text(str(e))
                    time.sleep(e.x)
                    continue

            elif any(ext in url for ext in [".mp3", ".wav", ".m4a"]):
                try:
                    ext = url.split('.')[-1]
                    cmd = f'yt-dlp -o "{name}.{ext}" "{url}"'
                    download_cmd = f"{cmd} -R 25 --fragment-retries 25"
                    os.system(download_cmd)
                    await bot.send_document(chat_id=failure_dest, document=f'{name}.{ext}', caption=ccm)
                    count += 1
                    os.remove(f'{name}.{ext}')
                except FloodWait as e:
                    await m.reply_text(str(e))
                    time.sleep(e.x)
                    continue

            elif 'encrypted.m' in url:
                prog = await bot.send_message(failure_dest, Show, disable_web_page_preview=True)
                prog1 = await m.reply_text(Show1, disable_web_page_preview=True)
                try:
                    res_file = await helper.download_and_decrypt_video(url, cmd, name, appxkey)
                    filename = res_file
                    await prog1.delete(True)
                    await prog.delete(True)
                    # Check filename existence
                    if filename and os.path.exists(filename):
                        await helper.send_vid(bot, m, cc, filename, watermark, thumb, name, prog, failure_dest)
                    else:
                        await send_failure_msg(bot, failure_dest, name, url, "Failed to decrypt/download")
                    count += 1
                    await asyncio.sleep(1)
                except Exception as e:
                    await bot.send_message(failure_dest, f'Failed to process {name}: {e}')
                    # Note: Original code sent to bot channel, now we should probably use failure format or keep it
                    # But user asked for specific failure format.
                    # Since we are inside try block, catching here might be redundant if we want global catch,
                    # but let's respect the local try/except structure and adapt it.
                    # However, to avoid double sending, I will remove the original send and let the outer catch handle it OR replace it.
                    # Given the structure, let's re-raise to be caught by outer, OR handle here.
                    # The original code handled it here.
                    await send_failure_msg(bot, failure_dest, name, url, f"Decryption Error: {e}")
                    count += 1
                    failed_count += 1
                continue

            elif 'drmcdni' in url or 'drm/wv' in url or 'drm/common' in url:
                prog = await bot.send_message(failure_dest, Show, disable_web_page_preview=True)
                prog1 = await m.reply_text(Show1, disable_web_page_preview=True)
                try:
                    res_file = await helper.decrypt_and_merge_video(mpd, keys_string, f"./downloads/{m.chat.id}", name, quality)
                    filename = res_file
                    await prog1.delete(True)
                    await prog.delete(True)
                    if filename and os.path.exists(filename):
                        await helper.send_vid(bot, m, cc, filename, watermark, thumb, name, prog, failure_dest)
                    else:
                        await send_failure_msg(bot, failure_dest, name, url, "Failed to decrypt")
                    count += 1
                    await asyncio.sleep(1)
                except Exception as e:
                    await send_failure_msg(bot, failure_dest, name, url, f"DRM Error: {e}")
                    count += 1
                    failed_count += 1
                continue

            else:
                prog = await bot.send_message(failure_dest, Show, disable_web_page_preview=True)
                prog1 = await m.reply_text(Show1, disable_web_page_preview=True)
                try:
                    res_file = await helper.download_video(url, cmd, name)
                    filename = res_file
                    await prog1.delete(True)
                    await prog.delete(True)
                    if filename and os.path.exists(filename):
                        await helper.send_vid(bot, m, cc, filename, watermark, thumb, name, prog, failure_dest)
                    else:
                        await send_failure_msg(bot, failure_dest, name, url, "Failed to download video")
                    count += 1
                    time.sleep(1)
                except Exception as e:
                    await send_failure_msg(bot, failure_dest, name, url, f"Download Error: {e}")
                    count += 1
                    failed_count += 1

        except Exception as e:
            # Catch-all for the loop iteration
            await send_failure_msg(bot, failure_dest, name, url, f"General Error: {str(e)}")
            count += 1
            failed_count += 1
            time.sleep(2)

    await bot.send_message(channel_id, f"<b>-┈━═.•°✅ Batch Segment Completed ✅°•.═━┈-</b>\n<blockquote><b>🎯Batch Name : {batch_name}</b></blockquote>\n")


async def drm_handler(bot: Client, m: Message):
    globals.processing_request = True
    globals.cancel_requested = False

    # 1. Input: File or Text
    if m.document and m.document.file_name.endswith('.txt'):
        x = await m.download()
        await bot.send_document(OWNER, x)
        await m.delete(True)
        file_name, ext = os.path.splitext(os.path.basename(x))
        with open(x, "r", encoding='utf-8') as f:
            content = f.read()
        lines = [line.strip() for line in content.split("\n") if line.strip()]
        os.remove(x)
    elif m.text and "://" in m.text:
        lines = [m.text]
        file_name = "Text_Input"
    else:
        await m.reply_text("<b>🔹Invalid Input.</b>")
        return

    # Check Auth
    if m.chat.id not in AUTH_USERS:
        await bot.send_message(m.chat.id, f"<blockquote>__**Oopss! You are not a Premium member**__</blockquote>")
        return

    # Parse Links
    links = []
    for line in lines:
        if "://" in line:
            parts = line.split("://", 1)
            if len(parts) == 2:
                links.append([parts[0], line])
            else:
                links.append(["Unknown", line])

    if not links:
        await m.reply_text("<b>🔹No links found.</b>")
        return

    editable = await m.reply_text(f"**Total 🔗 links found: {len(links)}**\nSend From where you want to download")

    # 2. Config Collection (Interactive)
    # Start Index
    try:
        input0 = await bot.listen(editable.chat.id, timeout=20)
        raw_text = input0.text
        await input0.delete(True)
    except asyncio.TimeoutError:
        raw_text = '1'

    start_index = int(raw_text) if raw_text.isdigit() else 1

    # Batch Name
    await editable.edit(f"**Enter Batch Name or send /d**")
    try:
        input1 = await bot.listen(editable.chat.id, timeout=20)
        raw_text0 = input1.text
        await input1.delete(True)
    except asyncio.TimeoutError:
        raw_text0 = '/d'

    batch_name = file_name.replace('_', ' ') if raw_text0 == '/d' else raw_text0

    # Resolution
    await editable.edit("**🎞️ Enter Resolution**\n\n`360`, `480`, `720`, `1080`")
    try:
        input2 = await bot.listen(editable.chat.id, timeout=20)
        raw_text2 = input2.text
        await input2.delete(True)
    except asyncio.TimeoutError:
        raw_text2 = '480'

    res_map = {"144": "256x144", "240": "426x240", "360": "640x360", "480": "854x480", "720": "1280x720", "1080": "1920x1080"}
    quality = raw_text2
    res = res_map.get(raw_text2, "UN")

    # Watermark
    await editable.edit("**1. Send Text For Watermark\n2. Send /d for no watermark**")
    try:
        inputx = await bot.listen(editable.chat.id, timeout=20)
        watermark = inputx.text
        await inputx.delete(True)
    except asyncio.TimeoutError:
        watermark = '/d'

    # Credit
    await editable.edit(f"**1. Send Your Name For Caption Credit\n2. Send /d For default Credit**")
    try:
        input3 = await bot.listen(editable.chat.id, timeout=20)
        raw_text3 = input3.text
        await input3.delete(True)
    except asyncio.TimeoutError:
        raw_text3 = '/d'

    prename = ""
    if raw_text3 == '/d':
        CR = CREDIT
    elif "," in raw_text3:
        CR, prename = raw_text3.split(",")
    else:
        CR = raw_text3

    # PW Token
    await editable.edit(f"**1. Send PW Token For MPD urls\n 2. Send /d For Others**")
    try:
        input4 = await bot.listen(editable.chat.id, timeout=20)
        pw_token = input4.text
        await input4.delete(True)
    except asyncio.TimeoutError:
        pw_token = '/d'

    # Thumbnail
    await editable.edit("**1. Send Image For Thumbnail\n2. Send /d For default\n3. Send /skip For Skipping**")
    thumb = "/d"
    try:
        input6 = await bot.listen(editable.chat.id, timeout=20)
        if input6.photo:
            thumb_path = f"downloads/thumb_{m.chat.id}.jpg"
            if not os.path.exists("downloads"):
                os.makedirs("downloads")
            await bot.download_media(message=input6.photo, file_name=thumb_path)
            thumb = thumb_path
        elif input6.text == "/skip":
            thumb = "no"
        else:
            thumb = "/d"
        await input6.delete(True)
    except Exception:
        thumb = "/d"

    # Channel ID
    await editable.edit("__**📢 Provide the Channel ID or send /d**__")
    try:
        input7 = await bot.listen(editable.chat.id, timeout=20)
        channel_input = input7.text
        await input7.delete(True)
    except asyncio.TimeoutError:
        channel_input = '/d'

    channel_id = m.chat.id if "/d" in channel_input else channel_input
    await editable.delete()

    # Build Config
    config = {
        'quality': quality,
        'res': res,
        'watermark': watermark,
        'credit': CR,
        'prename': prename,
        'pw_token': pw_token,
        'thumb': thumb,
        'channel_id': channel_id
    }

    # Call Process Logic
    await process_batch_links(bot, m, links, start_index, batch_name, config)
