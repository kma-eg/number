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
import re
from flask import Flask

# ==================== 1. إعدادات البوت والمفاتيح ====================
BOT_TOKEN = "ضع_التوكن_الجديد_هنا" # <--- غير ده بالتوكن الجديد من BotFather
ADMIN_ID = 6318333901

SUPABASE_URL = "postgresql://postgres.rjialktdutmbuqhaznzu:5455%40Kma01020755609@aws-0-us-west-2.pooler.supabase.com:6543/postgres"

SUB_CHANNEL_ID = -1003316907453       
SUB_CHANNEL_LINK = "https://t.me/kma_c"

LOG_CHANNEL_ID = -1003709813767       
LOG_CHANNEL_LINK = "https://t.me/kms_ad"

REFERRAL_REWARD = 0.02  
GMAIL_PRICE = 1.0       

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
    "Accept": "application/json"
}

# ==================== 2. سيرفر Flask ====================
app = Flask(__name__)
@app.route('/')
def home(): return "Temp Mail Bot is Running! 🚀"
def run_web_server():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

# ==================== 3. قاعدة البيانات ====================
def get_db_connection(): return psycopg2.connect(SUPABASE_URL)

def init_db():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS users (chat_id BIGINT PRIMARY KEY, username TEXT, balance FLOAT DEFAULT 0, referrer_id BIGINT, joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP);""")
        cur.execute("""CREATE TABLE IF NOT EXISTS email_history (id SERIAL PRIMARY KEY, chat_id BIGINT, email TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);""")
        cur.execute("""CREATE TABLE IF NOT EXISTS paid_accounts (id SERIAL PRIMARY KEY, account_type TEXT, email_pass TEXT, is_sold BOOLEAN DEFAULT FALSE, buyer_id BIGINT);""")
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

def get_total_users():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    count = cur.fetchone()[0]
    conn.close()
    return count

# ==================== 4. المتغيرات ====================
bot = telebot.TeleBot(BOT_TOKEN)
user_captchas = {}
active_temp_mails = {}
admin_notifications_cooldown = {}

def gen_complex_captcha():
    chars = string.ascii_letters + string.digits + "@#$&*?!"
    return ''.join(random.choice(chars) for _ in range(6))

def mask_string(s, visible_start=2, visible_end=2):
    if len(s) <= visible_start + visible_end: return s
    return s[:visible_start] + "*" * (len(s) - visible_start - visible_end) + s[-visible_end:]

# ==================== 5. البداية والقائمة ====================
@bot.message_handler(commands=['start'])
def start_msg(message):
    cid = message.chat.id
    username = message.from_user.username or "لا يوجد"
    first_name = message.from_user.first_name
    args = message.text.split()
    referrer_id = 0
    if len(args) > 1 and args[1].isdigit():
        ref = int(args[1])
        if ref != cid: referrer_id = ref

    status = add_user(cid, username, referrer_id)
    total_users = get_total_users()
    user_link = f"[{first_name}](tg://user?id={cid})"
    current_time = time.time()
    
    if status == "NEW":
        admin_msg = f"👤 **قام مستخدم جديد بالدخول للبوت**\n\n📌 **معلومات العضو:**\n• الاسم: {user_link}\n• اليوزر: @{username}\n• الآيدي: `{cid}`\n\n📊 **إجمالي المحادثات:** {total_users}"
        try: bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown")
        except: pass

        if referrer_id != 0:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("UPDATE users SET balance = balance + %s WHERE chat_id IN (%s, %s)", (REFERRAL_REWARD, referrer_id, cid))
            conn.commit()
            conn.close()
            try: bot.send_message(referrer_id, f"🎉 **دعوة ناجحة!**\nسجل {first_name} وحصلت على {REFERRAL_REWARD}$")
            except: pass
            
        captcha_code = gen_complex_captcha()
        user_captchas[cid] = captcha_code
        bot.send_message(cid, f"🔒 **التحقق البشري**\nاكتب الرموز التالية بدقة:\n\n`{captcha_code}`", parse_mode="Markdown")

    elif status == "EXISTS":
        last_notified = admin_notifications_cooldown.get(cid, 0)
        if (current_time - last_notified) > 864000:
            admin_msg = f"🔄 **مستخدم قديم عاد لاستخدام البوت**\n\n📌 **معلومات العضو:**\n• الاسم: {user_link}\n• اليوزر: @{username}\n• الآيدي: `{cid}`\n\n📊 **إجمالي المحادثات:** {total_users}"
            try: bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown")
            except: pass
            admin_notifications_cooldown[cid] = current_time
        check_sub_and_open_menu(cid)

@bot.message_handler(func=lambda m: m.chat.id in user_captchas)
def verify_captcha(message):
    cid = message.chat.id
    if message.text.strip() == user_captchas[cid]:
        del user_captchas[cid]
        check_sub_and_open_menu(cid)
    else: bot.send_message(cid, "❌ **كود خاطئ!** تأكد من الحروف.")

def check_sub_and_open_menu(cid):
    try:
        stat = bot.get_chat_member(SUB_CHANNEL_ID, cid).status
        if stat not in ['member', 'administrator', 'creator']: raise Exception
        main_menu(cid)
    except:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 اشترك في القناة", url=SUB_CHANNEL_LINK), types.InlineKeyboardButton("🔄 تحقق", callback_data="check_sub"))
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
        types.InlineKeyboardButton("💎 شراء Gmail", callback_data="buy_gmail"),
        types.InlineKeyboardButton("👤 حسابي", callback_data="profile"),
        types.InlineKeyboardButton("🎁 دعوة أصدقاء", callback_data="invite"),
        types.InlineKeyboardButton("✅ التفعيلات", url=LOG_CHANNEL_LINK)
    )
    if cid == ADMIN_ID: markup.add(types.InlineKeyboardButton("👮 لوحة الأدمن", callback_data="admin_panel"))
    bot.send_message(cid, f"👋 **أهلاً بك!**\n💰 رصيدك: `{balance:.2f}$`\nاختر من القائمة:", reply_markup=markup, parse_mode="Markdown")

# ==================== 6. الإيميلات المؤقتة (API جديد ومستقر) ====================
@bot.callback_query_handler(func=lambda call: call.data == "gen_temp")
def generate_temp_email(call):
    cid = call.message.chat.id
    current_time = time.time()
    
    if cid in active_temp_mails:
        last_gen_time = active_temp_mails[cid].get('time', 0)
        time_diff = current_time - last_gen_time
        if time_diff < 900:
            mins_left = int((900 - time_diff) // 60)
            return bot.answer_callback_query(call.id, f"⏳ الإيميل المؤقت صالح. يرجى الانتظار {mins_left} دقيقة.", show_alert=True)

    bot.edit_message_text("🔄 جاري إنشاء إيميل مؤقت...", cid, call.message.message_id)
    try:
        # استخدام API قوي لا يحظر السيرفرات
        r = requests.post("https://api.internal.temp-mail.io/api/v3/email/new", json={"min_name_length": 10, "max_name_length": 10}, headers=HEADERS)
        if r.status_code != 200: raise Exception("Server API Error")
        
        email = r.json().get('email')
        active_temp_mails[cid] = {'email': email, 'time': current_time}
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO email_history (chat_id, email) VALUES (%s, %s)", (cid, email))
        conn.commit()
        conn.close()

        msg = f"✅ **تم إنشاء الإيميل بنجاح!**\n\n✉️ الإيميل:\n`{email}`\n\n⚠️ صالح لمدة 15 دقيقة."
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📥 فحص صندوق الوارد", callback_data="check_inbox"), types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu"))
        bot.edit_message_text(msg, cid, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        bot.edit_message_text("❌ حدث ضغط على السيرفر، يرجى المحاولة بعد قليل.", cid, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "check_inbox")
def check_temp_inbox(call):
    cid = call.message.chat.id
    temp_data = active_temp_mails.get(cid)
    
    if not temp_data: return bot.answer_callback_query(call.id, "❌ لم تقم بإنشاء إيميل مؤقت!", show_alert=True)
    
    email = temp_data['email']
    bot.answer_callback_query(call.id, "🔄 جاري فحص الصندوق...")
    
    try:
        r = requests.get(f"https://api.internal.temp-mail.io/api/v3/email/{email}/messages", headers=HEADERS)
        messages = r.json()
        
        if not messages:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔄 تحديث", callback_data="check_inbox"), types.InlineKeyboardButton("🔙 القائمة", callback_data="main_menu"))
            bot.edit_message_text(f"✉️ **الصندوق:** `{email}`\n\n📭 فارغ حالياً.", cid, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        else:
            msg_data = messages[0]
            subject = msg_data.get('subject', 'بدون عنوان')
            text_body = msg_data.get('body_text', 'لا يوجد نص')
            
            code_match = re.search(r'\b\d{4,6}\b', text_body)
            code = code_match.group(0) if code_match else None
            
            if code:
                login, domain = email.split('@')
                masked_email = mask_string(login, 2, 1) + "@" + domain
                masked_code = mask_string(code, 1, 1)
                proof_msg = f"🔥 **تفعيل جديد!**\n\n📧 الإيميل: `{masked_email}`\n🔐 الكود: `{masked_code}`\n\n✨ البوت الأسرع 🚀"
                markup_ch = types.InlineKeyboardMarkup()
                try: markup_ch.add(types.InlineKeyboardButton("احصل على إيميلات 🔥", url=f"https://t.me/{bot.get_me().username}"))
                except: pass
                bot.send_message(LOG_CHANNEL_ID, proof_msg, reply_markup=markup_ch, parse_mode="Markdown")

            out = f"📬 **رسالة جديدة!**\n✉️ إلى: `{email}`\n\n📌 **الموضوع:** {subject}\n📝 **المحتوى:**\n`{text_body[:500]}`"
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔄 فحص مجدداً", callback_data="check_inbox"), types.InlineKeyboardButton("🔙 القائمة", callback_data="main_menu"))
            bot.edit_message_text(out, cid, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        bot.answer_callback_query(call.id, "❌ خطأ في الاتصال بالبريد.", show_alert=True)

# ==================== 7. شراء Gmail ====================
@bot.callback_query_handler(func=lambda call: call.data == "buy_gmail")
def buy_gmail_request(call):
    cid = call.message.chat.id
    user = get_user(cid)
    if user[2] < GMAIL_PRICE: return bot.answer_callback_query(call.id, f"❌ رصيدك لا يكفي. السعر: {GMAIL_PRICE}$", show_alert=True)
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM paid_accounts WHERE is_sold = FALSE LIMIT 1")
    acc = cur.fetchone()
    conn.close()
    if not acc: return bot.answer_callback_query(call.id, "⚠️ المخزون فارغ حالياً.", show_alert=True)
    
    msg = f"⚠️ **مراجعة الطلب**\n\n📦 **المنتج:** حساب Gmail\n💵 **السعر:** `{GMAIL_PRICE}$`\n💰 **رصيدك:** `{user[2]:.2f}$`\n\nهل أنت متأكد من الشراء؟"
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("✅ تأكيد", callback_data="confirm_buy_gmail"), types.InlineKeyboardButton("❌ إلغاء", callback_data="main_menu"))
    bot.edit_message_text(msg, cid, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "confirm_buy_gmail")
def confirm_buy_permanent_gmail(call):
    cid = call.message.chat.id
    user = get_user(cid)
    if user[2] < GMAIL_PRICE: return bot.answer_callback_query(call.id, "❌ رصيدك غير كافٍ.", show_alert=True)
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, email_pass FROM paid_accounts WHERE is_sold = FALSE LIMIT 1")
    acc = cur.fetchone()
    if not acc:
        conn.close()
        return bot.answer_callback_query(call.id, "⚠️ نفد المخزون.", show_alert=True)
    
    acc_id, email_pass = acc[0], acc[1]
    cur.execute("UPDATE paid_accounts SET is_sold = TRUE, buyer_id = %s WHERE id = %s", (cid, acc_id))
    cur.execute("UPDATE users SET balance = balance - %s WHERE chat_id = %s", (GMAIL_PRICE, cid))
    conn.commit()
    conn.close()
    
    msg = f"🎉 **تم الشراء!**\n\n💎 تفاصيل الحساب:\n`{email_pass}`\n\n⚠️ يرجى تغيير كلمة المرور."
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 القائمة", callback_data="main_menu"))
    bot.edit_message_text(msg, cid, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    
    try:
        ch_msg = f"🛒 **عملية شراء جديدة!**\n\n👤 قام عميل بشراء حساب Gmail دائم 💎\n\n✨ انضم واستفد من خدماتنا 🚀"
        markup_ch = types.InlineKeyboardMarkup()
        markup_ch.add(types.InlineKeyboardButton("شراء حسابك 🛒", url=f"https://t.me/{bot.get_me().username}"))
        bot.send_message(LOG_CHANNEL_ID, ch_msg, reply_markup=markup_ch, parse_mode="Markdown")
    except: pass

# ==================== 8. الحساب ولوحة التحكم ====================
@bot.callback_query_handler(func=lambda call: call.data == "invite")
def invite_link(call):
    cid = call.message.chat.id
    try: bot_username = bot.get_me().username
    except: bot_username = "bot"
    msg = f"🎁 **اربح {REFERRAL_REWARD}$** لكل صديق!\n🔗 رابطك:\n`https://t.me/{bot_username}?start={cid}`"
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
    users_count = get_total_users()
    cur.execute("SELECT chat_id, COUNT(*) as mail_count FROM email_history GROUP BY chat_id ORDER BY mail_count DESC LIMIT 10")
    top_users = cur.fetchall()
    conn.close()
    top_text = "".join([f"{idx}- أيدي: `{u[0]}` | **{u[1]}** إيميل\n" for idx, u in enumerate(top_users, 1)]) if top_users else "لا يوجد بيانات.\n"
    
    msg = f"👮 **لوحة التحكم**\n👥 المستخدمين: `{users_count}`\n📦 المخزون: `{stock_count}`\n\n🏆 **الأكثر استخراجاً:**\n{top_text}\nاختر إجراء:"
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("📢 إذاعة", callback_data="adm_broadcast"), types.InlineKeyboardButton("➕ إضافة جيميل", callback_data="adm_add_gmail"), types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu"))
    bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "adm_add_gmail")
def ask_add_gmail(call):
    msg = bot.send_message(call.message.chat.id, "📦 أرسل بيانات الجيميل:")
    bot.register_next_step_handler(msg, do_add_gmail)

def do_add_gmail(message):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO paid_accounts (account_type, email_pass) VALUES ('GMAIL', %s)", (message.text,))
    conn.commit()
    conn.close()
    bot.send_message(ADMIN_ID, "✅ تم الإضافة بنجاح.")

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

if __name__ == "__main__":
    init_db()
    t = threading.Thread(target=run_web_server)
    t.start()
    
    print("🤖 Bot is starting...")
    while True:
        try: bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(5)
    
