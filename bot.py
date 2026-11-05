# ============================================================
#  ADVANCED TELEGRAM AUTOMATION BOT — by CHIKUU
# ============================================================
import asyncio
import logging
import json
import os
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import httpx

# Token environment variable se uthayega Render par, ya direct string daal sakte ho
TOKEN = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# API Configuration
JWT_API_BASE = "https://rosyy-jwt-genrator.vercel.app/token"

class BotStates(StatesGroup):
    waiting_for_auto_json = State()
    waiting_for_req_json = State()

# --- Keyboards ---
def get_main_menu():
    keyboard = [
        [types.InlineKeyboardButton(text="🔄 Auto Process & GitHub Sync", callback_data="auto_process")],
        [types.InlineKeyboardButton(text="📨 Req Send Button", callback_data="req_send")],
        [types.InlineKeyboardButton(text="📝 Add Long Bio", callback_data="long_bio")]
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_cancel_menu():
    # Sirf Cancel button dikhega jab process chal raha ho
    keyboard = [
        [types.InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")]
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)

# --- Start Command ---
@dp.message(Command("start"))
async def start_handler(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "✨ **Welcome to Automated JWT & Request Bot** ✨\n"
        "Developed & Managed by **Chikuu** 🚀\n\n"
        "Neeche diye gaye buttons me se apna option select karein:",
        reply_markup=get_main_menu(),
        parse_mode="Markdown"
    )

# --- Add Long Bio Button Handler ---
@dp.callback_query(F.data == "long_bio")
async def long_bio_handler(callback: types.CallbackQuery):
    await callback.answer("Coming Soon!", show_alert=True)
    await callback.message.edit_text(
        "📝 **Add Long Bio**\n\n⚠️ Ye feature jald hi launch kiya jayega! **Coming Soon 🚧**\n\n— *Powered by Chikuu*",
        reply_markup=get_main_menu(),
        parse_mode="Markdown"
    )

# --- Auto Process / GitHub Sync Handler ---
@dp.callback_query(F.data == "auto_process")
async def auto_process_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(BotStates.waiting_for_auto_json)
    # Yahan sirf cancel button aayega, baki sab hat jayenge
    await callback.message.edit_text(
        "🔄 **Auto Process & GitHub Sync**\n\n"
        "Kripya apni `.json` file bhejein jisme accounts (UID + Password) ki list ho.\n\n"
        "⚠️ *Process chal raha hai, dusra command chalane ke liye pehle cancel karein.*",
        reply_markup=get_cancel_menu(),
        parse_mode="Markdown"
    )

# --- Process Auto JSON & Generate Tokens via API ---
@dp.message(BotStates.waiting_for_auto_json, F.document)
async def handle_auto_json_file(message: types.Message, state: FSMContext):
    document = message.document
    if not document.file_name.endswith('.json'):
        await message.answer("❌ Kripya sirf valid `.json` file hi upload karein!", reply_markup=get_cancel_menu())
        return

    file = await bot.get_file(document.file_id)
    file_bytes = await bot.download_file(file.file_path)
    
    try:
        accounts = json.loads(file_bytes.read().decode('utf-8'))
        if not isinstance(accounts, list):
            raise ValueError("JSON must be a list of objects.")
        
        status_msg = await message.answer(
            "⏳ Processing accounts and fetching tokens via API... Live updates shuru ho rahe hain ⚡",
            reply_markup=get_cancel_menu()
        )
        
        region_tokens = {}
        success_count = 0
        fail_count = 0

        async with httpx.AsyncClient(timeout=15.0) as client_http:
            for i, acc in enumerate(accounts[:50], 1):
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
                
                if i % 5 == 0:
                    try:
                        await status_msg.edit_text(
                            f"⚡ Live Processing...\n✅ Success: {success_count}\n❌ Failed: {fail_count}",
                            reply_markup=get_cancel_menu()
                        )
                    except Exception:
                        pass

        saved_files_text = ""
        for reg, toks in region_tokens.items():
            filename = f"token_{reg}.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(toks, f, indent=2)
            saved_files_text += f"\n📁 `{filename}` ({len(toks)} tokens)"

        await message.answer(
            f"🎉 **Auto Process Completed!**\n"
            f"✅ Successfully Processed: `{success_count}`\n"
            f"❌ Failed: `{fail_count}`\n\n"
            f"📂 **Generated Files:**{saved_files_text}\n\n"
            f"— *System managed by Chikuu 🌸*",
            reply_markup=get_main_menu(),
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.answer(f"❌ Error parsing file: `{str(e)}`", reply_markup=get_main_menu())
    
    await state.clear()

# --- Req Send Button Handler ---
@dp.callback_query(F.data == "req_send")
async def req_send_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(BotStates.waiting_for_req_json)
    # Yahan bhi sirf cancel button aayega
    await callback.message.edit_text(
        "📨 **Request Sender System**\n\n"
        "Kripya apni accounts wali `.json` file upload karein jisse bot log in karke requests bhej sake.\n\n"
        "⚠️ *Process chal raha hai, dusra command chalane ke liye pehle cancel karein.*",
        reply_markup=get_cancel_menu(),
        parse_mode="Markdown"
    )

@dp.message(BotStates.waiting_for_req_json, F.document)
async def handle_req_file(message: types.Message, state: FSMContext):
    document = message.document
    file = await bot.get_file(document.file_id)
    file_bytes = await bot.download_file(file.file_path)
    
    try:
        accounts = json.loads(file_bytes.read().decode('utf-8'))
        await message.answer(
            f"✅ File loaded successfully! Total accounts found: `{len(accounts)}`.\n🎯 Ab apne target UIDs bhejein.",
            reply_markup=get_main_menu()
        )
    except Exception as e:
        await message.answer(f"❌ Error: `{str(e)}`", reply_markup=get_main_menu())
    await state.clear()

# --- Cancel Handler ---
@dp.callback_query(F.data == "cancel")
async def cancel_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Process cancelled successfully.")
    await callback.message.edit_text(
        "❌ **Process Cancelled.**\n\nMain menu par wapas aa gaye hain. Niche diye gaye options me se select karein:",
        reply_markup=get_main_menu(),
        parse_mode="Markdown"
    )

async def main():
    print("Bot started successfully by Chikuu...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[STOPPED]")
        