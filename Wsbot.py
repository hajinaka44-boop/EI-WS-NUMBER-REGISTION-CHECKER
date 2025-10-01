import logging
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.error import BadRequest
import requests

# --- CONFIGURATION ---
# 1. Fill in your bot token from BotFather
TELEGRAM_BOT_TOKEN = "7727850131:AAFM4IzhdGjZtbEoKRfGOMkrNxSxn11wwSc"

# 2. Fill in your API token from whapi.cloud
WHAPI_API_TOKEN = "7bll65fpJmnZSi7SaXWgCZpcFb7hg5xX"

# 3. Your channel username. The bot MUST be an admin in this channel.
CHANNEL_USERNAME = "@wsceko" 
# --- END OF CONFIGURATION ---


# --- CONSTANTS ---
WHAPI_API_URL = "https://gate.whapi.cloud/contacts"
CREATOR_CREDIT = "Made By EI TECH METHOD"
# --- END OF CONSTANTS ---

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- HELPER FUNCTION: CHECK CHANNEL MEMBERSHIP (PERMANENT FIX) ---
async def is_user_subscribed(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Checks if a user is a member of the required channel.
    This version uses raw strings ('left', 'kicked') to be compatible with ALL versions 
    of the python-telegram-bot library. This is the permanent fix.
    """
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        
        # The user's status is returned as a string (e.g., 'member', 'administrator', 'left').
        # We check against the raw strings to avoid library version issues.
        if member.status not in ['left', 'kicked']:
            return True
        else:
            return False
    except BadRequest as e:
        if "user not found" in e.message.lower():
            return False
        logger.error(f"BadRequest when checking membership for user {user_id}: {e}")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred when checking membership for user {user_id}: {e}")
        return False

# --- API INTEGRATION FUNCTION ---
def check_whatsapp_with_whapi(phone_number: str) -> dict:
    """Calls the whapi.cloud API to check a single number."""
    logger.info(f"Checking number with whapi.cloud API: {phone_number}")
    headers = {'Authorization': f'Bearer {WHAPI_API_TOKEN}', 'Content-Type': 'application/json'}
    payload = {"blocking": "wait", "contacts": [phone_number]}

    try:
        response = requests.post(WHAPI_API_URL, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        api_data = response.json()
        logger.info(f"API Response: {api_data}")
        if "contacts" in api_data and api_data["contacts"]:
            status = api_data["contacts"][0].get("status")
            return {'status': 'success', 'registered': status == "valid"}
        return {'status': 'error', 'message': 'Unexpected API format.'}
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            return {'status': 'error', 'message': 'Authentication failed. API Token is incorrect.'}
        return {'status': 'error', 'message': f'API server error (Code: {e.response.status_code}).'}
    except requests.exceptions.RequestException:
        return {'status': 'error', 'message': 'Could not connect to the checker service.'}

# --- TELEGRAM BOT HANDLERS ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /start command and the force join process."""
    user = update.effective_user
    
    if await is_user_subscribed(user.id, context):
        welcome_message = f"👋 *Welcome back, {user.first_name}!* \n\n🤖 I am ready to work. Send me any phone number(s) to check."
        await update.message.reply_text(welcome_message, parse_mode='Markdown')
    else:
        join_channel_url = f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Our Channel", url=join_channel_url)],
            [InlineKeyboardButton("✅ Verify Subscription", callback_data="verify_join")]
        ])
        join_message = (
            f"Hi {user.first_name}!\n\n"
            f"⚠️ To use this bot, you **must subscribe** to our official channel.\n\n"
            f"1. Click the button below to join **{CHANNEL_USERNAME}**.\n"
            "2. Return here and click **Verify Subscription**."
        )
        await update.message.reply_text(join_message, reply_markup=keyboard)

async def verify_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the 'Verify Subscription' button click."""
    query = update.callback_query
    user = query.from_user

    await query.answer(text="Checking your subscription status...", show_alert=False)

    if await is_user_subscribed(user.id, context):
        await query.edit_message_text(
            text=f"✅ *Verification Successful!* \n\nThank you for subscribing, {user.first_name}. You can now use the bot.",
            parse_mode='Markdown',
            reply_markup=None
        )
    else:
        await query.answer(
            text="❌ You are not yet subscribed. Please join the channel and try again.",
            show_alert=True
        )

async def handle_any_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """A central handler for all text messages to check for subscription first."""
    user = update.effective_user
    if not await is_user_subscribed(user.id, context):
        await start_command(update, context)
        return
    
    user_input = update.message.text
    phone_numbers = re.findall(r'\d{10,}', user_input)

    if not phone_numbers:
        await update.message.reply_text("🤔 I couldn't find any valid phone numbers. Please send numbers with country code (e.g., 919876543210).")
        return

    await update.message.reply_text(f"🔍 Found {len(phone_numbers)} number(s). Checking now, please wait...")

    results = []
    for number in phone_numbers:
        result = check_whatsapp_with_whapi(number)
        if result['status'] == 'success':
            status_emoji = "✅" if result['registered'] else "❌"
            status_text = "HAS WhatsApp" if result['registered'] else "DOES NOT have WhatsApp"
            results.append(f"{status_emoji} `{number}`: **{status_text}**")
        else:
            results.append(f"⚠️ `{number}`: Error - {result['message']}")
    
    final_response = "--- *Check Results* ---\n\n" + "\n".join(results)
    await update.message.reply_text(final_response, parse_mode='Markdown')

def main() -> None:
    """Start the bot."""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(verify_join_callback, pattern="^verify_join$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_any_message))

    logger.info("Bot is starting with permanent verification fix...")
    application.run_polling()

if __name__ == '__main__':
    main()
