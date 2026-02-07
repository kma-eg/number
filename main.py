# -*- coding: utf-8 -*-
import telebot
from telebot import types
import requests
import psycopg2
import threading
import time
import random
import os
from flask import Flask

# ==================== 1. بيانات البوت والمفاتيح (تم الدمج بنجاح) ====================
BOT_TOKEN = "6058936352:AAFNKPjfj5A4qMYlyE-KPhBx_BUjSNlbYy0"
API_KEY = "eyJhbGciOiJSUzUxMiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE4MDAxMjk3MzIsImlhdCI6MTc2ODU5MzczMiwicmF5IjoiYjI1MDRmNzVlYzI2MTAzZmQ4MDVhNmZjNTU1OTNlMDgiLCJzdWIiOjM3NDE4NTl9.fChnApox83L626jS4ZajT1Sg0fEiYdqySUDJ9-AWEsNiHDJWv2hRaCk_MAtYJCa3nu1uo4HdTz-y4ug1EsAUbziQJncz5Q91Fh9ADt7LLgm8UyKzP4uFif5XY9rHpQ5zGiA8MN8HNIhtf-bHsJZxBNU0S8GT4VseKb1bbl3PEYB3H6IDSbH3csom0rWzYoySt9RPfOTuqJQlFk5T7TE_h4NjZhFvpt7_chzF2HQoLy0Js1esOyALhyX7D0xjCVet7df3CySYNn70sdJsPYRyEepetjsbq5lzHWg4zE4MOqB7_Q7iFPhQE_-t1v3J1yR1ARq9kMnzgH00I7cKcU0_Fg"
ADMIN_ID = 6318333901

# رابط قاعدة البيانات (Supabase - للحفاظ على الرصيد في Render)
SUPABASE_URL = "postgresql://postgres:5455%40Kma01020755609@aws-0-us-west-2.pooler.supabase.com:6543/postgres"

# ==================== 2. إعدادات القنوات (التقسيمة الجديدة) ====================
# 1. قناة الاشتراك الإجباري (القديمة)
SUB_CHANNEL_ID = -1003316907453
SUB_CHANNEL_LINK = "https://t.me/kma_c"

# 2. قناة التفعيلات والإثباتات (الجديدة)
LOG_CHANNEL_ID = -1003709813767
LOG_CHANNEL_LINK = "https://t.me/kms_ad"

REFERRAL_REWARD = 0.02

# ==================== 3. المحافظ ====================
WALLETS = {
    'vodafone': '01020755609',
    'vodafone2': '01005016893',
    'binance_id': '566079884',
    'bybit_id': '250000893',
    'usdt_address': 'TJuoPbUQepNx8SyUKNnxCU3ti4FeKZsZQx'
}

# ==================== 4. إعداد Webhook لـ Render ====================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is Running 24/7 on Render! 🚀"

def run_web_server():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

# ==================== 5. قاعدة البيانات (Supabase) ====================
def get_db_connection():
    return psycopg2.connect(SUPABASE_URL)

def init_db():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                chat_id BIGINT PRIMARY KEY,
                username TEXT,
                balance FLOAT DEFAULT 0,
                referrer_id BIGINT,
                joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        conn.close()
        print("✅ Database Connected (Supabase)")
    except Exception as e:
        print(f"❌ Database Error: {e}")

# ==================== 6. منطق البوت ====================
bot = telebot.TeleBot(BOT_TOKEN)

COUNTRIES = {
    'canada': '🇨🇦 كندا (Koho)', 
    'egypt': '🇪🇬 مصر', 'saudiarabia': '🇸🇦 السعودية', 'usa': '🇺🇸 أمريكا',
    'russia': '🇷🇺 روسيا', 'brazil': '🇧🇷 البرازيل', 'morocco': '🇲🇦 المغرب',
    'algeria': '🇩🇿 الجزائر', 'iraq': '🇮🇶 العراق', 'unitedkingdom': '🇬🇧 بريطانيا',
    'germany': '🇩🇪 ألمانيا', 'france': '🇫🇷 فرنسا', 'yemen': '🇾🇪 اليمن'
}
SERVICES = {
    'other': '🏦 Koho / Bank (Other)', 
    'whatsapp': '💚 WhatsApp', 'telegram': '💙 Telegram',
    'facebook': '💙 Facebook', 'instagram': '🩷 Instagram',
    'tiktok': '🖤 TikTok', 'google': '❤️ Gmail',
    'twitter': '🖤 X (Twitter)', 'snapchat': '💛 Snapchat'
}

# دوال القاعدة
def add_user(chat_id, username, referrer_id=None):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO users (chat_id, username, referrer_id) VALUES (%s, %s, %s)", (chat_id, username, referrer_id))
        conn.commit()
        return True
    except: return False
    finally: conn.close()

def get_user(chat_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE chat_id = %s", (chat_id,))
    res = cur.fetchone()
    conn.close()
    return res

def update_balance(chat_id, amount):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET balance = balance + %s WHERE chat_id = %s", (amount, chat_id))
    conn.commit()
    conn.close()

user_captchas = {}
user_selections = {}

def gen_captcha():
    a, b = random.randint(1, 9), random.randint(1, 9)
    return {'q': f"{a} + {b} = ?", 'a': str(a+b)}

@bot.message_handler(commands=['start'])
def start_msg(message):
    cid = message.chat.id
    username = message.from_user.username
    args = message.text.split()
    referrer_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else 0
    if referrer_id == cid: referrer_id = 0
    
    add_user(cid, username, referrer_id)
    captcha = gen_captcha()
    user_captchas[cid] = captcha['a']
    bot.send_message(cid, f"🔒 التحقق الأمني\n{captcha['q']}")

@bot.message_handler(func=lambda m: m.chat.id in user_captchas)
def verify_captcha(message):
    cid = message.chat.id
    if message.text.strip() == user_captchas[cid]:
        del user_captchas[cid]
        check_sub_and_open_menu(cid)
    else:
        bot.send_message(cid, "❌ إجابة خاطئة")

def check_sub_and_open_menu(cid):
    try:
        # التحقق من قناة الاشتراك الإجباري فقط
        stat = bot.get_chat_member(SUB_CHANNEL_ID, cid).status
        if stat not in ['member', 'administrator', 'creator']:
            raise Exception("Not Subscribed")
        main_menu(cid)
    except:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 اشترك في القناة", url=SUB_CHANNEL_LINK))
        markup.add(types.InlineKeyboardButton("🔄 تحقق من الاشتراك", callback_data="check_sub"))
        bot.send_message(cid, "⚠️ يجب الاشتراك في القناة أولاً لاستخدام البوت", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_sub_callback(call):
    check_sub_and_open_menu(call.message.chat.id)

def main_menu(cid):
    user = get_user(cid)
    balance = user[2] if user else 0.0
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🛒 شراء أرقام", callback_data="buy"),
        types.InlineKeyboardButton("💰 شحن رصيد", callback_data="deposit_select_amount"),
        types.InlineKeyboardButton("👤 حسابي", callback_data="profile"),
        types.InlineKeyboardButton("🎁 دعوة أصدقاء", callback_data="invite")
    )
    # إضافة زر قناة الإثباتات في القائمة
    markup.add(types.InlineKeyboardButton("✅ قناة التفعيلات (الإثباتات)", url=LOG_CHANNEL_LINK))
    
    if cid == ADMIN_ID:
        markup.add(types.InlineKeyboardButton("👮 لوحة الأدمن", callback_data="admin_panel"))
    bot.send_message(cid, f"👋 أهلاً بك! رصيدك الحالي: {balance:.2f}$\nاختر من القائمة:", reply_markup=markup)

# الشحن
@bot.callback_query_handler(func=lambda call: call.data == "deposit_select_amount")
def deposit_amount_menu(call):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("1 USD 💵", callback_data="dep_amt:1"),
        types.InlineKeyboardButton("3 USD 💵", callback_data="dep_amt:3"),
        types.InlineKeyboardButton("5 USD 💵", callback_data="dep_amt:5"),
        types.InlineKeyboardButton("10 USD 💎", callback_data="dep_amt:10"),
        types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")
    )
    bot.edit_message_text("💰 **شحن الرصيد**\n⚠️ أقل مبلغ للإيداع هو **1$**.", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("dep_amt:"))
def deposit_method_menu(call):
    amount = call.data.split(":")[1]
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("Binance Pay 🟨", callback_data=f"pay_mtd:binance:{amount}"),
        types.InlineKeyboardButton("Bybit Pay ⚫", callback_data=f"pay_mtd:bybit:{amount}"),
        types.InlineKeyboardButton("Vodafone Cash 🇪🇬", callback_data=f"pay_mtd:vodafone:{amount}"),
        types.InlineKeyboardButton("🔙 رجوع", callback_data="deposit_select_amount")
    )
    bot.edit_message_text(f"💳 المبلغ: {amount}$", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_mtd:"))
def pay_info_msg(call):
    parts = call.data.split(":")
    method = parts[1]
    amount = parts[2]
    msg = f"💰 **إيداع {amount}$ عبر {method.upper()}**\n\n"
    if method == 'binance': msg += f"🆔 Binance Pay ID: `{WALLETS['binance_id']}`\n"
    elif method == 'bybit': msg += f"🆔 Bybit UID: `{WALLETS['bybit_id']}`\n"
    elif method == 'vodafone': msg += f"📱 رقم المحفظة: `{WALLETS['vodafone']}`\n"
    msg += "\n📝 أرسل صورة الإيصال هنا."
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="deposit_select_amount"))
    bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(content_types=['photo'])
def handle_receipt(message):
    cid = message.chat.id
    bot.forward_message(ADMIN_ID, cid, message.message_id)
    markup = types.InlineKeyboardMarkup(row_width=4)
    markup.add(
        types.InlineKeyboardButton("✅ 1$", callback_data=f"add:{cid}:1"),
        types.InlineKeyboardButton("✅ 3$", callback_data=f"add:{cid}:3"),
        types.InlineKeyboardButton("✅ 5$", callback_data=f"add:{cid}:5"),
        types.InlineKeyboardButton("✅ 10$", callback_data=f"add:{cid}:10"),
        types.InlineKeyboardButton("❌ رفض", callback_data=f"rej:{cid}")
    )
    bot.send_message(ADMIN_ID, f"📩 إيصال من `{cid}`", reply_markup=markup)
    bot.reply_to(message, "✅ تم الاستلام، جاري المراجعة...")

@bot.callback_query_handler(func=lambda call: call.data.startswith("add:") or call.data.startswith("rej:"))
def admin_process_payment(call):
    if call.from_user.id != ADMIN_ID: return
    parts = call.data.split(":")
    action, uid = parts[0], parts[1]
    if action == "add":
        val = float(parts[2])
        update_balance(uid, val)
        bot.send_message(uid, f"🎉 تم شحن رصيدك: {val}$")
        bot.edit_message_text(f"✅ تم إضافة {val}$ للمستخدم {uid}", call.message.chat.id, call.message.message_id)
    else:
        bot.send_message(uid, "❌ تم رفض الشحن.")
        bot.edit_message_text(f"❌ تم الرفض لـ {uid}", call.message.chat.id, call.message.message_id)

# الشراء
def get_live_stock(country):
    try:
        headers = {'Accept': 'application/json'}
        r = requests.get(f'https://5sim.net/v1/guest/products/{country}/any', headers=headers, timeout=5)
        if r.status_code == 200: return r.json() 
    except: pass
    return {}

@bot.callback_query_handler(func=lambda call: call.data == "buy")
def buy_countries(call):
    markup = types.InlineKeyboardMarkup(row_width=3)
    btns = [types.InlineKeyboardButton(n, callback_data=f"cnt:{k}") for k, n in COUNTRIES.items()]
    markup.add(*btns)
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu"))
    bot.edit_message_text("🌍 **اختر الدولة:**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("cnt:"))
def buy_services(call):
    country = call.data.split(":")[1]
    user_selections[call.from_user.id] = country
    bot.edit_message_text(f"🔄 جاري الاتصال...", call.message.chat.id, call.message.message_id)
    stock_data = get_live_stock(country)
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for srv_key, srv_name in SERVICES.items():
        qty = stock_data.get(srv_key, {}).get('Qty', 0)
        if qty > 0:
            buttons.append(types.InlineKeyboardButton(f"{srv_name} [{qty}]", callback_data=f"srv:{srv_key}"))
        else:
            buttons.append(types.InlineKeyboardButton(f"🚫 {srv_name} (0)", callback_data="none"))
    markup.add(*buttons)
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="buy"))
    bot.edit_message_text(f"🌍 **{COUNTRIES.get(country)}**\n👇 الكميات:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("srv:"))
def execute_buy(call):
    cid = call.message.chat.id
    service = call.data.split(":")[1]
    country = user_selections.get(cid)
    if not country: return bot.answer_callback_query(call.id, "خطأ، حاول مجدداً")
    
    cost = 0.5
    user_bal = get_user(cid)[2]
    if user_bal < cost:
        bot.answer_callback_query(call.id, "❌ رصيدك غير كافي!", show_alert=True)
        return
        
    update_balance(cid, -cost)
    bot.send_message(cid, "🔄 جاري حجز الرقم...")
    try:
        headers = {'Authorization': 'Bearer ' + API_KEY, 'Accept': 'application/json'}
        r = requests.get(f'https://5sim.net/v1/user/buy/activation/{country}/any/{service}', headers=headers)
        if r.status_code == 200:
            data = r.json()
            if 'phone' in data:
                phone = data['phone']
                oid = data['id']
                bot.send_message(cid, f"✅ **تم الشراء!**\n📱 الرقم: `{phone}`\n⏳ الخدمة: {SERVICES.get(service)}\n⚠️ انتظر الكود...", parse_mode="Markdown")
                threading.Thread(target=check_sms, args=(cid, oid, headers, country, service)).start()
            else:
                update_balance(cid, cost)
                bot.send_message(cid, "⚠️ لا توجد أرقام، تم استرداد الرصيد.")
        else:
            update_balance(cid, cost)
            bot.send_message(cid, f"❌ خطأ: {r.text}")
    except Exception as e:
        update_balance(cid, cost)
        bot.send_message(cid, f"Error: {e}")

def check_sms(cid, oid, headers, country, service):
    for _ in range(36): 
        time.sleep(5)
        try:
            r = requests.get(f'https://5sim.net/v1/user/check/{oid}', headers=headers)
            data = r.json()
            if data['status'] == 'RECEIVED':
                code = data['sms'][0]['code']
                phone = data['phone']
                bot.send_message(cid, f"📬 **الكود:** `{code}`", parse_mode="Markdown")
                
                # إرسال الإثبات لقناة الـ LOGS الجديدة
                try:
                    masked = phone[:-4] + "****"
                    msg_ch = f"✅ **تفعيل جديد!** 🚀\n🌍 {COUNTRIES.get(country)}\n📱 {SERVICES.get(service)}\n📞 `{masked}`"
                    markup = types.InlineKeyboardMarkup()
                    bot_url = f"https://t.me/{bot.get_me().username}"
                    markup.add(types.InlineKeyboardButton("🤖 اطلب رقمك الآن", url=bot_url))
                    
                    # الإرسال لقناة التفعيلات
                    bot.send_message(LOG_CHANNEL_ID, msg_ch, parse_mode="Markdown", reply_markup=markup)
                except: pass
                
                return
            elif data['status'] in ['CANCELED', 'TIMEOUT']:
                bot.send_message(cid, "❌ تم الإلغاء.")
                return
        except: pass
    bot.send_message(cid, "⏰ انتهى الوقت.")

@bot.callback_query_handler(func=lambda call: call.data == "profile")
def profile_show(call):
    cid = call.message.chat.id
    user = get_user(cid)
    msg = f"👤 **ملفك**\n🆔 `{cid}`\n💰 رصيدك: `{user[2]}$`"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu"))
    bot.edit_message_text(msg, cid, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "invite")
def invite_link(call):
    cid = call.message.chat.id
    bot_user = bot.get_me().username
    link = f"https://t.me/{bot_user}?start={cid}"
    msg = f"🎁 **اربح {REFERRAL_REWARD}$**\nرابطك:\n`{link}`"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu"))
    bot.edit_message_text(msg, cid, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "admin_panel")
def admin_menu_func(call):
    if call.from_user.id != ADMIN_ID: return
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu"))
    bot.edit_message_text("👮 لوحة التحكم", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def back_main(call):
    main_menu(call.message.chat.id)

# تشغيل البوت + السيرفر (Render)
if __name__ == "__main__":
    init_db()
    t = threading.Thread(target=run_web_server)
    t.start()
    print("🤖 Bot & Web Server Started for Render...")
    bot.infinity_polling(skip_pending=True)
