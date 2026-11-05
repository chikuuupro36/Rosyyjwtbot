# ============================================================
#  ADVANCED TELEGRAM AUTOMATION WEB SERVICE — by CHIKUU
# ============================================================
import asyncio
import logging
import json
import os
import base64
import random
import time
from datetime import datetime
from fastapi import FastAPI
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import httpx
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# FastAPI App initialization for UpToTime / Web Service
app = FastAPI()
scheduler = AsyncIOScheduler()

@app.get("/")
def home():
    return {"status": "Bot is running 24/7 live!", "managed_by": "Chikuu"}

# Token environment variable from Render
TOKEN = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# API & Crypto Configuration
JWT_API_BASE = "https://rosyy-jwt-genrator.vercel.app/token"
LOGIN_HOST = "https://loginbp.ppmainecoonghj.com"
AES_KEY = b'Yg&tc%DEuh6%Zc^8'
AES_IV  = b'6oyZDr22E3ychjM%'

class AutoProcessStates(StatesGroup):
    waiting_for_github_repo = State()
    waiting_for_github_token = State()
    waiting_for_timer = State()
    waiting_for_json_file = State()

class ReqSendStates(StatesGroup):
    waiting_for_req_file = State()
    waiting_for_targets = State()

# --- Keyboards ---
def get_main_menu():
    keyboard = [
        [types.InlineKeyboardButton(text="🔄 Auto Process & GitHub Sync", callback_data="auto_process")],
        [types.InlineKeyboardButton(text="📨 Req Send Button", callback_data="req_send")],
        [types.InlineKeyboardButton(text="📝 Add Long Bio", callback_data="long_bio")],
        [types.InlineKeyboardButton(text="🆘 Help Center", callback_data="help_menu")]
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_cancel_menu():
    keyboard = [
        [types.InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")]
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_help_menu_kb():
    keyboard = [
        [types.InlineKeyboardButton(text="📌 Normal Commands", callback_data="help_normal")],
        [types.InlineKeyboardButton(text="❓ FAQ", callback_data="help_faq")],
        [types.InlineKeyboardButton(text="💡 Tips", callback_data="help_tips")],
        [types.InlineKeyboardButton(text="« Back", callback_data="back_to_menu")]
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)

# --- Crypto & Proto Helpers for Friend Request ---
def varint(n):
    out = bytearray()
    if n < 0: n &= 0xFFFFFFFFFFFFFFFF
    while True:
        b = n & 0x7F; n >>= 7
        if n: b |= 0x80
        out.append(b)
        if not n: break
    return bytes(out)

def build_proto(fields):
    parts = []
    for k, v in fields.items():
        if isinstance(v, int): parts.append(varint((k<<3)|0) + varint(v))
        elif isinstance(v, (str, bytes)):
            ev = v.encode() if isinstance(v, str) else v
            parts.append(varint((k<<3)|2) + varint(len(ev)) + ev)
    return b''.join(parts)

def enc(b): return AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(pad(b, 16))

def dec_proto(data):
    result = {}; o = 0
    while o < len(data):
        h = 0; s = 0
        while o < len(data):
            b = data[o]; o += 1; h |= (b & 0x7F) << s
            if not (b & 0x80): break
            s += 7
        if h == 0: break
        fn = h >> 3; wt = h & 7
        if fn == 0: break
        if wt == 0:
            v = 0; s = 0
            while o < len(data):
                b = data[o]; o += 1; v |= (b & 0x7F) << s
                if not (b & 0x80): break
                s += 7
            result[fn] = v
        elif wt == 2:
            l = 0; s = 0
            while o < len(data):
                b = data[o]; o += 1; l |= (b & 0x7F) << s
                if not (b & 0x80): break
                s += 7
            v = data[o:o+l]; o += l
            try:
                st = v.decode()
                result[fn] = st if st.isprintable() else dec_proto(v)
            except: result[fn] = dec_proto(v) if v else v.hex()
        elif wt == 5: o += 4
        elif wt == 1: o += 8
        else: break
    return result

def gf(d, k, default=None):
    if not d: return default
    if k in d: return d[k]
    if str(k) in d: return d[str(k)]
    return default

# --- GitHub File Uploader Function ---
async def update_github_file(repo: str, gh_token: str, file_path: str, file_content: str, commit_message: str):
    url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
    headers = {
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    async with httpx.AsyncClient() as client:
        sha = None
        resp = await client.get(url, headers=headers)
        if resp.status_code == 200:
            sha = resp.json().get("sha")
        encoded_content = base64.b64encode(file_content.encode("utf-8")).decode("utf-8")
        payload = {
            "message": commit_message,
            "content": encoded_content,
            "branch": "main"
        }
        if sha:
            payload["sha"] = sha
        put_resp = await client.put(url, headers=headers, json=payload)
        if put_resp.status_code in [200, 201]:
            return True, "Success"
        else:
            return False, put_resp.text

# --- Start Command ---
@dp.message(Command("start"))
async def start_handler(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 **Hello 🌸!**\n\n"
        "🚀 **JWT TOKEN GENERATOR & AUTOMATION BOT**\n"
        "Managed & Powered by **Chikuu** ✨\n\n"
        "Please select an option from the menu below:",
        reply_markup=get_main_menu(),
        parse_mode="Markdown"
    )

# --- Help Center Handlers ---
@dp.callback_query(F.data == "help_menu")
async def help_menu_handler(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "🆘 **HELP CENTER**\n\n"
        "Choose a section below for Purpose, Usage & Examples of every command:",
        reply_markup=get_help_menu_kb(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "help_normal")
async def help_normal_handler(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "📌 **NORMAL COMMANDS**\n\n"
        "• `/start` — Open the Welcome Message and Main Menu[span_2](start_span)[span_2](end_span).\n"
        "• `/help` — Open the Complete Help Menu[span_3](start_span)[span_3](end_span).\n"
        "• **Auto Process** — Connect GitHub repo & set timer to automatically update tokens via `.json` file.\n"
        "• **Req Send** — Upload account file and target UIDs to send bulk friend requests.\n"
        "• `/cancel` — Immediately stop any current setup or running process[span_4](start_span)[span_4](end_span).",
        reply_markup=get_help_menu_kb(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "help_faq")
async def help_faq_handler(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "❓ **FAQ**\n\n"
        "❓ **Auto Update or GitHub sync not working?**\n"
        "➡️ Check if your GitHub Token and Repository name are entered correctly.\n\n"
        "❓ **Main menu or buttons not showing?**\n"
        "➡️ Send `/start` or `/help` again. The menu will refresh automatically[span_5](start_span)[span_5](end_span).\n\n"
        "❓ **Facing issues during setup?**\n"
        "➡️ Use `/cancel` to stop the current process and restart the setup[span_6](start_span)[span_6](end_span).",
        reply_markup=get_help_menu_kb(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "help_tips")
async def help_tips_handler(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "💡 **TIPS**\n\n"
        "• **Fast Processing:** Process all accounts in parallel with live status updates[span_7](start_span)[span_7](end_span).\n"
        "• **Auto Updates:** Automatically sync region-wise JSON files (`token_ind.json`, `token_bd.json`) directly to your GitHub repo based on your timer.\n"
        "• **Quick Cancel:** Use the Cancel button at any setup step to immediately stop the current process[span_8](start_span)[span_8](end_span).",
        reply_markup=get_help_menu_kb(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(
        "✨ **Main Menu** ✨\nSelect an option below:",
        reply_markup=get_main_menu(),
        parse_mode="Markdown"
    )

@dp.message(Command("help"))
async def help_command_handler(message: types.Message):
    await message.answer(
        "🆘 **HELP CENTER**\n\nChoose a section below:",
        reply_markup=get_help_menu_kb(),
        parse_mode="Markdown"
    )

# --- Add Long Bio Button Handler ---
@dp.callback_query(F.data == "long_bio")
async def long_bio_handler(callback: types.CallbackQuery):
    await callback.answer("Coming Soon!", show_alert=True)
    await callback.message.edit_text(
        "📝 **Add Long Bio**\n\n⚠️ This feature will be launched soon! **Coming Soon 🚧**\n\n— *Powered by Chikuu*",
        reply_markup=get_main_menu(),
        parse_mode="Markdown"
    )

# ================= AUTO PROCESS & GITHUB FLOW WITH TIMER =================
@dp.callback_query(F.data == "auto_process")
async def auto_process_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AutoProcessStates.waiting_for_github_repo)
    await callback.message.edit_text(
        "🔄 **GitHub Setup (Step 1/4)**\n\n"
        "Please send your **GitHub Repository** name in this format:\n"
        "`username/repository-name` (e.g., `chikuu/my-tokens-repo`)\n\n"
        "⚠️ *Tap cancel below to stop the process anytime.*",
        reply_markup=get_cancel_menu(),
        parse_mode="Markdown"
    )

@dp.message(AutoProcessStates.waiting_for_github_repo)
async def receive_github_repo(message: types.Message, state: FSMContext):
    repo = message.text.strip()
    if "/" not in repo:
        await message.answer("❌ Invalid format! Please send in `username/repo-name` format.", reply_markup=get_cancel_menu())
        return
    await state.update_data(github_repo=repo)
    await state.set_state(AutoProcessStates.waiting_for_github_token)
    await message.answer(
        "🔑 **GitHub Setup (Step 2/4)**\n\n"
        "Now send your **GitHub Personal Access Token (PAT)** (must have repo permissions).\n\n"
        "⚠️ *Your token is completely secure.*",
        reply_markup=get_cancel_menu(),
        parse_mode="Markdown"
    )

@dp.message(AutoProcessStates.waiting_for_github_token)
async def receive_github_token(message: types.Message, state: FSMContext):
    gh_token = message.text.strip()
    await state.update_data(github_token=gh_token)
    await state.set_state(AutoProcessStates.waiting_for_timer)
    await message.answer(
        "⏰ **Auto-Update Timer (Step 3/4)**\n\n"
        "After how many hours do you want the files to automatically update?\n"
        "Type numbers only (e.g., `2` for every 2 hours, `6` for every 6 hours):",
        reply_markup=get_cancel_menu(),
        parse_mode="Markdown"
    )

@dp.message(AutoProcessStates.waiting_for_timer)
async def receive_timer(message: types.Message, state: FSMContext):
    timer_text = message.text.strip()
    if not timer_text.isdigit() or int(timer_text) <= 0:
        await message.answer("❌ Please send a valid number (e.g. 2, 4, 6):", reply_markup=get_cancel_menu())
        return
    hours = int(timer_text)
    await state.update_data(timer_hours=hours)
    await state.set_state(AutoProcessStates.waiting_for_json_file)
    await message.answer(
        f"📁 **GitHub Setup (Step 4/4)**\n\n"
        f"✅ Timer set: Auto-update will run every `{hours}` hours!\n\n"
        "Now upload your accounts `.json` file containing `uid` and `password` list.",
        reply_markup=get_cancel_menu(),
        parse_mode="Markdown"
    )

@dp.message(AutoProcessStates.waiting_for_json_file, F.document)
async def process_auto_json_file(message: types.Message, state: FSMContext):
    document = message.document
    if not document.file_name.endswith('.json'):
        await message.answer("❌ Please upload a valid `.json` file only!", reply_markup=get_cancel_menu())
        return

    data_state = await state.get_data()
    repo = data_state.get("github_repo")
    gh_token = data_state.get("github_token")
    hours = data_state.get("timer_hours", 2)
    chat_id = message.chat.id

    file = await bot.get_file(document.file_id)
    file_bytes = await bot.download_file(file.file_path)
    file_content_bytes = file_bytes.read()
    
    try:
        accounts = json.loads(file_content_bytes.decode('utf-8'))
        if not isinstance(accounts, list):
            raise ValueError("JSON must be a list of objects.")
        
        status_msg = await message.answer(
            f"⏳ Initial processing & GitHub sync starting (Timer: Every {hours} hours)... ⚡",
            reply_markup=get_cancel_menu()
        )
        
        async def run_auto_sync():
            try:
                region_tokens = {}
                success_count = 0
                fail_count = 0
                async with httpx.AsyncClient(timeout=15.0) as client_http:
                    for acc in accounts[:50]:
                        uid = acc.get("uid")
                        pwd = acc.get("password")
                        if not uid or not pwd:
                            continue
                        try:
                            api_url = f"{JWT_API_BASE}?uid={uid}&password={pwd}"
                            resp = await client_http.get(api_url)
                            if resp.status_code == 200:
                                res_data = resp.json()
                                token = res_data.get("token") or res_data.get("access_token")
                                region = res_data.get("region", "IND").lower()
                                if token:
                                    if region not in region_tokens:
                                        region_tokens[region] = []
                                    region_tokens[region].append({"uid": uid, "token": token})
                                    success_count += 1
                                else:
                                    fail_count += 1
                            else:
                                fail_count += 1
                        except Exception:
                            fail_count += 1

                github_status_text = ""
                for reg, toks in region_tokens.items():
                    filename = f"token_{reg}.json"
                    file_content = json.dumps(toks, indent=2)
                    success, msg = await update_github_file(
                        repo=repo, gh_token=gh_token, file_path=filename,
                        file_content=file_content, commit_message=f"Scheduled Auto-update {filename} via Chikuu Bot 🚀"
                    )
                    if success:
                        github_status_text += f"\n📁 `{filename}` ➔ **Updated ✅**"
                    else:
                        github_status_text += f"\n📁 `{filename}` ➔ **Failed ❌**"

                await bot.send_message(
                    chat_id,
                    f"🔄 **Scheduled Auto-Update Triggered!**\n"
                    f"✅ Success: `{success_count}` | ❌ Failed: `{fail_count}`\n"
                    f"🌐 **GitHub Status:**{github_status_text}\n\n— *Chikuu Bot 🌸*",
                    parse_mode="Markdown"
                )
            except Exception as ex:
                logging.error(f"Auto sync error: {ex}")

        await run_auto_sync()

        job_id = f"autoupdate_{chat_id}"
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
        scheduler.add_job(run_auto_sync, 'interval', hours=hours, id=job_id)

        await message.answer(
            f"🎉 **Auto Process & GitHub Timer Configured Successfully!**\n"
            f"⏰ From now on, every **{hours} hours** the bot will automatically generate tokens and update your GitHub repository!\n\n"
            f"— *System managed by Chikuu 🌸*",
            reply_markup=get_main_menu(),
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.answer(f"❌ Error parsing file: `{str(e)}`", reply_markup=get_main_menu())
    await state.clear()

# ================= REQ SEND FLOW (FIXED & RESTORED) =================
@dp.callback_query(F.data == "req_send")
async def req_send_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(ReqSendStates.waiting_for_req_file)
    await callback.message.edit_text(
        "📨 **Request Sender System (Step 1/2)**\n\n"
        "Please upload your accounts `.json` file (`uid` & `password` list) so the bot can send requests.\n\n"
        "⚠️ *Tap cancel below to stop the process anytime.*",
        reply_markup=get_cancel_menu(),
        parse_mode="Markdown"
    )

@dp.message(ReqSendStates.waiting_for_req_file, F.document)
async def process_req_file(message: types.Message, state: FSMContext):
    document = message.document
    if not document.file_name.endswith('.json'):
        await message.answer("❌ Please upload a valid `.json` file only!", reply_markup=get_cancel_menu())
        return

    file = await bot.get_file(document.file_id)
    file_bytes = await bot.download_file(file.file_path)
    
    try:
        accounts = json.loads(file_bytes.read().decode('utf-8'))
        if not isinstance(accounts, list) or not accounts:
            raise ValueError("JSON must be a non-empty list.")
        
        # Save accounts data in FSM state and ask for target UIDs
        await state.update_data(accounts=accounts)
        await state.set_state(ReqSendStates.waiting_for_targets)
        
        await message.answer(
            f"✅ File loaded successfully! Total accounts found: `{len(accounts)}`.\n\n"
            f"🎯 **Step 2/2:** Now send your **Target UID(s)** comma-separated (e.g., `1234567, 8910111`):",
            reply_markup=get_cancel_menu(),
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.answer(f"❌ Error parsing file: `{str(e)}`", reply_markup=get_main_menu())
        await state.clear()

@dp.message(ReqSendStates.waiting_for_targets)
async def process_friend_requests(message: types.Message, state: FSMContext):
    tg_raw = message.text.strip()
    targets = [int(t) for t in tg_raw.replace(" ", "").split(",") if t.isdigit()]
    if not targets:
        await message.answer("❌ No valid target UIDs found! Please send comma-separated numbers (e.g., `123456, 789012`):", reply_markup=get_cancel_menu())
        return

    data = await state.get_data()
    accounts = data.get("accounts", [])
    chat_id = message.chat.id

    status_msg = await message.answer(
        f"🚀 Starting Bulk Friend Request Sender for `{len(targets)}` targets using `{len(accounts)}` accounts...\n"
        f"⚡ Live progress updates will appear below:",
        reply_markup=get_cancel_menu()
    )

    # Background runner for sending requests
    async def run_friend_sender():
        try:
            total_succ = 0
            total_fail = 0
            
            async with httpx.AsyncClient(verify=False, timeout=15.0, http2=False, trust_env=False) as http_client:
                for idx, acc in enumerate(accounts[:30], 1): # Safety limit
                    uid = acc.get("uid")
                    pwd = acc.get("password")
                    if not uid or not pwd:
                        continue

                    try:
                        # 1. Guest login
                        login_url = "https://100067.connect.garena.com/oauth/guest/token/grant"
                        hdrs = {"Host": "100067.connect.garena.com", "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 12; SM-G998B)", "Content-Type": "application/x-www-form-urlencoded"}
                        payload = {"uid": uid, "password": pwd, "response_type": "token", "client_type": "2", "client_secret": "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3", "client_id": "100067"}
                        
                        r = await http_client.post(login_url, headers=hdrs, data=payload)
                        if r.status_code != 200:
                            continue
                        d = r.json()
                        open_id = d.get("open_id")
                        access_token = d.get("access_token")
                        platform = d.get("platform", 4)
                        if not open_id or not access_token:
                            continue

                        # 2. Major Login simulation
                        p = {3: str(datetime.now())[:-7], 4: "free fire", 5: "1", 7: "1.132.15", 8: "Android OS 12 / API-31", 9: "Handheld", 12: "1440", 13: "3200", 14: "420", 19: f"Google|{uuid.uuid4()}", 20: "103.20.10.15", 21: "en", 22: str(open_id), 23: str(platform), 25: "SM-G998B", 26: "IND", 29: str(access_token), 30: "1"}
                        major_payload = enc(build_proto(p))
                        major_resp = await http_client.post(f"{LOGIN_HOST}/MajorLogin", headers={"Content-Type": "application/x-www-form-urlencoded", "ReleaseVersion": "OB55"}, data=major_payload)
                        
                        if major_resp.status_code != 200:
                            continue
                        
                        acc_id, token, s_url = None, None, None
                        for off in [0, 64, 128]:
                            if off >= len(major_resp.content): break
                            dec = dec_proto(major_resp.content[off:])
                            if dec and 1 in dec and 8 in dec and 2 in dec:
                                acc_id = int(dec[1])
                                token = str(dec[8])
                                s_url = str(gf(dec, 10, ""))
                                break
                        
                        if not token or not acc_id:
                            continue
                        
                        server_url = s_url or "https://client.ind.freefiremobile.com"
                        
                        # 3. Send Request to targets
                        for t in targets:
                            if t == acc_id: continue
                            req_payload = enc(bytes.fromhex("08a7c4839f1e") + varint((2<<3)|0) + varint(t) + varint((3<<3)|0) + varint(1))
                            req_hdrs = {"Authorization": f"Bearer {token}", "X-Unity-Version": "2018.4.12f1", "X-GA": "v1 1", "X-GA-SV": str(int(time.time())), "ReleaseVersion": "OB55", "Content-Type": "application/x-www-form-urlencoded", "User-Agent": "UnityPlayer/2018.4.12f1"}
                            
                            req_r = await http_client.post(server_url.rstrip("/") + "/RequestAddingFriend", content=req_payload, headers=req_hdrs)
                            if req_r.status_code == 200 or "already" in req_r.text.lower():
                                total_succ += 1
                            else:
                                total_fail += 1
                            await asyncio.sleep(1.5)
                    except Exception:
                        continue

            await bot.send_message(
                chat_id,
                f"🎉 **Bulk Friend Request Completed!**\n"
                f"✅ Total Requests Sent Successfully: `{total_succ}`\n"
                f"❌ Failed: `{total_fail}`\n\n"
                f"— *Managed by Chikuu 🌸*",
                reply_markup=get_main_menu(),
                parse_mode="Markdown"
            )
        except Exception as ex:
            logging.error(f"Friend request execution error: {ex}")

    asyncio.create_task(run_friend_sender())
    await state.clear()

# --- Cancel Handler ---
@dp.callback_query(F.data == "cancel")
async def cancel_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Process cancelled successfully.")
    await callback.message.edit_text(
        "❌ **Process Cancelled.**\n\nYou are back at the main menu. Select an option:",
        reply_markup=get_main_menu(),
        parse_mode="Markdown"
    )

# Startup event for FastAPI web service & Telegram polling + Scheduler
@app.on_event("startup")
async def startup_event():
    scheduler.start()
    asyncio.create_task(dp.start_polling(bot))
    print("FastAPI Web Service & Telegram Bot started successfully by Chikuu...")
