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
BOT_TOKEN = "6058936352:AAFNKPjfj5A4qMYlyE-KPhBx_BUjSNlbYy0"
ADMIN_ID = 6318333901

# رابط قاعدة البيانات
SUPABASE_URL = "postgresql://postgres.rjialktdutmbuqhaznzu:5455%40Kma01020755609@aws-0-us-west-2.pooler.supabase.com:6543/postgres"

# إعدادات القنوات
SUB_CHANNEL_ID = -1003316907453       # قناة الاشتراك الإجباري
SUB_CHANNEL_LINK = "https://t.me/kma_c"

LOG_CHANNEL_ID = -1003709813767       # قناة التفعيلات (الإثباتات)
LOG_CHANNEL_LINK = "https://t.me/kms_ad"

# الثوابت المالية
REFERRAL_REWARD = 0.02  # مكافأة الدعوة (دولار)
USD_EGP_RATE = 50.0     # سعر الدولار 
GMAIL_PRICE = 1.0       # سعر الجيميل الدائم (تعدله براحتك)

# ==================== 2. المحافظ ====================
WALLETS = {
    'vodafone': '01020755609',
    'vodafone2': '01005016893',
    'binance_id': '566079884',
    'bybit_id': '250000893'
}

# ==================== 3. سيرفر Flask (لـ Render) ====================
app = Flask(__name__)
@app.route('/')
def home(): return "Temp Mail Bot is Running! 🚀"
def run_web_server():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

# ==================== 4. قاعدة البيانات ====================
def get_db_connection(): return psycopg2.connect(SUPABASE_URL)

def init_db():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # جدول المستخدمين
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                chat_id BIGINT PRIMARY KEY, username TEXT,
                balance FLOAT DEFAULT 0, referrer_id BIGINT,
                joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # جدول سجل الإيميلات المؤقتة
        cur.execute("""
            CREATE TABLE IF NOT EXISTS email_history (
                id SERIAL PRIMARY KEY, chat_id BIGINT,
                email TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # جدول مخزن الإيميلات المدفوعة (التي يضيفها الأدمن)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS paid_accounts (
                id SERIAL PRIMARY KEY, account_type TEXT,
                email_pass TEXT, is_sold BOOLEAN DEFAULT FALSE,
                buyer_id BIGINT
            );
        """)
        conn.commit()
        conn.close()
        print("✅ Database Connected")
    except Exception as e: print(f"❌ DB Error: {e}")

def add_user(chat_id, username, referrer_id=None):
    conn = get_db_connection()
    cur = conn.cursor()
    status = "ERROR"
    try:
        cur.execute("SELECT chat_id FROM users WHERE chat_id = %s", (chat_id,))
        if cur.fetchone(): status = "EXISTS"
        else:
            cur.execute("INSERT INTO users (chat_id, username, referrer_id) VALUES (%s, %s, %s)", (chat_id, username, referrer_id))
            conn.commit()
            status = "NEW"
    except: pass
    finally: conn.close()
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

# ==================== 5. الكابتشا المعقدة ومنطق البداية ====================
bot = telebot.TeleBot(BOT_TOKEN)
user_captchas = {}
active_temp_mails = {} # لتخزين الإيميل المؤقت النشط لكل مستخدم

def gen_complex_captcha():
    chars = string.ascii_letters + string.digits + "@#$&*?!"
    return ''.join(random.choice(chars) for _ in range(6))

@bot.message_handler(commands=['start'])
def start_msg(message):
    cid = message.chat.id
    username = message.from_user.username or "NoUser"
    first_name = message.from_user.first_name
    
    args = message.text.split()
    referrer_id = 0
    if len(args) > 1 and args[1].isdigit():
        ref = int(args[1])
        if ref != cid: referrer_id = ref

    status = add_user(cid, username, referrer_id)
    if status == "NEW":
        if referrer_id != 0:
            update_balance(referrer_id, REFERRAL_REWARD)
            update_balance(cid, REFERRAL_REWARD)
            try: bot.send_message(referrer_id, f"🎉 **دعوة ناجحة!**\nسجل {first_name} وحصلت على {REFERRAL_REWARD}$")
            except: pass
        bot.send_message(ADMIN_ID, f"👾 **عضو جديد:** {first_name} (`{cid}`)")
    
    captcha_code = gen_complex_captcha()
    user_captchas[cid] = captcha_code
    bot.send_message(cid, f"🔒 **التحقق البشري**\nاكتب الرموز التالية بدقة (الحروف الكبيرة والصغيرة والرموز):\n\n`{captcha_code}`", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.chat.id in user_captchas)
def verify_captcha(message):
    cid = message.chat.id
    if message.text.strip() == user_captchas[cid]:
        del user_captchas[cid]
        check_sub_and_open_menu(cid)
    else:
        bot.send_message(cid, "❌ **كود خاطئ!** تأكد من الحروف الكبيرة والصغيرة.")

def check_sub_and_open_menu(cid):
    try:
        stat = bot.get_chat_member(SUB_CHANNEL_ID, cid).status
        if stat not in ['member', 'administrator', 'creator']: raise Exception
        main_menu(cid)
    except:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 اشترك في القناة", url=SUB_CHANNEL_LINK))
        markup.add(types.InlineKeyboardButton("🔄 تحقق", callback_data="check_sub"))
        bot.send_message(cid, "⚠️ **اشترك في القناة أولاً لتفعيل البوت.**", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_sub_callback(call): check_sub_and_open_menu(call.message.chat.id)

def main_menu(cid):
    user = get_user(cid)
    balance = user[2] if user else 0.0
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🆓 توليد إيميل مؤقت", callback_data="gen_temp"),
        types.InlineKeyboardButton("📥 صندوق الوارد", callback_data="check_inbox"),
        types.InlineKeyboardButton("💎 شراء Gmail (دائم)", callback_data="buy_gmail"),
        types.InlineKeyboardButton("💰 شحن رصيد", callback_data="deposit_select_amount"),
        types.InlineKeyboardButton("👤 حسابي", callback_data="profile"),
        types.InlineKeyboardButton("🎁 دعوة أصدقاء", callback_data="invite"),
        types.InlineKeyboardButton("✅ قناة التفعيلات", url=LOG_CHANNEL_LINK)
    )
    if cid == ADMIN_ID: markup.add(types.InlineKeyboardButton("👮 لوحة الأدمن", callback_data="admin_panel"))
    bot.send_message(cid, f"👋 **أهلاً بك في بوت الخدمات الذكية!**\n💰 رصيدك: `{balance:.2f}$`\nاختر من القائمة:", reply_markup=markup, parse_mode="Markdown")

# ==================== 6. الإيميلات المؤقتة (مجاني) ====================
@bot.callback_query_handler(func=lambda call: call.data == "gen_temp")
def generate_temp_email(call):
    cid = call.message.chat.id
    bot.edit_message_text("🔄 جاري إنشاء إيميل مؤقت...", cid, call.message.message_id)
    try:
        r = requests.get("https://www.1secmail.com/api/v1/?action=genRandomMailbox&count=1")
        email = r.json()[0]
        active_temp_mails[cid] = email
        
        # حفظ في قاعدة البيانات (السجل)
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO email_history (chat_id, email) VALUES (%s, %s)", (cid, email))
        conn.commit()
        conn.close()

        # إرسال إشعار للقناة
        masked = email[:3] + "****" + email[email.find("@"):]
        markup_ch = types.InlineKeyboardMarkup()
        markup_ch.add(types.InlineKeyboardButton("🤖 احصل على إيميلك الآن", url=f"https://t.me/{bot.get_me().username}"))
        bot.send_message(LOG_CHANNEL_ID, f"✅ **توليد إيميل جديد!** 🚀\n✉️ `{masked}`\n✨ مجاناً عبر بوتنا!", reply_markup=markup_ch, parse_mode="Markdown")

        # رسالة للمستخدم
        msg = f"✅ **تم إنشاء الإيميل المؤقت بنجاح!**\n\n✉️ الإيميل:\n`{email}`\n\n⚠️ استخدمه للتسجيل في المواقع، ثم اضغط على (صندوق الوارد) لرؤية رمز التحقق."
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📥 فحص صندوق الوارد", callback_data="check_inbox"))
        markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu"))
        bot.edit_message_text(msg, cid, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    except:
        bot.edit_message_text("❌ حدث خطأ في السيرفر، جرب مرة أخرى.", cid, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "check_inbox")
def check_temp_inbox(call):
    cid = call.message.chat.id
    email = active_temp_mails.get(cid)
    if not email:
        return bot.answer_callback_query(call.id, "❌ لم تقم بإنشاء إيميل مؤقت بعد!", show_alert=True)
    
    bot.answer_callback_query(call.id, "🔄 جاري تحديث الصندوق...")
    login, domain = email.split('@')
    try:
        r = requests.get(f"https://www.1secmail.com/api/v1/?action=getMessages&login={login}&domain={domain}")
        messages = r.json()
        
        if not messages:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔄 تحديث", callback_data="check_inbox"))
            markup.add(types.InlineKeyboardButton("🔙 القائمة", callback_data="main_menu"))
            bot.edit_message_text(f"✉️ **صندوق الوارد:** `{email}`\n\n📭 الصندوق فارغ حالياً، انتظر قليلاً ثم حدث.", cid, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        else:
            # نجلب آخر رسالة فقط للتبسيط
            msg_id = messages[0]['id']
            r_msg = requests.get(f"https://www.1secmail.com/api/v1/?action=readMessage&login={login}&domain={domain}&id={msg_id}")
            msg_data = r_msg.json()
            subject = msg_data.get('subject', 'بدون عنوان')
            text_body = msg_data.get('textBody', 'لا يوجد نص')
            
            out = f"📬 **رسالة جديدة!**\n✉️ إلى: `{email}`\n\n📌 **الموضوع:** {subject}\n📝 **المحتوى:**\n`{text_body[:500]}`"
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔄 فحص مجدداً", callback_data="check_inbox"))
            markup.add(types.InlineKeyboardButton("🔙 القائمة", callback_data="main_menu"))
            bot.edit_message_text(out, cid, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    except:
        bot.answer_callback_query(call.id, "❌ خطأ في الاتصال.")

# ==================== 7. شراء Gmail دائم (المدفوع) ====================
@bot.callback_query_handler(func=lambda call: call.data == "buy_gmail")
def buy_permanent_gmail(call):
    cid = call.message.chat.id
    user = get_user(cid)
    
    if user[2] < GMAIL_PRICE:
        return bot.answer_callback_query(call.id, f"❌ رصيدك لا يكفي. السعر: {GMAIL_PRICE}$", show_alert=True)
    
    # البحث عن جيميل متاح في المخزون
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, email_pass FROM paid_accounts WHERE is_sold = FALSE LIMIT 1")
    acc = cur.fetchone()
    
    if not acc:
        conn.close()
        return bot.answer_callback_query(call.id, "⚠️ المخزون فارغ حالياً، يرجى المحاولة لاحقاً.", show_alert=True)
    
    # تنفيذ الشراء
    acc_id, email_pass = acc[0], acc[1]
    cur.execute("UPDATE paid_accounts SET is_sold = TRUE, buyer_id = %s WHERE id = %s", (cid, acc_id))
    cur.execute("UPDATE users SET balance = balance - %s WHERE chat_id = %s", (GMAIL_PRICE, cid))
    conn.commit()
    conn.close()
    
    # رسالة النجاح
    msg = f"🎉 **تم الشراء بنجاح!**\n\n💎 تفاصيل الحساب (Gmail):\n`{email_pass}`\n\n⚠️ يرجى تغيير كلمة المرور فوراً لتأمين حسابك."
    bot.edit_message_text(msg, cid, call.message.message_id, parse_mode="Markdown")
    
    # إشعار القناة
    markup_ch = types.InlineKeyboardMarkup()
    markup_ch.add(types.InlineKeyboardButton("🤖 اشتري جيميل دائم", url=f"https://t.me/{bot.get_me().username}"))
    bot.send_message(LOG_CHANNEL_ID, f"💎 **شراء حساب Gmail دائم!** 🚀\nتم تسليم الحساب بنجاح لعميلنا.", reply_markup=markup_ch, parse_mode="Markdown")

# ==================== 8. نظام الشحن والإيصالات ====================
@bot.callback_query_handler(func=lambda call: call.data == "deposit_select_amount")
def deposit_amount_menu(call):
    markup = types.InlineKeyboardMarkup(row_width=2)
    for amt in [1, 3, 5, 10]:
        egp_val = int(amt * USD_EGP_RATE)
        markup.add(types.InlineKeyboardButton(f"{amt}$ ({egp_val} EGP) 🇪🇬", callback_data=f"dep_amt:{amt}"))
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu"))
    bot.edit_message_text("💰 **شحن الرصيد**\nاختر الباقة المناسبة:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("dep_amt:"))
def deposit_method_menu(call):
    amount = call.data.split(":")[1]
    egp_val = int(float(amount) * USD_EGP_RATE)
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(f"Vodafone Cash ({egp_val} EGP) 🇪🇬", callback_data=f"pay_mtd:vodafone:{amount}"),
        types.InlineKeyboardButton("Binance Pay 🟨", callback_data=f"pay_mtd:binance:{amount}"),
        types.InlineKeyboardButton("🔙 رجوع", callback_data="deposit_select_amount")
    )
    bot.edit_message_text(f"💳 المبلغ: **{amount}$**\nاختر وسيلة الدفع:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_mtd:"))
def pay_info_msg(call):
    parts = call.data.split(":")
    method, amount_usd = parts[1], parts[2]
    amount_egp = int(float(amount_usd) * USD_EGP_RATE)
    
    msg = ""
    if method == 'vodafone':
        msg = f"🇪🇬 **فودافون كاش**\n📱 رقم المحفظة: `{WALLETS['vodafone']}`\n💸 **المطلوب:** `{amount_egp} جنيه`\n⚠️ حول المبلغ كاملاً وأرسل صورة الإيصال هنا."
    elif method == 'binance':
        msg = f"🟨 **Binance Pay**\n🆔 Pay ID: `{WALLETS['binance_id']}`\n💰 **المبلغ:** `{amount_usd} USDT`\n📸 أرسل صورة المعاملة هنا."

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="deposit_select_amount"))
    bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(content_types=['photo'])
def handle_receipt(message):
    cid = message.chat.id
    bot.forward_message(ADMIN_ID, cid, message.message_id)
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(
        types.InlineKeyboardButton("✅ 1$", callback_data=f"add:{cid}:1"),
        types.InlineKeyboardButton("✅ 5$", callback_data=f"add:{cid}:5"),
        types.InlineKeyboardButton("❌ رفض (مبلغ ناقص)", callback_data=f"rej:{cid}:less"),
        types.InlineKeyboardButton("❌ رفض (إيصال وهمي)", callback_data=f"rej:{cid}:fake")
    )
    user = get_user(cid)
    bot.send_message(ADMIN_ID, f"📩 **إيصال جديد!**\n🆔 الآيدي: `{cid}`\n💰 رصيده: `{user[2]}$`", reply_markup=markup, parse_mode="Markdown")
    bot.reply_to(message, "✅ **تم الاستلام!** جاري مراجعة الإيصال.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("add:") or call.data.startswith("rej:"))
def admin_process_payment(call):
    if call.from_user.id != ADMIN_ID: return
    parts = call.data.split(":")
    action, uid = parts[0], parts[1]
    
    if action == "add":
        val = float(parts[2])
        update_balance(uid, val)
        bot.send_message(uid, f"🎉 **تم قبول الشحن!**\n💰 تمت إضافة {val}$ إلى رصيدك.")
        bot.edit_message_text(f"✅ تم الشحن {val}$ لـ {uid}", call.message.chat.id, call.message.message_id)
    elif action == "rej":
        reason = "المبلغ المحول ناقص" if parts[2] == "less" else "الإيصال غير صحيح"
        bot.send_message(uid, f"❌ **تم رفض طلب الشحن**\n⚠️ السبب: {reason}")
        bot.edit_message_text(f"❌ تم الرفض لـ {uid}", call.message.chat.id, call.message.message_id)

# ==================== 9. الحساب ولوحة التحكم ====================
@bot.callback_query_handler(func=lambda call: call.data == "invite")
def invite_link(call):
    cid = call.message.chat.id
    link = f"https://t.me/{bot.get_me().username}?start={cid}"
    msg = f"🎁 **اربح {REFERRAL_REWARD}$** لكل صديق يسجل من خلالك!\n🔗 رابطك:\n`{link}`"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu"))
    bot.edit_message_text(msg, cid, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "profile")
def profile_show(call):
    user = get_user(call.message.chat.id)
    msg = f"👤 **حسابي**\n🆔 `{user[0]}`\n💰 الرصيد: `{user[2]:.2f}$`"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu"))
    bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "admin_panel")
def admin_menu_func(call):
    if call.from_user.id != ADMIN_ID: return
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM paid_accounts WHERE is_sold = FALSE")
    stock_count = cur.fetchone()[0]
    conn.close()
    
    msg = f"👮 **لوحة التحكم**\n📦 مخزون الجيميلات المتاحة للبيع: `{stock_count}`\nاختر إجراء:"
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📢 إذاعة", callback_data="adm_broadcast"),
        types.InlineKeyboardButton("➕ إضافة جيميل للمخزون", callback_data="adm_add_gmail"),
        types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")
    )
    bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

# إضافة جيميلات للمخزون
@bot.callback_query_handler(func=lambda call: call.data == "adm_add_gmail")
def ask_add_gmail(call):
    msg = bot.send_message(call.message.chat.id, "📦 أرسل بيانات الجيميل (الإيميل والباسورد وأي تفاصيل):")
    bot.register_next_step_handler(msg, do_add_gmail)

def do_add_gmail(message):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO paid_accounts (account_type, email_pass) VALUES ('GMAIL', %s)", (message.text,))
    conn.commit()
    conn.close()
    bot.send_message(ADMIN_ID, "✅ تم إضافة الحساب للمخزون بنجاح وجاهز للبيع.")

# الإذاعة
@bot.callback_query_handler(func=lambda call: call.data == "adm_broadcast")
def ask_broadcast(call):
    msg = bot.send_message(call.message.chat.id, "📢 أرسل الرسالة:")
    bot.register_next_step_handler(msg, do_broadcast)

def do_broadcast(message):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT chat_id FROM users")
    users = cur.fetchall()
    conn.close()
    for u in users:
        try: bot.copy_message(u[0], message.chat.id, message.message_id)
        except: pass
    bot.send_message(ADMIN_ID, "✅ تمت الإذاعة.")

@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def back_main(call): main_menu(call.message.chat.id)

# ==================== التشغيل ====================
if __name__ == "__main__":
    init_db()
    t = threading.Thread(target=run_web_server)
    t.start()
    bot.infinity_polling(skip_pending=True)
    
