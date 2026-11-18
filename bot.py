import asyncio
import logging
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from playwright.async_api import async_playwright

# هنجيب التوكن من إعدادات Render (Environment Variables) للأمان
TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

router = Router()
bot = Bot(token=TOKEN)
storage = MemoryStorage()

class BotStates(StatesGroup):
    waiting_for_student_code = State()
    waiting_for_password = State()

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="📚 أولى ثانوي", callback_data="grade_1"),
        types.InlineKeyboardButton(text="📚 تانية ثانوي", callback_data="grade_2")
    )
    builder.row(types.InlineKeyboardButton(text="📊 إحصائياتي", callback_data="stats"))
    builder.row(types.InlineKeyboardButton(text="🎉 مسابقة", callback_data="quiz"))
    builder.row(types.InlineKeyboardButton(text="💻 DEV", url="https://t.me/YOUR_USERNAME"))

    await message.answer(
        "👋 أهلاً بك يا بطل في بوت المساعد الذكي 🏴‍☠️!\n\nاختر صفك الدراسي:",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data.startswith("grade_"))
async def select_grade(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="🏛️ عام", callback_data="type_A"),
        types.InlineKeyboardButton(text="🕌 أزهر", callback_data="type_Azhar")
    )
    builder.row(types.InlineKeyboardButton(text="⬅️ رجوع", callback_data="back_to_start"))

    await callback.message.edit_text("✅ اخترت الصف الدراسي\n\nاختر النوع:", reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data.startswith("type_"))
async def select_type(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="☕ JavaScript", callback_data="sub_js"))
    builder.row(types.InlineKeyboardButton(text="🐍 Python", callback_data="sub_python"))
    builder.row(types.InlineKeyboardButton(text="📦 الثقافة المالية", callback_data="sub_financial"))
    builder.row(types.InlineKeyboardButton(text="⬅️ رجوع", callback_data="back_to_grades"))

    await callback.message.edit_text("✅ اخترت النوع\n\nاختر المادة:", reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data == "sub_financial")
async def select_financial(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(BotStates.waiting_for_student_code)
    await callback.message.edit_text("📦 اخترت الثقافة المالية\n\n📝 أرسل كود الطالب الآن:")
    await callback.answer()

@router.message(BotStates.waiting_for_student_code)
async def get_student_code(message: types.Message, state: FSMContext):
    await state.update_data(student_code=message.text)
    await state.set_state(BotStates.waiting_for_password)
    await message.answer(f"👤 كود الطالب: {message.text}\n\n🔑 أرسل كلمة المرور:")

@router.message(BotStates.waiting_for_password)
async def get_password(message: types.Message, state: FSMContext):
    password = message.text
    data = await state.get_data()
    student_code = data.get("student_code")

    status_msg = await message.answer("⏳ جاري تسجيل الدخول وحل الثقافة المالية على منصة SPX...\nيرجى الانتظار 🔄")

    try:
        result_message = await run_spx_automation(student_code, password)
        await status_msg.edit_text(f"✅ {result_message}")
    except Exception as e:
        await status_msg.edit_text(f"❌ حدث خطأ أثناء التنفيذ:\n{str(e)}")
    
    await state.clear()

async def run_spx_automation(code, password):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto("https://egy.app.spx-learning-square.com/dashboard")
        await page.wait_for_load_state("networkidle")

        await page.fill("input[type='text'], input[name='code'], input[placeholder*='كود']", code)
        await page.fill("input[type='password']", password)
        
        await page.click("button[type='submit'], button:has-text('دخول'), button:has-text('تسجيل')")
        await page.wait_for_load_state("networkidle")

        await page.click("text=الثقافة المالية")
        await page.wait_for_load_state("networkidle")
        await page.click("text=ابدأ, text=حل, text=بدء")

        while True:
            try:
                option_btn = page.locator(".option-item, .answer-option, label.choice").first
                if await option_btn.is_visible():
                    await option_btn.click()
                
                next_btn = page.locator("button:has-text('التالي'), button:has-text('السؤال التالي')")
                if await next_btn.is_visible():
                    await next_btn.click()
                    await page.wait_for_timeout(400)
                else:
                    submit_btn = page.locator("button:has-text('إرسال'), button:has-text('تسليم')")
                    if await submit_btn.is_visible():
                        await submit_btn.click()
                    break
            except:
                break

        await browser.close()
        return "تم حل جميع أسئلة الثقافة المالية بنجاح على منصة SPX! 🚀"

# سيرفر ويب خفيف عشان Render يتأكد إن البوت شغال وميقفلهوش
async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    await start_web_server()
    dp = Dispatcher(storage=storage)
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    print("🤖 البوت يعمل الآن على Render...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
