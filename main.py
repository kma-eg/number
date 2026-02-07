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
from datetime import datetime, timedelta
from flask import Flask

# ==================== 1. إعدادات البوت والمفاتيح ====================
BOT_TOKEN = "6058936352:AAFNKPjfj5A4qMYlyE-KPhBx_BUjSNlbYy0"
API_KEY = "eyJhbGciOiJSUzUxMiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE4MDAxMjk3MzIsImlhdCI6MTc2ODU5MzczMiwicmF5IjoiYjI1MDRmNzVlYzI2MTAzZmQ4MDVhNmZjNTU1OTNlMDgiLCJzdWIiOjM3NDE4NTl9.fChnApox83L626jS4ZajT1Sg0fEiYdqySUDJ9-AWEsNiHDJWv2hRaCk_MAtYJCa3nu1uo4HdTz-y4ug1EsAUbziQJncz5Q91Fh9ADt7LLgm8UyKzP4uFif5XY9rHpQ5zGiA8MN8HNIhtf-bHsJZxBNU0S8GT4VseKb1bbl3PEYB3H6IDSbH3csom0rWzYoySt9RPfOTuqJQlFk5T7TE_h4NjZhFvpt7_chzF2HQoLy0Js1esOyALhyX7D0xjCVet7df3CySYNn70sdJsPYRyEepetjsbq5lzHWg4zE4MOqB7_Q7iFPhQE_-t1v3J1yR1ARq9kMnzgH00I7cKcU0_Fg"
ADMIN_ID = 6318333901

# رابط قاعدة البيانات
SUPABASE_URL = "postgresql://postgres.rjialktdutmbuqhaznzu:5455%40Kma01020755609@aws-0-us-west-2.pooler.supabase.com:6543/postgres"

# القنوات
SUB_CHANNEL_ID = -1003316907453
SUB_CHANNEL_LINK = "https://t.me/kma_c"
LOG_CHANNEL_ID = -1003709813767
LOG_CHANNEL_LINK = "https://t.me/kms_ad"

# الماليات
REFERRAL_REWARD = 0.02
USD_EGP_RATE = 50.0

WALLETS = {
    'vodafone': '01020755609',
    'vodafone2': '01005016893',
    'binance_id': '566079884',
    'bybit_id': '250000893',
    'usdt_address': 'TJuoPbUQepNx8SyUKNnxCU3ti4FeKZsZQx'
}

# متغيرات الذاكرة (RAM) للحماية والجلسات
user_spam = {}        # {chat_id: [time1, time2, ...]}
user_sessions = {}    # {chat_id: last_captcha_time}
user_captchas = {}    # {chat_id: captcha_code}
user_selections = {}  # {chat_id: selection_data}

# ==================== 2. سيرفر Flask ====================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is Running 24/7! 🚀"

def run_web_server():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

# ==================== 3. قاعدة البيانات ====================
def get_db_connection():
    return psycopg2.connect(SUPABASE_URL)

def init_db():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # إنشاء الجدول إذا لم يكن موجوداً
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                chat_id BIGINT PRIMARY KEY,
                username TEXT,
                balance FLOAT DEFAULT 0,
                referrer_id BIGINT,
                joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        # محاولة إضافة عمود last_seen لو مش موجود (للمستخدمين القدامى)
        try:
            cur.execute("ALTER TABLE users ADD COLUMN last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP;")
            conn.commit()
        except:
            conn.rollback()
        
        conn.close()
        print("✅ Database Connected")
    except Exception as e:
        print(f"❌ DB Error: {e}")

def add_user(chat_id, username, referrer_id=None):
    conn = get_db_connection()
    cur = conn.cursor()
    status = "ERROR"
    try:
        cur.execute("SELECT chat_id, last_seen FROM users WHERE chat_id = %s", (chat_id,))
        res = cur.fetchone()
        
        if res:
            status = "EXISTS"
            # تحديث وقت آخر ظهور
            cur.execute("UPDATE users SET last_seen = NOW() WHERE chat_id = %s", (chat_id,))
            conn.commit()
            return status, res[1] # Return last_seen
        else:
            cur.execute("INSERT INTO users (chat_id, username, referrer_id, last_seen) VALUES (%s, %s, %s, NOW())", (chat_id, username, referrer_id))
            conn.commit()
            status = "NEW"
            return status, None
    except Exception as e:
        print(f"Error adding user: {e}")
        return "ERROR", None
    finally:
        conn.close()

def get_user(chat_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE chat_id = %s", (chat_id,))
    res = cur.fetchone()
    conn.close()
    return res

def get_referrals_count(chat_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users WHERE referrer_id = %s", (chat_id,))
    res = cur.fetchone()
    conn.close()
    return res[0] if res else 0

def get_total_users():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    res = cur.fetchone()
    conn.close()
    return res[0] if res else 0

def update_balance(chat_id, amount):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET balance = balance + %s WHERE chat_id = %s", (amount, chat_id))
    conn.commit()
    conn.close()

# ==================== 4. منطق البوت والحماية ====================
bot = telebot.TeleBot(BOT_TOKEN)

def gen_complex_captcha():
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(5))

# نظام الحماية من السبام (Spam Protection)
def check_spam(chat_id):
    now = time.time()
    if chat_id not in user_spam:
        user_spam[chat_id] = []
    
    # حذف الطوابع الزمنية القديمة (أكثر من دقيقة)
    user_spam[chat_id] = [t for t in user_spam[chat_id] if now - t < 60]
    
    # إضافة الوقت الحالي
    user_spam[chat_id].append(now)
    
    # لو ضغط أكثر من 8 مرات في الدقيقة
    if len(user_spam[chat_id]) > 8:
        return True
    return False

@bot.message_handler(commands=['start'])
def start_msg(message):
    cid = message.chat.id
    
    # 1. فحص السبام
    if check_spam(cid):
        bot.send_message(cid, "⛔ **تم إيقافك مؤقتاً!**\nأنت تضغط بسرعة كبيرة، يرجى الانتظار لمدة دقيقة.")
        return

    username = message.from_user.username or "NoUsername"
    first_name = message.from_user.first_name or "Unknown"
    
    # 2. معالجة الإحالة والتسجيل
    args = message.text.split()
    referrer_id = 0
    if len(args) > 1 and args[1].isdigit():
        possible_ref = int(args[1])
        if possible_ref != cid:
            referrer_id = possible_ref

    status, last_seen_db = add_user(cid, username, referrer_id)
    total_users = get_total_users()

    # 3. إشعارات الأدمن (Logs)
    if status == "NEW":
        # توزيع المكافآت
        if referrer_id != 0:
            update_balance(referrer_id, REFERRAL_REWARD)
            update_balance(cid, REFERRAL_REWARD)
            try:
                bot.send_message(referrer_id, f"🎉 **تهانينا!**\nقام {first_name} بالدخول عبر رابطك.\n💰 رصيد مضاف: {REFERRAL_REWARD}$")
            except: pass
            
        # إشعار العضو الجديد المنظم
        inviter_txt = f"`{referrer_id}`" if referrer_id else "لا يوجد"
        log_msg = (f"👾 **تم دخول شخص جديد إلى البوت الخاص بك**\n"
                   f"------------------------\n"
                   f"• معلومات العضو الجديد .\n\n"
                   f"• الاسم : {first_name}\n"
                   f"• معرف : @{username}\n"
                   f"• الايدي : `{cid}`\n"
                   f"------------------------\n"
                   f"• عدد الأعضاء الكلي : {total_users}")
        bot.send_message(ADMIN_ID, log_msg, parse_mode="Markdown")

    elif status == "EXISTS":
        # إشعار العودة (فقط لو غايب أكثر من أسبوعين)
        if last_seen_db:
            # last_seen_db is a datetime object from psycopg2
            now_dt = datetime.now()
            # تأكد من التنسيق (أحياناً يأتي string حسب الـ driver)
            if isinstance(last_seen_db, str):
                last_seen_db = datetime.strptime(last_seen_db, '%Y-%m-%d %H:%M:%S.%f')
                
            delta = now_dt - last_seen_db
            if delta.days > 14:
                log_msg = (f"📶 **قام مستخدم جديد بإعادة استخدام البوت**\n"
                           f"الخاص بك مرة أخرى.\n\n"
                           f"👤 **معلومات العضو:**\n"
                           f"• الاسم: {first_name}\n"
                           f"• اسم المستخدم: @{username}\n"
                           f"• الآيدي: `{cid}`\n\n"
                           f"📊 إجمالي المستخدمين: {total_users}")
                bot.send_message(ADMIN_ID, log_msg, parse_mode="Markdown")

    # 4. نظام الكابتشا (مرة كل ساعة)
    last_cap = user_sessions.get(cid, 0)
    if time.time() - last_cap > 3600: # 3600 ثانية = ساعة
        captcha_code = gen_complex_captcha()
        user_captchas[cid] = captcha_code
        bot.send_message(cid, f"🔒 **التحقق الأمني**\nمن فضلك أعد كتابة الكود التالي:\n\n`{captcha_code}`", parse_mode="Markdown")
    else:
        # لو عدى الكابتشا من قريب، ادخله القائمة علطول
        check_sub_and_open_menu(cid)

@bot.message_handler(func=lambda m: m.chat.id in user_captchas)
def verify_captcha(message):
    cid = message.chat.id
    if message.text.strip() == user_captchas[cid]:
        del user_captchas[cid]
        user_sessions[cid] = time.time() # تسجيل وقت النجاح
        check_sub_and_open_menu(cid)
    else:
        bot.send_message(cid, "❌ **كود خاطئ!** حاول مرة أخرى.")

def check_sub_and_open_menu(cid):
    try:
        # تأكد إن البوت أدمن في القناة عشان يقدر يفحص
        stat = bot.get_chat_member(SUB_CHANNEL_ID, cid).status
        if stat not in ['member', 'administrator', 'creator']:
            raise Exception("Not Subscribed")
        main_menu(cid)
    except:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 اشترك في القناة", url=SUB_CHANNEL_LINK))
        markup.add(types.InlineKeyboardButton("🔄 تحقق من الاشتراك", callback_data="check_sub"))
        bot.send_message(cid, "⚠️ **عذراً، يجب الاشتراك في القناة أولاً لاستخدام البوت.**", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_sub_callback(call):
    check_sub_and_open_menu(call.message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def main_menu_callback(call):
    main_menu(call.message.chat.id, message_id=call.message.message_id)

def main_menu(cid, message_id=None):
    user = get_user(cid)
    balance = user[2] if user else 0.0
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🛒 شراء أرقام", callback_data="buy"),
        types.InlineKeyboardButton("💰 شحن رصيد", callback_data="dep_region_select"),
        types.InlineKeyboardButton("👤 حسابي", callback_data="profile"),
        types.InlineKeyboardButton("🎁 دعوة أصدقاء", callback_data="invite"),
        types.InlineKeyboardButton("✅ قناة التفعيلات", url=LOG_CHANNEL_LINK)
    )
    if cid == ADMIN_ID:
        markup.add(types.InlineKeyboardButton("👮 لوحة الأدمن", callback_data="admin_panel"))
    
    text = f"👋 **أهلاً بك!**\n💰 رصيدك الحالي: `{balance:.2f}$`\nاختر من القائمة:"
    if message_id:
        bot.edit_message_text(text, cid, message_id, reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(cid, text, reply_markup=markup, parse_mode="Markdown")

# ==================== 5. حسابي (Profile) ====================
@bot.callback_query_handler(func=lambda call: call.data == "profile")
def profile_func(call):
    cid = call.message.chat.id
    user = get_user(cid)
    if not user: return
    
    username = user[1]
    balance = user[2]
    joined = user[4]
    invites = get_referrals_count(cid)
    
    msg = (f"👤 **ملف المستخدم**\n\n"
           f"🆔 الآيدي: `{cid}`\n"
           f"📛 المعرف: @{username}\n"
           f"💰 الرصيد: `{balance:.2f}$`\n"
           f"👥 عدد الدعوات: `{invites}`\n"
           f"📅 تاريخ الانضمام: `{joined}`")
           
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu"))
    bot.edit_message_text(msg, cid, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

# ==================== 6. نظام الشحن الجديد (المنفصل) ====================
@bot.callback_query_handler(func=lambda call: call.data == "dep_region_select")
def select_deposit_region(call):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🇪🇬 أنا داخل مصر (Vodafone Cash)", callback_data="dep_reg:eg"),
        types.InlineKeyboardButton("🌍 أنا خارج مصر (Crypto/Global)", callback_data="dep_reg:global"),
        types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")
    )
    bot.edit_message_text("🌍 **من فضلك حدد مكانك:**\nعشان نقدر نطلعلك طرق الدفع المناسبة.", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("dep_reg:"))
def deposit_amount_menu(call):
    region = call.data.split(":")[1]
    markup = types.InlineKeyboardMarkup(row_width=2)
    amounts = [1, 3, 5, 10]
    
    if region == "eg":
        # داخل مصر - فودافون كاش
        for amt in amounts:
            egp_val = int(amt * USD_EGP_RATE)
            markup.add(types.InlineKeyboardButton(f"{amt}$ = {egp_val} EGP 🇪🇬", callback_data=f"pay:vf:{amt}"))
    else:
        # خارج مصر - كريبتو
        for amt in amounts:
            markup.add(types.InlineKeyboardButton(f"{amt}$ (USDT)", callback_data=f"pay:crypto:{amt}"))
            
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="dep_region_select"))
    
    reg_txt = "🇪🇬 (داخل مصر)" if region == "eg" else "🌍 (خارج مصر)"
    bot.edit_message_text(f"💰 **شحن الرصيد {reg_txt}**\nاختر الباقة المناسبة:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("pay:"))
def pay_details(call):
    # Data format: pay:vf:5 or pay:crypto:5
    parts = call.data.split(":")
    method_type = parts[1]
    amount_usd = parts[2]
    amount_egp = int(float(amount_usd) * USD_EGP_RATE)
    
    msg = ""
    warning_text = ("\n⚠️ **هام جداً:**\n"
                    "يجب تحويل المبلغ **بالضبط** كما هو موضح.\n"
                    "• إذا حولت مبلغاً **أقل**، لن يتم احتسابه.\n"
                    "• إذا حولت مبلغاً **أكثر**، لن يتم رد الباقي.\n"
                    "• في حالة التحويل الخاطئ، قد تفقد أموالك.")

    if method_type == 'vf':
        msg = (f"🇪🇬 **شحن فودافون كاش**\n\n"
               f"📱 رقم المحفظة: `{WALLETS['vodafone']}`\n"
               f"💸 **المبلغ المطلوب:** `{amount_egp} جنيه`\n"
               f"💵 (يعادل {amount_usd}$)\n"
               f"{warning_text}\n\n"
               f"📸 بعد التحويل، أرسل صورة الإيصال هنا.")
    
    elif method_type == 'crypto':
        msg = (f"💎 **شحن عملات رقمية (USDT)**\n\n"
               f"🔸 **Binance Pay ID:** `{WALLETS['binance_id']}`\n"
               f"🔹 **Bybit UID:** `{WALLETS['bybit_id']}`\n"
               f"🕸 **TRC20 Address:** `{WALLETS['usdt_address']}`\n\n"
               f"💰 **المبلغ المطلوب:** `{amount_usd} USDT`\n"
               f"{warning_text}\n\n"
               f"📸 أرسل صورة العملية هنا.")

    markup = types.InlineKeyboardMarkup()
    # زر رجوع حسب النوع
    back_data = "dep_reg:eg" if method_type == 'vf' else "dep_reg:global"
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data=back_data))
    
    bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

# ==================== 7. معالجة الإيصالات ====================
@bot.message_handler(content_types=['photo'])
def handle_receipt(message):
    cid = message.chat.id
    bot.forward_message(ADMIN_ID, cid, message.message_id)
    
    markup = types.InlineKeyboardMarkup(row_width=4)
    markup.add(
        types.InlineKeyboardButton("✅ 1$", callback_data=f"adm_cfm:{cid}:1"),
        types.InlineKeyboardButton("✅ 3$", callback_data=f"adm_cfm:{cid}:3"),
        types.InlineKeyboardButton("✅ 5$", callback_data=f"adm_cfm:{cid}:5"),
        types.InlineKeyboardButton("✅ 10$", callback_data=f"adm_cfm:{cid}:10")
    )
    markup.add(
        types.InlineKeyboardButton("❌ رفض (مبلغ ناقص)", callback_data=f"adm_rej:{cid}:less"),
        types.InlineKeyboardButton("❌ رفض (وهمي)", callback_data=f"adm_rej:{cid}:fake")
    )
    
    user = get_user(cid)
    cur_bal = user[2] if user else 0.0
    bot.send_message(ADMIN_ID, f"📩 **إيصال من:** {message.from_user.first_name} (`{cid}`)\nرصيده الحالي: {cur_bal}$", reply_markup=markup, parse_mode="Markdown")
    bot.reply_to(message, "✅ **تم الاستلام!**\nجاري المراجعة من قبل الإدارة.")

# ==================== 8. لوحة الأدمن (المصلحة) ====================
@bot.callback_query_handler(func=lambda call: call.data == "admin_panel")
def admin_dashboard(call):
    if call.from_user.id != ADMIN_ID: return
    
    users = get_total_users()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SUM(balance) FROM users") # Bug fix logic
    # الصحيح:
    cur.execute("SELECT SUM(balance) FROM users")
    res = cur.fetchone()
    total_money = res[0] if res[0] else 0.0
    conn.close()
    
    msg = (f"👮 **لوحة التحكم**\n"
           f"👥 الأعضاء: `{users}`\n"
           f"💰 أموال العملاء: `{total_money:.2f}$`")
           
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📢 إذاعة للكل", callback_data="adm_broadcast_start"),
        types.InlineKeyboardButton("➕ شحن يدوي", callback_data="adm_manual_add_start"),
        types.InlineKeyboardButton("➖ خصم رصيد", callback_data="adm_manual_sub_start"),
        types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")
    )
    bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

# معالجات أزرار الأدمن
@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_"))
def admin_action_handler(call):
    if call.from_user.id != ADMIN_ID: return
    action = call.data
    cid = call.message.chat.id

    # 1. قبول الإيصال
    if action.startswith("adm_cfm:"):
        parts = action.split(":")
        uid, amount = int(parts[1]), float(parts[2])
        update_balance(uid, amount)
        bot.send_message(uid, f"✅ **تم شحن رصيدك بنجاح!**\n💰 المبلغ المضاف: {amount}$")
        bot.edit_message_text(f"✅ تم الشحن لـ {uid} بمبلغ {amount}$", cid, call.message.message_id)

    # 2. رفض الإيصال
    elif action.startswith("adm_rej:"):
        parts = action.split(":")
        uid, reason = int(parts[1]), parts[2]
        reason_msg = "المبلغ المحول غير مطابق" if reason == "less" else "البيانات غير صحيحة"
        bot.send_message(uid, f"❌ **تم رفض طلب الشحن**\nالسبب: {reason_msg}")
        bot.edit_message_text(f"❌ تم الرفض لـ {uid}", cid, call.message.message_id)

    # 3. بدء الإذاعة
    elif action == "adm_broadcast_start":
        msg = bot.send_message(cid, "📢 **أرسل الرسالة للإذاعة الآن:**\n(أرسل 'إلغاء' للتراجع)")
        bot.register_next_step_handler(msg, process_broadcast)

    # 4. بدء الشحن اليدوي
    elif action == "adm_manual_add_start":
        msg = bot.send_message(cid, "💰 **شحن يدوي**\nأرسل: `الآيدي المبلغ`\nمثال: `123456789 5`")
        bot.register_next_step_handler(msg, process_manual_add)

    # 5. بدء الخصم اليدوي
    elif action == "adm_manual_sub_start":
        msg = bot.send_message(cid, "🛑 **خصم يدوي**\nأرسل: `الآيدي المبلغ`\nمثال: `123456789 5`")
        bot.register_next_step_handler(msg, process_manual_sub)

def process_broadcast(message):
    if message.text == "إلغاء": return bot.reply_to(message, "تم الإلغاء")
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT chat_id FROM users")
    users = cur.fetchall()
    conn.close()
    
    bot.reply_to(message, f"🚀 جاري الإرسال لـ {len(users)}...")
    count = 0
    for (uid,) in users:
        try:
            bot.copy_message(uid, message.chat.id, message.message_id)
            count += 1
            time.sleep(0.04) 
        except: pass
    bot.reply_to(message, f"✅ تمت الإذاعة لـ {count} مستخدم.")

def process_manual_add(message):
    try:
        data = message.text.split()
        uid, amt = int(data[0]), float(data[1])
        update_balance(uid, amt)
        bot.reply_to(message, f"✅ تم شحن {amt}$ للمستخدم {uid}")
        bot.send_message(uid, f"🎁 **مكافأة إدارية!**\nتم إضافة {amt}$ لرصيدك.")
    except: bot.reply_to(message, "❌ خطأ في التنسيق")

def process_manual_sub(message):
    try:
        data = message.text.split()
        uid, amt = int(data[0]), float(data[1])
        update_balance(uid, -amt)
        bot.reply_to(message, f"✅ تم خصم {amt}$ من {uid}")
    except: bot.reply_to(message, "❌ خطأ في التنسيق")

# ==================== 9. الشراء من 5sim (نفس الكود القديم) ====================
COUNTRIES = {
    'canada': '🇨🇦 كندا (Koho)', 'egypt': '🇪🇬 مصر', 'saudiarabia': '🇸🇦 السعودية',
    'usa': '🇺🇸 أمريكا', 'russia': '🇷🇺 روسيا', 'brazil': '🇧🇷 البرازيل',
    'morocco': '🇲🇦 المغرب', 'algeria': '🇩🇿 الجزائر', 'iraq': '🇮🇶 العراق',
    'unitedkingdom': '🇬🇧 بريطانيا', 'germany': '🇩🇪 ألمانيا', 'france': '🇫🇷 فرنسا',
    'yemen': '🇾🇪 اليمن'
}
SERVICES = {
    'other': '🏦 Koho / Bank', 'whatsapp': '💚 WhatsApp', 'telegram': '💙 Telegram',
    'facebook': '💙 Facebook', 'instagram': '🩷 Instagram', 'tiktok': '🖤 TikTok',
    'google': '❤️ Gmail', 'twitter': '🖤 X (Twitter)', 'snapchat': '💛 Snapchat'
}

def get_live_stock(country):
    try:
        headers = {'Accept': 'application/json'}
        r = requests.get(f'https://5sim.net/v1/guest/products/{country}/any', headers=headers, timeout=5)
        return r.json() if r.status_code == 200 else {}
    except: return {}

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
    bot.edit_message_text("🔄 جاري الاتصال بالسيرفر...", call.message.chat.id, call.message.message_id)
    
    stock = get_live_stock(country)
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    
    for k, n in SERVICES.items():
        qty = stock.get(k, {}).get('Qty', 0)
        btn_txt = f"{n} [{qty}]" if qty > 0 else f"🚫 {n} (0)"
        cb = f"srv:{k}" if qty > 0 else "none"
        buttons.append(types.InlineKeyboardButton(btn_txt, callback_data=cb))
        
    markup.add(*buttons)
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="buy"))
    bot.edit_message_text(f"🌍 {COUNTRIES.get(country)}\n👇 الخدمات المتاحة:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("srv:"))
def execute_buy(call):
    cid = call.message.chat.id
    service = call.data.split(":")[1]
    country = user_selections.get(cid)
    
    if not country: return bot.answer_callback_query(call.id, "خطأ، حاول مجدداً")
    
    cost = 0.5 
    user_bal = get_user(cid)[2]
    
    if user_bal < cost:
        return bot.answer_callback_query(call.id, "❌ رصيدك غير كافي", show_alert=True)
        
    update_balance(cid, -cost)
    bot.send_message(cid, "🔄 جاري حجز الرقم... يرجى الانتظار")
    
    try:
        headers = {'Authorization': 'Bearer ' + API_KEY, 'Accept': 'application/json'}
        r = requests.get(f'https://5sim.net/v1/user/buy/activation/{country}/any/{service}', headers=headers)
        
        if r.status_code == 200:
            data = r.json()
            if 'phone' in data:
                phone = data['phone']
                oid = data['id']
                bot.send_message(cid, f"✅ **تم شراء الرقم بنجاح!**\n📱 الرقم: `{phone}`\n⏳ الخدمة: {SERVICES.get(service)}\n\n⚠️ **جاري انتظار الكود...**", parse_mode="Markdown")
                threading.Thread(target=check_sms, args=(cid, oid, headers, country, service)).start()
            else:
                update_balance(cid, cost)
                bot.send_message(cid, "⚠️ لا توجد أرقام متاحة الآن، تم استرداد الرصيد.")
        else:
            update_balance(cid, cost)
            bot.send_message(cid, f"❌ خطأ من المزود: {r.text}")
    except Exception as e:
        update_balance(cid, cost)
        bot.send_message(cid, f"خطأ تقني: {e}")

def check_sms(cid, oid, headers, country, service):
    for _ in range(36):
        time.sleep(5)
        try:
            r = requests.get(f'https://5sim.net/v1/user/check/{oid}', headers=headers)
            data = r.json()
            if data['status'] == 'RECEIVED':
                code = data['sms'][0]['code']
                phone = data['phone']
                bot.send_message(cid, f"📬 **وصل الكود!**\nCode: `{code}`", parse_mode="Markdown")
                
                try:
                    masked = phone[:-4] + "****"
                    log_msg = (f"✅ **تفعيل جديد!** 🚀\n"
                               f"🌍 الدولة: {COUNTRIES.get(country)}\n"
                               f"📱 الخدمة: {SERVICES.get(service)}\n"
                               f"📞 الرقم: `{masked}`")
                    markup = types.InlineKeyboardMarkup()
                    bot_url = f"https://t.me/{bot.get_me().username}"
                    markup.add(types.InlineKeyboardButton("🤖 احصل على رقمك الآن", url=bot_url))
                    bot.send_message(LOG_CHANNEL_ID, log_msg, parse_mode="Markdown", reply_markup=markup)
                except: pass
                return
            elif data['status'] in ['CANCELED', 'TIMEOUT']:
                bot.send_message(cid, "❌ تم إلغاء الرقم أو انتهاء الوقت.")
                return
        except: pass
    bot.send_message(cid, "⏰ انتهى الوقت ولم يصل الكود.")

@bot.callback_query_handler(func=lambda call: call.data == "invite")
def invite_link(call):
    cid = call.message.chat.id
    bot_name = bot.get_me().username
    link = f"https://t.me/{bot_name}?start={cid}"
    msg = f"🎁 **اربح رصيد مجاني!**\n\nشارك الرابط التالي مع أصدقائك واحصل على {REFERRAL_REWARD}$ لكل شخص ينضم:\n\n`{link}`"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu"))
    bot.edit_message_text(msg, cid, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

if __name__ == "__main__":
    init_db()
    t = threading.Thread(target=run_web_server)
    t.start()
    print("🤖 Bot is Live with Security Update...")
    while True:
        try:
            bot.infinity_polling(skip_pending=True)
        except Exception as e:
            time.sleep(5)
