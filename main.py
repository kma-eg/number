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
from flask import Flask

# ==================== 1. إعدادات البوت والمفاتيح ====================
# تم دمج بياناتك كاملة هنا
BOT_TOKEN = "6058936352:AAFNKPjfj5A4qMYlyE-KPhBx_BUjSNlbYy0"
API_KEY = "eyJhbGciOiJSUzUxMiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE4MDAxMjk3MzIsImlhdCI6MTc2ODU5MzczMiwicmF5IjoiYjI1MDRmNzVlYzI2MTAzZmQ4MDVhNmZjNTU1OTNlMDgiLCJzdWIiOjM3NDE4NTl9.fChnApox83L626jS4ZajT1Sg0fEiYdqySUDJ9-AWEsNiHDJWv2hRaCk_MAtYJCa3nu1uo4HdTz-y4ug1EsAUbziQJncz5Q91Fh9ADt7LLgm8UyKzP4uFif5XY9rHpQ5zGiA8MN8HNIhtf-bHsJZxBNU0S8GT4VseKb1bbl3PEYB3H6IDSbH3csom0rWzYoySt9RPfOTuqJQlFk5T7TE_h4NjZhFvpt7_chzF2HQoLy0Js1esOyALhyX7D0xjCVet7df3CySYNn70sdJsPYRyEepetjsbq5lzHWg4zE4MOqB7_Q7iFPhQE_-t1v3J1yR1ARq9kMnzgH00I7cKcU0_Fg"
ADMIN_ID = 6318333901

# رابط قاعدة البيانات (Supabase Pooler - الآمن لـ Render)
SUPABASE_URL = "postgresql://postgres.rjialktdutmbuqhaznzu:5455%40Kma01020755609@aws-0-us-west-2.pooler.supabase.com:6543/postgres"

# إعدادات القنوات
SUB_CHANNEL_ID = -1003316907453       # قناة الاشتراك الإجباري
SUB_CHANNEL_LINK = "https://t.me/kma_c"

LOG_CHANNEL_ID = -1003709813767       # قناة التفعيلات (الإثباتات)
LOG_CHANNEL_LINK = "https://t.me/kms_ad"

# الثوابت المالية
REFERRAL_REWARD = 0.02  # مكافأة الدعوة (دولار)
USD_EGP_RATE = 50.0     # سعر الدولار مقابل الجنيه المصري

# ==================== 2. المحافظ ====================
WALLETS = {
    'vodafone': '01020755609',
    'vodafone2': '01005016893',
    'binance_id': '566079884',
    'bybit_id': '250000893',
    'usdt_address': 'TJuoPbUQepNx8SyUKNnxCU3ti4FeKZsZQx'
}

# ==================== 3. سيرفر Flask (لضمان بقاء Render شغال) ====================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is Running 24/7! 🚀"

def run_web_server():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

# ==================== 4. دوال قاعدة البيانات (Supabase) ====================
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
        print("✅ Database Connected Successfully")
    except Exception as e:
        print(f"❌ Database Connection Error: {e}")

def add_user(chat_id, username, referrer_id=None):
    conn = get_db_connection()
    cur = conn.cursor()
    status = "ERROR"
    try:
        cur.execute("SELECT chat_id FROM users WHERE chat_id = %s", (chat_id,))
        if cur.fetchone():
            status = "EXISTS"
        else:
            cur.execute("INSERT INTO users (chat_id, username, referrer_id) VALUES (%s, %s, %s)", (chat_id, username, referrer_id))
            conn.commit()
            status = "NEW"
    except Exception as e:
        print(f"Error adding user: {e}")
    finally:
        conn.close()
    return status

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

# ==================== 5. منطق البوت الأساسي ====================
bot = telebot.TeleBot(BOT_TOKEN)
user_captchas = {}
user_selections = {}

# توليد كابتشا معقدة (حروف وأرقام)
def gen_complex_captcha():
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(5))

@bot.message_handler(commands=['start'])
def start_msg(message):
    cid = message.chat.id
    username = message.from_user.username or "NoUsername"
    first_name = message.from_user.first_name or "Unknown"
    
    # معالجة نظام الإحالة
    args = message.text.split()
    referrer_id = 0
    if len(args) > 1 and args[1].isdigit():
        possible_ref = int(args[1])
        if possible_ref != cid:
            referrer_id = possible_ref

    # تسجيل المستخدم في القاعدة
    status = add_user(cid, username, referrer_id)
    
    # التعامل مع المستخدم الجديد
    if status == "NEW":
        # 1. توزيع المكافآت
        if referrer_id != 0:
            update_balance(referrer_id, REFERRAL_REWARD)
            update_balance(cid, REFERRAL_REWARD)
            try:
                bot.send_message(referrer_id, f"🎉 **تهانينا!**\nقام {first_name} بالدخول عبر رابطك.\n💰 تمت إضافة {REFERRAL_REWARD}$ إلى رصيدك.", parse_mode="Markdown")
            except: pass
            
        # 2. إرسال تقرير للأدمن (Log)
        inviter_txt = f"`{referrer_id}`" if referrer_id else "لا يوجد"
        log_msg = (f"👾 **عضو جديد انضم للبوت!**\n"
                   f"👤 الاسم: {first_name}\n"
                   f"🆔 الآيدي: `{cid}`\n"
                   f"🔗 المعرف: @{username}\n"
                   f"📥 الدعوة بواسطة: {inviter_txt}")
        bot.send_message(ADMIN_ID, log_msg, parse_mode="Markdown")

    elif status == "EXISTS":
        # لو المستخدم رجع بعد غياب أو حظر
        bot.send_message(ADMIN_ID, f"♻️ **مستخدم عاد للبوت:**\n👤 {first_name} (`{cid}`)", parse_mode="Markdown")

    # إرسال الكابتشا
    captcha_code = gen_complex_captcha()
    user_captchas[cid] = captcha_code
    bot.send_message(cid, f"🔒 **التحقق الأمني**\nمن فضلك أعد كتابة الكود التالي:\n\n`{captcha_code}`", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.chat.id in user_captchas)
def verify_captcha(message):
    cid = message.chat.id
    if message.text.strip() == user_captchas[cid]:
        del user_captchas[cid]
        check_sub_and_open_menu(cid)
    else:
        bot.send_message(cid, "❌ **كود خاطئ!** حاول مرة أخرى.")

def check_sub_and_open_menu(cid):
    try:
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

def main_menu(cid):
    user = get_user(cid)
    balance = user[2] if user else 0.0
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🛒 شراء أرقام", callback_data="buy"),
        types.InlineKeyboardButton("💰 شحن رصيد", callback_data="deposit_select_amount"),
        types.InlineKeyboardButton("👤 حسابي", callback_data="profile"),
        types.InlineKeyboardButton("🎁 دعوة أصدقاء", callback_data="invite"),
        types.InlineKeyboardButton("✅ قناة التفعيلات", url=LOG_CHANNEL_LINK)
    )
    if cid == ADMIN_ID:
        markup.add(types.InlineKeyboardButton("👮 لوحة الأدمن", callback_data="admin_panel"))
    
    bot.send_message(cid, f"👋 **أهلاً بك!**\n💰 رصيدك الحالي: `{balance:.2f}$`\nاختر من القائمة:", reply_markup=markup, parse_mode="Markdown")

# ==================== 6. نظام الشحن المتطور (EGP/USD) ====================
@bot.callback_query_handler(func=lambda call: call.data == "deposit_select_amount")
def deposit_amount_menu(call):
    markup = types.InlineKeyboardMarkup(row_width=2)
    # عرض المبالغ بالدولار والمقابل بالمصري
    amounts = [1, 3, 5, 10]
    for amt in amounts:
        egp_val = int(amt * USD_EGP_RATE)
        markup.add(types.InlineKeyboardButton(f"{amt}$  ({egp_val} EGP) 🇪🇬", callback_data=f"dep_amt:{amt}"))
    
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu"))
    bot.edit_message_text("💰 **شحن الرصيد**\nاختر الباقة المناسبة:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("dep_amt:"))
def deposit_method_menu(call):
    amount = call.data.split(":")[1]
    egp_val = int(float(amount) * USD_EGP_RATE)
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(f"Vodafone Cash ({egp_val} EGP) 🇪🇬", callback_data=f"pay_mtd:vodafone:{amount}"),
        types.InlineKeyboardButton("Binance Pay (USDT) 🟨", callback_data=f"pay_mtd:binance:{amount}"),
        types.InlineKeyboardButton("Bybit Pay (USDT) ⚫", callback_data=f"pay_mtd:bybit:{amount}"),
        types.InlineKeyboardButton("🔙 رجوع", callback_data="deposit_select_amount")
    )
    bot.edit_message_text(f"💳 المبلغ المختار: **{amount}$**\nاختر وسيلة الدفع:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_mtd:"))
def pay_info_msg(call):
    parts = call.data.split(":")
    method = parts[1]
    amount_usd = parts[2]
    amount_egp = int(float(amount_usd) * USD_EGP_RATE)
    
    msg = ""
    if method == 'vodafone':
        msg = (f"🇪🇬 **شحن فودافون كاش**\n\n"
               f"📱 رقم المحفظة: `{WALLETS['vodafone']}`\n"
               f"📞 رقم بديل: `{WALLETS['vodafone2']}`\n\n"
               f"💸 **المبلغ المطلوب:** `{amount_egp} جنيه`\n"
               f"⚠️ **تنبيه:** حول المبلغ كاملاً (بدون خصم رسوم التحويل).\n"
               f"📸 بعد التحويل، أرسل صورة الإيصال هنا.")
    elif method == 'binance':
        msg = (f"🟨 **شحن Binance Pay**\n\n"
               f"🆔 Pay ID: `{WALLETS['binance_id']}`\n"
               f"💰 **المبلغ:** `{amount_usd} USDT`\n\n"
               f"⚠️ استخدم Pay ID لتجنب الرسوم.\n"
               f"📸 أرسل صورة العملية هنا.")
    elif method == 'bybit':
        msg = (f"⚫ **شحن Bybit**\n\n"
               f"🆔 UID: `{WALLETS['bybit_id']}`\n"
               f"💰 **المبلغ:** `{amount_usd} USDT`\n\n"
               f"📸 أرسل صورة التحويل هنا.")

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="deposit_select_amount"))
    bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

# معالجة الإيصالات (للأدمن)
@bot.message_handler(content_types=['photo'])
def handle_receipt(message):
    cid = message.chat.id
    # توجيه الصورة للأدمن
    bot.forward_message(ADMIN_ID, cid, message.message_id)
    
    markup = types.InlineKeyboardMarkup(row_width=3)
    # أزرار القبول
    markup.add(
        types.InlineKeyboardButton("✅ 1$", callback_data=f"add:{cid}:1"),
        types.InlineKeyboardButton("✅ 3$", callback_data=f"add:{cid}:3"),
        types.InlineKeyboardButton("✅ 5$", callback_data=f"add:{cid}:5"),
        types.InlineKeyboardButton("✅ 10$", callback_data=f"add:{cid}:10")
    )
    # أزرار الرفض المسببة
    markup.add(
        types.InlineKeyboardButton("❌ رفض (مبلغ ناقص)", callback_data=f"rej:{cid}:less"),
        types.InlineKeyboardButton("❌ رفض (إيصال وهمي)", callback_data=f"rej:{cid}:fake"),
        types.InlineKeyboardButton("❌ رفض (تحت المراجعة)", callback_data=f"rej:{cid}:wait")
    )
    
    user = get_user(cid)
    cur_bal = user[2] if user else 0.0
    admin_msg = (f"📩 **إيصال جديد!**\n"
                 f"👤 الاسم: {message.from_user.first_name}\n"
                 f"🆔 الآيدي: `{cid}`\n"
                 f"💰 رصيده الحالي: `{cur_bal}$`")
    
    bot.send_message(ADMIN_ID, admin_msg, reply_markup=markup, parse_mode="Markdown")
    bot.reply_to(message, "✅ **تم استلام الإيصال!**\nجاري المراجعة، سيصلك إشعار قريباً.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("add:") or call.data.startswith("rej:"))
def admin_process_payment(call):
    if call.from_user.id != ADMIN_ID: return
    parts = call.data.split(":")
    action, uid = parts[0], parts[1]
    
    if action == "add":
        val = float(parts[2])
        update_balance(uid, val)
        bot.send_message(uid, f"🎉 **تم قبول الشحن!**\n💰 تمت إضافة {val}$ إلى رصيدك.\nاستمتع بخدماتنا! 🚀")
        bot.edit_message_text(f"✅ تم قبول وشحن {val}$ للمستخدم {uid}", call.message.chat.id, call.message.message_id)
    
    elif action == "rej":
        reason_code = parts[2]
        reason_txt = "بيانات غير صحيحة"
        if reason_code == "less": reason_txt = "المبلغ المحول أقل من المطلوب للباقة."
        elif reason_code == "fake": reason_txt = "الإيصال غير صحيح أو مستخدم سابقاً."
        elif reason_code == "wait": reason_txt = "الطلب قيد المراجعة اليدوية، يرجى الانتظار."
        
        bot.send_message(uid, f"❌ **تم رفض طلب الشحن**\n⚠️ السبب: {reason_txt}")
        bot.edit_message_text(f"❌ تم الرفض لـ {uid} (السبب: {reason_txt})", call.message.chat.id, call.message.message_id)

# ==================== 7. نظام الشراء و 5sim ====================
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
    
    cost = 0.5 # تكلفة افتراضية
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
    # محاولة لمدة 3 دقائق (36 * 5 ثواني)
    for _ in range(36):
        time.sleep(5)
        try:
            r = requests.get(f'https://5sim.net/v1/user/check/{oid}', headers=headers)
            data = r.json()
            if data['status'] == 'RECEIVED':
                code = data['sms'][0]['code']
                phone = data['phone']
                bot.send_message(cid, f"📬 **وصل الكود!**\nCode: `{code}`", parse_mode="Markdown")
                
                # إرسال إثبات لقناة التفعيلات
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

# ==================== 8. لوحة التحكم والإضافات ====================
@bot.callback_query_handler(func=lambda call: call.data == "admin_panel")
def admin_menu_func(call):
    if call.from_user.id != ADMIN_ID: return
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*), SUM(balance) FROM users")
    stats = cur.fetchone()
    conn.close()
    
    users_count = stats[0]
    total_balance = stats[1] if stats[1] else 0.0
    
    msg = (f"👮 **لوحة التحكم**\n"
           f"👥 الأعضاء: `{users_count}`\n"
           f"💰 إجمالي الأرصدة: `{total_balance:.2f}$`")
           
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📢 إذاعة للكل", callback_data="adm_broadcast"),
        types.InlineKeyboardButton("💰 شحن يدوي", callback_data="adm_add"),
        types.InlineKeyboardButton("🛑 خصم رصيد", callback_data="adm_sub"),
        types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")
    )
    bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

# وظائف الأدمن (إذاعة، شحن، خصم)@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_"))
def admin_actions(call):
    if call.from_user.id != ADMIN_ID: return
    action = call.data.split("_")[1]
    
    cid = call.message.chat.id
    if action == "broadcast":
        msg = bot.send_message(cid, "📢 **أرسل الرسالة التي تريد إذاعتها:**\n(يمكنك إرسال نص، صورة، أو توجيه رسالة)", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_broadcast)
    
    elif action == "add":
        msg = bot.send_message(cid, "💰 **شحن رصيد يدوي**\nأرسل: `الآيدي المبلغ`\nمثال: `123456789 5`", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_manual_add)
        
    elif action == "sub":
        msg = bot.send_message(cid, "🛑 **خصم رصيد يدوي**\nأرسل: `الآيدي المبلغ`\nمثال: `123456789 5`", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_manual_sub)

def process_broadcast(message):
    if message.text == "إلغاء": 
        bot.reply_to(message, "تم الإلغاء.")
        return

    # جلب جميع المستخدمين لإرسال الرسالة
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT chat_id FROM users")
    ids = cur.fetchall()
    conn.close()
    
    bot.reply_to(message, f"🚀 جاري الإرسال لـ {len(ids)} مستخدم...")
    
    count = 0
    for (uid,) in ids:
        try:
            bot.copy_message(uid, message.chat.id, message.message_id)
            count += 1
            time.sleep(0.05) # تأخير بسيط لتجنب الحظر من تيليجرام
        except Exception as e: 
            pass # تخطي المستخدمين اللي حاظرين البوت
    
    bot.reply_to(message, f"✅ تمت الإذاعة بنجاح لـ {count} مستخدم.")

def process_manual_add(message):
    try:
        args = message.text.split()
        uid = int(args[0])
        amount = float(args[1])
        update_balance(uid, amount)
        bot.reply_to(message, f"✅ تم شحن {amount}$ للمستخدم {uid} بنجاح.")
        try: 
            bot.send_message(uid, f"🎁 **إشعار إداري**\nتم إضافة {amount}$ إلى رصيدك بواسطة الإدارة.")
        except: pass
    except:
        bot.reply_to(message, "❌ تنسيق خاطئ! تأكد من كتابة الآيدي ثم مسافة ثم المبلغ.")

def process_manual_sub(message):
    try:
        args = message.text.split()
        uid = int(args[0])
        amount = float(args[1])
        # التأكد من أن الرصيد يكفي قبل الخصم (اختياري)
        update_balance(uid, -amount)
        bot.reply_to(message, f"✅ تم خصم {amount}$ من المستخدم {uid} بنجاح.")
    except:
        bot.reply_to(message, "❌ تنسيق خاطئ! تأكد من كتابة الآيدي ثم مسافة ثم المبلغ.")

# ==================== 9. التشغيل النهائي ====================
if __name__ == "__main__":
    # تشغيل سيرفر Flask في خيط منفصل (عشان Render يفضل شغال)
    t = threading.Thread(target=run_web_server)
    t.start()
    
    print("🤖 Bot is executing...")
    
    # حلقة التشغيل اللانهائية للبوت
    while True:
        try:
            bot.infinity_polling(skip_pending=True)
        except Exception as e:
            print(f"⚠️ Error detected: {e}")
            time.sleep(5)
