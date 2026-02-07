
# -*- coding: utf-8 -*-
import telebot
from telebot import types
import requests
import psycopg2
import threading
import time
import random
import string
import os
from datetime import datetime
from flask import Flask

# ==================== 1. إعدادات البوت والأسعار ====================
BOT_TOKEN = "6058936352:AAFNKPjfj5A4qMYlyE-KPhBx_BUjSNlbYy0"
API_KEY = "eyJhbGciOiJSUzUxMiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE4MDAxMjk3MzIsImlhdCI6MTc2ODU5MzczMiwicmF5IjoiYjI1MDRmNzVlYzI2MTAzZmQ4MDVhNmZjNTU1OTNlMDgiLCJzdWIiOjM3NDE4NTl9.fChnApox83L626jS4ZajT1Sg0fEiYdqySUDJ9-AWEsNiHDJWv2hRaCk_MAtYJCa3nu1uo4HdTz-y4ug1EsAUbziQJncz5Q91Fh9ADt7LLgm8UyKzP4uFif5XY9rHpQ5zGiA8MN8HNIhtf-bHsJZxBNU0S8GT4VseKb1bbl3PEYB3H6IDSbH3csom0rWzYoySt9RPfOTuqJQlFk5T7TE_h4NjZhFvpt7_chzF2HQoLy0Js1esOyALhyX7D0xjCVet7df3CySYNn70sdJsPYRyEepetjsbq5lzHWg4zE4MOqB7_Q7iFPhQE_-t1v3J1yR1ARq9kMnzgH00I7cKcU0_Fg"
ADMIN_ID = 6318333901

SUPABASE_URL = "postgresql://postgres.rjialktdutmbuqhaznzu:5455%40Kma01020755609@aws-0-us-west-2.pooler.supabase.com:6543/postgres"

# القنوات
SUB_CHANNEL_ID = -1003316907453
SUB_CHANNEL_LINK = "https://t.me/kma_c"
LOG_CHANNEL_ID = -1003709813767
LOG_CHANNEL_LINK = "https://t.me/kms_ad"

# === إعدادات الماليات (مهم جداً) ===
REFERRAL_REWARD = 0.02
DEPOSIT_RATE = 50.0    # سعر الدولار عند الإيداع (المستخدم يدفع 50 عشان ياخد 1 دولار)
WITHDRAW_RATE = 47.0   # سعر الدولار عند السحب (المستخدم يسحب 1 دولار ياخد 47 جنيه)
MIN_WITHDRAW = 1.0     # أقل مبلغ للسحب

WALLETS = {
    'vodafone': '01020755609',
    'vodafone2': '01005016893',
    'binance_id': '566079884',
    'bybit_id': '250000893',
    'usdt_address': 'TJuoPbUQepNx8SyUKNnxCU3ti4FeKZsZQx'
}

# متغيرات مؤقتة
user_data_cache = {} # لتخزين بيانات السحب المؤقتة
user_sessions = {}
user_captchas = {}
user_selections = {}

# ==================== 2. السيرفر وقاعدة البيانات ====================
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is Running 🚀"
def run_web_server():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

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
                joined_date DATE DEFAULT CURRENT_DATE,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        conn.close()
    except Exception as e: print(f"DB Error: {e}")

def add_user(chat_id, username, referrer_id=None):
    conn = get_db_connection()
    cur = conn.cursor()
    status = "ERROR"
    last_seen = None
    try:
        cur.execute("SELECT chat_id, last_seen FROM users WHERE chat_id = %s", (chat_id,))
        res = cur.fetchone()
        if res:
            status = "EXISTS"
            last_seen = res[1]
            cur.execute("UPDATE users SET last_seen = NOW() WHERE chat_id = %s", (chat_id,))
        else:
            cur.execute("INSERT INTO users (chat_id, username, referrer_id, joined_date, last_seen) VALUES (%s, %s, %s, CURRENT_DATE, NOW())", (chat_id, username, referrer_id))
            status = "NEW"
        conn.commit()
    except Exception as e: print(f"Add User Error: {e}")
    finally: conn.close()
    return status, last_seen

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

def get_referrals_count(chat_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users WHERE referrer_id = %s", (chat_id,))
    res = cur.fetchone()
    conn.close()
    return res[0] if res else 0

# ==================== 3. بداية البوت ====================
bot = telebot.TeleBot(BOT_TOKEN)

def gen_captcha():
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(5))

@bot.message_handler(commands=['start'])
def start_msg(message):
    cid = message.chat.id
    username = message.from_user.username or "Unknown"
    
    # تسجيل المستخدم
    args = message.text.split()
    referrer_id = int(args[1]) if len(args) > 1 and args[1].isdigit() and int(args[1]) != cid else None
    
    status, last_seen = add_user(cid, username, referrer_id)
    
    if status == "NEW" and referrer_id:
        update_balance(referrer_id, REFERRAL_REWARD)
        update_balance(cid, REFERRAL_REWARD)
        bot.send_message(referrer_id, f"🎉 **دعوة ناجحة!**\nتم إضافة {REFERRAL_REWARD}$ لرصيدك.")
        # إشعار أدمن (عضو جديد)
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        total = cur.fetchone()[0]
        conn.close()
        bot.send_message(ADMIN_ID, f"🆕 **عضو جديد**\nName: {message.from_user.first_name}\nID: `{cid}`\nTotal: {total}", parse_mode="Markdown")

    elif status == "EXISTS" and last_seen:
        # إشعار العودة (كل أسبوعين فقط)
        if isinstance(last_seen, str): last_seen = datetime.strptime(last_seen, '%Y-%m-%d %H:%M:%S.%f')
        if (datetime.now() - last_seen).days > 14:
            bot.send_message(ADMIN_ID, f"♻️ **عودة مستخدم**\nName: {message.from_user.first_name}\nID: `{cid}`", parse_mode="Markdown")

    # كابتشا (كل ساعة)
    if time.time() - user_sessions.get(cid, 0) > 3600:
        code = gen_captcha()
        user_captchas[cid] = code
        bot.send_message(cid, f"🔒 **التحقق الأمني**\nاكتب الكود: `{code}`", parse_mode="Markdown")
    else:
        main_menu(cid)

@bot.message_handler(func=lambda m: m.chat.id in user_captchas)
def verify_captcha(message):
    cid = message.chat.id
    if message.text.strip() == user_captchas[cid]:
        del user_captchas[cid]
        user_sessions[cid] = time.time()
        main_menu(cid)
    else:
        bot.send_message(cid, "❌ كود خاطئ.")

def main_menu(cid, msg_id=None):
    user = get_user(cid)
    bal = user[2] if user else 0.0
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🛒 شراء أرقام", callback_data="buy"),
        types.InlineKeyboardButton("💰 شحن رصيد", callback_data="deposit_start"),
        types.InlineKeyboardButton("🏦 سحب رصيد", callback_data="withdraw_start"),
        types.InlineKeyboardButton("👤 حسابي", callback_data="profile"),
        types.InlineKeyboardButton("🎁 دعوة أصدقاء", callback_data="invite"),
        types.InlineKeyboardButton("✅ قناة التفعيلات", url=LOG_CHANNEL_LINK)
    )
    if cid == ADMIN_ID:
        markup.add(types.InlineKeyboardButton("👮 لوحة الأدمن", callback_data="admin_panel"))
    
    text = f"👋أهلاً بك!\n💰 رصيدك: `{bal:.2f}$`\nاختر خدمتك:"
    if msg_id: bot.edit_message_text(text, cid, msg_id, reply_markup=markup, parse_mode="Markdown")
    else: bot.send_message(cid, text, reply_markup=markup, parse_mode="Markdown")

# ==================== 4. نظام الشحن (Deposit) ====================
@bot.callback_query_handler(func=lambda call: call.data == "deposit_start")
def deposit_region(call):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🇪🇬 أنا داخل مصر", callback_data="dep_loc:eg"),
        types.InlineKeyboardButton("🌍 أنا خارج مصر", callback_data="dep_loc:global"),
        types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")
    )
    bot.edit_message_text("🌍 حدد موقعك لعرض طرق الدفع المتاحة:**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("dep_loc:"))
def deposit_methods(call):
    loc = call.data.split(":")[1]
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    # خيارات مصر (فودافون + كريبتو)
    if loc == "eg":
        markup.add(types.InlineKeyboardButton(f"Vodafone Cash (1$ = {int(DEPOSIT_RATE)} EGP)", callback_data="dep_pay:vf"))
        markup.add(types.InlineKeyboardButton("Binance Pay (USDT)", callback_data="dep_pay:binance"))
        markup.add(types.InlineKeyboardButton("Bybit Pay (USDT)", callback_data="dep_pay:bybit"))
        markup.add(types.InlineKeyboardButton("USDT (TRC20)", callback_data="dep_pay:trc20"))
    # خيارات خارج مصر (كريبتو فقط)
    else:
        markup.add(types.InlineKeyboardButton("Binance Pay (USDT)", callback_data="dep_pay:binance"))
        markup.add(types.InlineKeyboardButton("Bybit Pay (USDT)", callback_data="dep_pay:bybit"))
        markup.add(types.InlineKeyboardButton("USDT (TRC20)", callback_data="dep_pay:trc20"))
        
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="deposit_start"))
    bot.edit_message_text("💰 اختر وسيلة الدفع:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("dep_pay:"))
def deposit_details(call):
    method = call.data.split(":")[1]
    cid = call.message.chat.id
    
    msg = ""
    # رسالة فودافون كاش (تظهر بالمصري)
    if method == "vf":
        msg = (f"🇪🇬 شحن فودافون كاش\n\n"
               f"📱 رقم المحفظة: `{WALLETS['vodafone']}`\n"
               f"💵 سعر الصرف 1$ = {int(DEPOSIT_RATE)} جنيه**\n\n"
               f"⚠️ تعليمات هامة:\n"
               f"1. حول المبلغ المطلوب بالضبط.\n"
               f"2. أرسل صورة الإيصال هنا ليتم إضافة الرصيد.")
    
    # رسائل الكريبتو (تظهر بالدولار فقط)
    elif method == "binance":
        msg = (f"🔶 شحن Binance Pay\n\n"
               f"🆔 Pay ID: `{WALLETS['binance_id']}`\n\n"
               f"📸 أرسل صورة العملية هنا.")
    elif method == "bybit":
        msg = (f"⚫ شحن Bybit Pay\n\n"
               f"🆔 UID: `{WALLETS['bybit_id']}`\n\n"
               f"📸 أرسل صورة التحويل هنا.")
    elif method == "trc20":
        msg = (f"🕸 شحن USDT (TRC20)\n\n"
               f"🔗 العنوان: `{WALLETS['usdt_address']}`\n\n"
               f"📸 أرسل صورة التحويل (TXID) هنا.")

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="deposit_start"))
    bot.edit_message_text(msg, cid, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

# استقبال الإيصالات
@bot.message_handler(content_types=['photo'])
def handle_deposit_proof(message):
    cid = message.chat.id
    bot.forward_message(ADMIN_ID, cid, message.message_id)
    
    # أزرار الأدمن للقبول/الرفض
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(
        types.InlineKeyboardButton("✅ 1$", callback_data=f"adm_dep:{cid}:1"),
        types.InlineKeyboardButton("✅ 3$", callback_data=f"adm_dep:{cid}:3"),
        types.InlineKeyboardButton("✅ 5$", callback_data=f"adm_dep:{cid}:5"),
        types.InlineKeyboardButton("✅ 10$", callback_data=f"adm_dep:{cid}:10"),
        types.InlineKeyboardButton("❌ رفض", callback_data=f"adm_rej:{cid}")
    )
    bot.send_message(ADMIN_ID, f"📩 إيصال إيداع من: `{cid}`", reply_markup=markup, parse_mode="Markdown")
    bot.reply_to(message, "✅ تم استلام الإيصال!\nجاري المراجعة، سيصلك إشعار قريباً.")

# ==================== 5. نظام السحب (Withdraw) - الجديد ====================
@bot.callback_query_handler(func=lambda call: call.data == "withdraw_start")
def withdraw_menu(call):
    markup = types.InlineKeyboardMarkup(row_width=1)
    # فودافون كاش بسعر 47
    markup.add(types.InlineKeyboardButton(f"Vodafone Cash (1$ = {int(WITHDRAW_RATE)} EGP)", callback_data="wd_mtd:vf"))
    # الكريبتو دولار بدولار
    markup.add(types.InlineKeyboardButton("Binance Pay (USDT)", callback_data="wd_mtd:binance"))
    markup.add(types.InlineKeyboardButton("Bybit (USDT)", callback_data="wd_mtd:bybit"))
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu"))
    
    bot.edit_message_text("🏦 سحب الرصيد\nاختر وسيلة السحب:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("wd_mtd:"))
def withdraw_amount_ask(call):
    method = call.data.split(":")[1]
    cid = call.message.chat.id
    user_data_cache[cid] = {'method': method}
    
    msg = bot.send_message(cid, f"💰 كم تريد أن تسحب؟\n(أقل مبلغ: {MIN_WITHDRAW}$)\nأرسل المبلغ فقط (رقم):")
    bot.register_next_step_handler(msg, process_withdraw_amount)

def process_withdraw_amount(message):
    cid = message.chat.id
    try:
        amount = float(message.text)
        user = get_user(cid)
        balance = user[2] if user else 0.0
        
        if amount < MIN_WITHDRAW:
            bot.reply_to(message, f"❌ أقل مبلغ للسحب هو {MIN_WITHDRAW}$")
            return
        if amount > balance:
            bot.reply_to(message, "❌ رصيدك غير كافي!")
            return
            
        user_data_cache[cid]['amount'] = amount
        method = user_data_cache[cid]['method']
        
        # حساب القيمة بالمصري لو فودافون
        extra_txt = ""
        if method == "vf":
            egp_val = int(amount * WITHDRAW_RATE)
            extra_txt = f"\n💵 ستستلم: {egp_val} جنيه (سعر الصرف {int(WITHDRAW_RATE)})"
            prompt = "📱 أرسل رقم محفظة فودافون كاش:"
        else:
            extra_txt = f"\n💵 ستستلم: {amount} USDT"
            prompt = "🆔 أرسل الـ ID أو عنوان المحفظة:"
            
        msg = bot.send_message(cid, f"✅ المبلغ: {amount}${extra_txt}\n\n{prompt}\n\n⚠️ تنبيه هام:** تأكد من الرقم/العنوان جيداً. لا يوجد استرداد للأموال في حالة الخطأ!")
        bot.register_next_step_handler(msg, process_withdraw_confirm)
        
    except ValueError:
        bot.reply_to(message, "❌ الرجاء إرسال رقم صحيح.")

def process_withdraw_confirm(message):
    cid = message.chat.id
    wallet_info = message.text
    data = user_data_cache.get(cid)
    
    if not data: return
    amount = data['amount']
    method = data['method']
    
    # خصم الرصيد مبدئياً
    update_balance(cid, -amount)
    
    # إشعار للأدمن
    method_name = "Vodafone Cash" if method == "vf" else method.title()
    val_txt = f"{int(amount * WITHDRAW_RATE)} EGP" if method == "vf" else f"{amount} USDT"
    
    admin_markup = types.InlineKeyboardMarkup()
    admin_markup.add(
        types.InlineKeyboardButton("✅ تم التحويل", callback_data=f"wd_ok:{cid}:{amount}"),
        types.InlineKeyboardButton("❌ رفض وإرجاع الرصيد", callback_data=f"wd_no:{cid}:{amount}")
    )
    
    log = (f"📤 طلب سحب جديد\n"
           f"👤 العضو: `{cid}`\n"
           f"💰 المبلغ: `{amount}$`\n"
           f"🏦 الوسيلة: {method_name}\n"
           f"📥 القيمة المستحقة: `{val_txt}`\n"
           f"📝 العنوان/الرقم: `{wallet_info}`")
           
    bot.send_message(ADMIN_ID, log, reply_markup=admin_markup, parse_mode="Markdown")
    bot.send_message(cid, "✅ تم استلام طلب السحب.\nسيتم المراجعة والتحويل قريباً.")

# ==================== 6. معالجة قرارات الأدمن ====================
@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_") or call.data.startswith("wd_"))
def admin_decisions(call):
    if call.from_user.id != ADMIN_ID: return
    action = call.data
    
    # قبول الإيداع
    if "adm_dep" in action:
        _, uid, amt = action.split(":")
        update_balance(int(uid), float(amt))
        bot.send_message(int(uid), f"✅ تم قبول الإيداع!\n💰 رصيدك الحالي زاد: {amt}$")
        bot.edit_message_text(f"✅ تم شحن {amt}$ لـ {uid}", call.message.chat.id, call.message.message_id)
        
    # رفض الإيداع
    elif "adm_rej" in action:
        uid = int(action.split(":")[1])
        bot.send_message(uid, "❌ تم رفض الإيداع.\nالبيانات غير مطابقة.")
        bot.edit_message_text(f"❌ تم الرفض لـ {uid}", call.message.chat.id, call.message.message_id)

    # قبول السحب
    elif "wd_ok" in action:
        _, uid, amt = action.split(":")
        bot.send_message(int(uid), f"✅ تم تنفيذ السحب بنجاح!\nتم تحويل المبلغ إليك.")
        bot.edit_message_text(f"✅ تم تأكيد السحب لـ {uid}", call.message.chat.id, call.message.message_id)

    # رفض السحب (إرجاع الرصيد)
    elif "wd_no" in action:
        _, uid, amt = action.split(":")
        update_balance(int(uid), float(amt)) # إرجاع الرصيد
        bot.send_message(int(uid), f"❌ تم رفض طلب السحب.\nتم إعادة {amt}$ إلى رصيدك بالبوت.")
        bot.edit_message_text(f"❌ تم رفض السحب وإرجاع الرصيد لـ {uid}", call.message.chat.id, call.message.message_id)

# ==================== 7. حسابي (Profile) ====================
@bot.callback_query_handler(func=lambda call: call.data == "profile")
def show_profile(call):
    cid = call.message.chat.id
    user = get_user(cid)
    if not user: return
    
    # user tuple: (chat_id, username, balance, referrer_id, joined_date, last_seen)
    bal = user[2]
    join_date = user[4]
    invites = get_referrals_count(cid)
    
    msg = (f"👤 حسابي\n\n"
           f"🆔 ID: `{cid}`\n"
           f"💰 الرصيد: `{bal:.2f}$`\n"
           f"👥 الدعوات: `{invites} صديق`\n"
           f"📅 انضممت منذ: `{join_date}`")
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu"))
    bot.edit_message_text(msg, cid, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

# ==================== 8. لوحة الأدمن (مصلحة) ====================
@bot.callback_query_handler(func=lambda call: call.data == "admin_panel")
def admin_panel_menu(call):
    if call.from_user.id != ADMIN_ID: return
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*), SUM(balance) FROM users")
    stats = cur.fetchone()
    conn.close()
    
    users = stats[0]
    money = stats[1] if stats[1] else 0.0
    
    msg = (f"👮 لوحة التحكم\n"
           f"👥 المستخدمين: `{users}`\n"
           f"💰 إجمالي الأرصدة: `{money:.2f}$`")
           
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📢 إذاعة", callback_data="adm_act:bc"),
        types.InlineKeyboardButton("➕ شحن يدوي", callback_data="adm_act:add"),
        types.InlineKeyboardButton("➖ خصم يدوي", callback_data="adm_act:sub"),
        types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")
    )
    bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_act:"))
def admin_actions(call):
    act = call.data.split(":")[1]
    cid = call.message.chat.id
    
    if act == "bc":
        m = bot.send_message(cid, "📢 أرسل الرسالة للإذاعة:\n(أرسل 'إلغاء' للتراجع)")
        bot.register_next_step_handler(m, do_broadcast)
    elif act == "add":
        m = bot.send_message(cid, "➕ شحن يدوي\nأرسل: `الآيدي المبلغ`\nمثال: `12345 10`")
        bot.register_next_step_handler(m, do_manual_add)
    elif act == "sub":
        m = bot.send_message(cid, "➖ خصم يدوي\nأرسل: `الآيدي المبلغ`\nمثال: `12345 5`")
        bot.register_next_step_handler(m, do_manual_sub)

def do_broadcast(message):
    if message.text == "إلغاء": return bot.reply_to(message, "تم الإلغاء")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT chat_id FROM users")
    users = cur.fetchall()
    conn.close()
    bot.reply_to(message, f"🚀 جاري الإرسال لـ {len(users)}...")
    for (uid,) in users:
        try:
            bot.copy_message(uid, message.chat.id, message.message_id)
            time.sleep(0.05)
        except: pass
    bot.reply_to(message, "✅ تمت الإذاعة.")

def do_manual_add(message):
    try:
        args = message.text.split()
        if len(args) < 2: raise ValueError
        u = int(args[0])
        a = float(args[1])
        update_balance(u, a)
        bot.reply_to(message, f"✅ تم شحن {a}$ للمستخدم {u} بنجاح.")
        try:
            bot.send_message(u, f"🎁 تم إضافة {a}$ لرصيدك من الإدارة.")
        except: pass
    except:
        bot.reply_to(message, "❌ خطأ في التنسيق. مثال: `12345 10`")

def do_manual_sub(message):
    try:
        args = message.text.split()
        if len(args) < 2: raise ValueError
        u = int(args[0])
        a = float(args[1])
        update_balance(u, -a)
        bot.reply_to(message, f"✅ تم خصم {a}$ من المستخدم {u} بنجاح.")
    except:
        bot.reply_to(message, "❌ خطأ في التنسيق. مثال: `12345 5`")

# ==================== 9. الشراء (نظام 5sim) ====================
COUNTRIES = {
    'canada': '🇨🇦 كندا (Koho)', 'egypt': '🇪🇬 مصر', 'saudiarabia': '🇸🇦 السعودية',
    'usa': '🇺🇸 أمريكا', 'russia': '🇷🇺 روسيا', 'brazil': '🇧🇷 البرازيل',
    'morocco': '🇲🇦 المغرب', 'algeria': '🇩🇿 الجزائر', 'iraq': '🇮🇶 العراق',
    'unitedkingdom': '🇬🇧 بريطانيا', 'germany': '🇩🇪 ألمانيا', 'france': '🇫🇷 فرنسا',
    'yemen': '🇾🇪 اليمن'
}
SERVICES = {
    'other': '🏦 Koho/Bank', 'whatsapp': '💚 WhatsApp', 'telegram': '💙 Telegram',
    'facebook': '💙 Facebook', 'instagram': '🩷 Instagram', 'tiktok': '🖤 TikTok',
    'google': '❤️ Gmail', 'twitter': '🖤 X (Twitter)'
}

@bot.callback_query_handler(func=lambda call: call.data == "buy")
def buy_menu(call):
    markup = types.InlineKeyboardMarkup(row_width=3)
    btns = [types.InlineKeyboardButton(n, callback_data=f"cnt:{k}") for k, n in COUNTRIES.items()]
    markup.add(*btns)
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu"))
    bot.edit_message_text("🌍 اختر الدولة:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("cnt:"))
def buy_srv(call):
    c = call.data.split(":")[1]
    user_selections[call.from_user.id] = c
    markup = types.InlineKeyboardMarkup(row_width=2)
    for k, n in SERVICES.items():
        markup.add(types.InlineKeyboardButton(n, callback_data=f"srv:{k}"))
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="buy"))
    bot.edit_message_text(f"👇 اختر الخدمة لـ {COUNTRIES[c]}:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("srv:"))
def do_buy(call):
    cid = call.message.chat.id
    srv = call.data.split(":")[1]
    cnt = user_selections.get(cid)
    
    # تحقق من الرصيد (تكلفة افتراضية)
    cost = 0.5
    user = get_user(cid)
    if not user or user[2] < cost: 
        return bot.answer_callback_query(call.id, "❌ رصيدك غير كافي!", show_alert=True)
    
    # هنا يتم وضع كود الشراء الفعلي من 5sim
    # حالياً سنقوم بخصم وهمي للتجربة
    update_balance(cid, -cost)
    bot.send_message(cid, f"✅ تم استلام طلبك!\nجاري جلب رقم {SERVICES[srv]} من دولة {COUNTRIES[cnt]}...\n(سيتم استكمال كود الـ API هنا)")

@bot.callback_query_handler(func=lambda call: call.data == "invite")
def invite_link(call):
    cid = call.message.chat.id
    link = f"https://t.me/{bot.get_me().username}?start={cid}"
    msg = f"🎁 شارك الرابط واربح!\nاحصل على {REFERRAL_REWARD}$ لكل صديق يسجل من خلالك:\n\n`{link}`"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu"))
    bot.edit_message_text(msg, cid, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

# ==================== 10. التشغيل النهائي ====================
if __name__ == "__main__":
    init_db()
    # تشغيل سيرفر Flask في خيط منفصل (عشان Render يفضل شغال)
    t = threading.Thread(target=run_web_server)
    t.start()
    
    print("🤖 Bot is Live and Running...")
    
    # حلقة التشغيل اللانهائية
    while True:
        try:
            bot.infinity_polling(skip_pending=True)
        except Exception as e:
            print(f"⚠️ Error: {e}")
            time.sleep(5)
