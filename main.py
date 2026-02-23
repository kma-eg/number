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
BOT_TOKEN = "6058936352:AAFNKPjfj5A4qMYlyE-KPhBx_BUjSNlbYy0"
ADMIN_ID = 6318333901

SUPABASE_URL = "postgresql://postgres.rjialktdutmbuqhaznzu:5455%40Kma01020755609@aws-0-us-west-2.pooler.supabase.com:6543/postgres"

SUB_CHANNEL_ID = -1003316907453       
SUB_CHANNEL_LINK = "https://t.me/kma_c"

LOG_CHANNEL_ID = -1003709813767       
LOG_CHANNEL_LINK = "https://t.me/kms_ad"

REFERRAL_REWARD = 0.02  
GMAIL_PRICE = 1.0       

# ==================== 2. سيرفر Flask (لـ Render) ====================
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
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                chat_id BIGINT PRIMARY KEY, username TEXT,
                balance FLOAT DEFAULT 0, referrer_id BIGINT,
                joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS email_history (
                id SERIAL PRIMARY KEY, chat_id BIGINT,
                email TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
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

def get_total_users():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    count = cur.fetchone()[0]
    conn.close()
    return count

# ==================== 4. المتغيرات والذاكرة المؤقتة ====================
bot = telebot.TeleBot(BOT_TOKEN)
user_captchas = {}
active_temp_mails = {}

# قاموس لتسجيل وقت آخر إشعار "إعادة استخدام" لكل مستخدم (عشان ميزعجكش)
admin_notifications_cooldown = {}

def gen_complex_captcha():
    chars = string.ascii_letters + string.digits + "@#$&*?!"
    return ''.join(random.choice(chars) for _ in range(6))

def mask_string(s, visible_start=2, visible_end=2):
    if len(s) <= visible_start + visible_end: return s
    return s[:visible_start] + "*" * (len(s) - visible_start - visible_end) + s[-visible_end:]

# ==================== 5. منطق البداية والقائمة ====================
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
        admin_msg = f"👤 **قام مستخدم جديد بالدخول للبوت الخاص بك**\n\n"
        admin_msg += f"📌 **معلومات العضو:**\n• الاسم: {user_link}\n• اسم المستخدم: @{username}\n• الآيدي: `{cid}`\n\n"
        admin_msg += f"📊 **إجمالي عدد المحادثات حتى الآن:** {total_users}"
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
        bot.send_message(cid, f"🔒 **التحقق البشري**\nاكتب الرموز التالية بدقة (الحروف الكبيرة والصغيرة والرموز):\n\n`{captcha_code}`", parse_mode="Markdown")

    elif status == "EXISTS":
        # التحقق من الـ Cooldown (10 أيام = 864000 ثانية)
        last_notified = admin_notifications_cooldown.get(cid, 0)
        if (current_time - last_notified) > 864000:
            admin_msg = f"🔄 **مستخدم قديم عاد لاستخدام البوت.**\n\n"
            admin_msg += f"📌 **معلومات العضو:**\n• الاسم: {user_link}\n• اسم المستخدم: @{username}\n• الآيدي: `{cid}`\n\n"
            admin_msg += f"📊 **إجمالي عدد المحادثات حتى الآن:** {total_users}"
            try: bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown")
            except: pass
            # تحديث وقت آخر إشعار
            admin_notifications_cooldown[cid] = current_time
            
        check_sub_and_open_menu(cid)

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
        types.InlineKeyboardButton("👤 حسابي", callback_data="profile"),
        types.InlineKeyboardButton("🎁 دعوة أصدقاء", callback_data="invite"),
        types.InlineKeyboardButton("✅ قناة التفعيلات", url=LOG_CHANNEL_LINK)
    )
    if cid == ADMIN_ID: markup.add(types.InlineKeyboardButton("👮 لوحة الأدمن", callback_data="admin_panel"))
    bot.send_message(cid, f"👋 **أهلاً بك في بوت الخدمات الذكية!**\n💰 رصيدك: `{balance:.2f}$`\nاختر من القائمة:", reply_markup=markup, parse_mode="Markdown")

# ==================== 6. الإيميلات المؤقتة (API جديد قوي Mail.gw) ====================
@bot.callback_query_handler(func=lambda call: call.data == "gen_temp")
def generate_temp_email(call):
    cid = call.message.chat.id
    current_time = time.time()
    
    if cid in active_temp_mails:
        last_gen_time = active_temp_mails[cid].get('time', 0)
        time_diff = current_time - last_gen_time
        if time_diff < 900:
            mins_left = int((900 - time_diff) // 60)
            return bot.answer_callback_query(call.id, f"⏳ الإيميل المؤقت صالح لمدة 15 دقيقة. يرجى الانتظار {mins_left} دقيقة.", show_alert=True)

    bot.edit_message_text("🔄 جاري إنشاء إيميل مؤقت وتجهيز السيرفرات...", cid, call.message.message_id)
    try:
        # جلب الدومينات المتاحة
        domains = requests.get("https://api.mail.gw/domains").json()
        domain = domains['hydra:member'][0]['domain']
        
        # إنشاء إيميل وباسورد عشوائي
        address = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10)) + "@" + domain
        password = "BotSecurePass123!"
        
        # تسجيل الحساب في الموقع
        requests.post("https://api.mail.gw/accounts", json={"address": address, "password": password})
        
        # جلب التوكن (مفتاح الدخول للصندوق)
        token_req = requests.post("https://api.mail.gw/token", json={"address": address, "password": password})
        token = token_req.json()['token']
        
        active_temp_mails[cid] = {'email': address, 'token': token, 'time': current_time}
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO email_history (chat_id, email) VALUES (%s, %s)", (cid, address))
        conn.commit()
        conn.close()

        msg = f"✅ **تم إنشاء الإيميل بنجاح!**\n\n✉️ الإيميل:\n`{address}`\n\n⚠️ صالح لمدة 15 دقيقة، استخدمه للتسجيل ثم اضغط (صندوق الوارد)."
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📥 فحص صندوق الوارد", callback_data="check_inbox"))
        markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu"))
        bot.edit_message_text(msg, cid, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        bot.edit_message_text(f"❌ حدث ضغط على السيرفر، يرجى المحاولة بعد قليل.", cid, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "check_inbox")
def check_temp_inbox(call):
    cid = call.message.chat.id
    temp_data = active_temp_mails.get(cid)
    
    if not temp_data:
        return bot.answer_callback_query(call.id, "❌ لم تقم بإنشاء إيميل مؤقت بعد!", show_alert=True)
    
    email = temp_data['email']
    token = temp_data['token']
    bot.answer_callback_query(call.id, "🔄 جاري فحص الصندوق...")
    
    try:
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get("https://api.mail.gw/messages", headers=headers)
        messages = r.json().get('hydra:member', [])
        
        if not messages:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔄 تحديث الصندوق", callback_data="check_inbox"))
            markup.add(types.InlineKeyboardButton("🔙 القائمة", callback_data="main_menu"))
            bot.edit_message_text(f"✉️ **الصندوق:** `{email}`\n\n📭 الصندوق فارغ حالياً، انتظر قليلاً ثم حدث.", cid, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        else:
            msg_id = messages[0]['id']
            r_msg = requests.get(f"https://api.mail.gw/messages/{msg_id}", headers=headers)
            msg_data = r_msg.json()
            subject = msg_data.get('subject', 'بدون عنوان')
            text_body = msg_data.get('text', 'لا يوجد نص')
            
            code_match = re.search(r'\b\d{4,6}\b', text_body)
            code = code_match.group(0) if code_match else None
            
            if code:
                login, domain = email.split('@')
                masked_email = mask_string(login, 2, 1) + "@" + domain
                masked_code = mask_string(code, 1, 1)
                
                proof_msg = f"🔥 **تم استلام كود تفعيل جديد!**\n\n📧 الإيميل: `{masked_email}`\n🔐 الكود: `{masked_code}`\n\n✨ البوت الأسرع والأفضل للخدمات 🚀"
                markup_ch = types.InlineKeyboardMarkup()
                try:
                    bot_username = bot.get_me().username
                    markup_ch.add(types.InlineKeyboardButton("احصل على إيميلات وتفعيلات مجاناً 🔥", url=f"https://t.me/{bot_username}"))
                except: pass
                bot.send_message(LOG_CHANNEL_ID, proof_msg, reply_markup=markup_ch, parse_mode="Markdown")

            out = f"📬 **رسالة جديدة!**\n✉️ إلى: `{email}`\n\n📌 **الموضوع:** {subject}\n📝 **المحتوى:**\n`{text_body[:500]}`"
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔄 فحص مجدداً", callback_data="check_inbox"))
            markup.add(types.InlineKeyboardButton("🔙 القائمة", callback_data="main_menu"))
            bot.edit_message_text(out, cid, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ خطأ في الاتصال بالبريد.", show_alert=True)

# ==================== 7. شراء Gmail (مع نظام التأكيد والدوامة) ====================
@bot.callback_query_handler(func=lambda call: call.data == "buy_gmail")
def buy_gmail_request(call):
    cid = call.message.chat.id
    user = get_user(cid)
    
    if user[2] < GMAIL_PRICE:
        return bot.answer_callback_query(call.id, f"❌ رصيدك لا يكفي لإتمام العملية. السعر: {GMAIL_PRICE}$", show_alert=True)
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM paid_accounts WHERE is_sold = FALSE LIMIT 1")
    acc = cur.fetchone()
    conn.close()
    
    if not acc:
        return bot.answer_callback_query(call.id, "⚠️ المخزون فارغ حالياً، تواصل مع الإدارة أو جرب لاحقاً.", show_alert=True)
    
    # رسالة التأكيد (مفيش خصم فلوس لسه)
    msg = f"⚠️ **مراجعة وتأكيد الطلب**\n\n"
    msg += f"📦 **المنتج:** حساب Gmail (دائم ومفعل)\n"
    msg += f"💵 **السعر:** `{GMAIL_PRICE}$`\n"
    msg += f"💰 **رصيدك الحالي:** `{user[2]:.2f}$`\n\n"
    msg += "هل أنت متأكد من رغبتك في إتمام عملية الشراء واستلام الحساب؟"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ تأكيد وخصم الرصيد", callback_data="confirm_buy_gmail"),
        types.InlineKeyboardButton("❌ إلغاء العملية", callback_data="main_menu")
    )
    bot.edit_message_text(msg, cid, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "confirm_buy_gmail")
def confirm_buy_permanent_gmail(call):
    cid = call.message.chat.id
    user = get_user(cid)
    
    if user[2] < GMAIL_PRICE:
        return bot.answer_callback_query(call.id, "❌ رصيدك غير كافٍ.", show_alert=True)
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, email_pass FROM paid_accounts WHERE is_sold = FALSE LIMIT 1")
    acc = cur.fetchone()
    
    if not acc:
        conn.close()
        return bot.answer_callback_query(call.id, "⚠️ نأسف، نفد المخزون أثناء تأكيد طلبك.", show_alert=True)
    
    # هنا بس بيتم الشراء وخصم الفلوس
    acc_id, email_pass = acc[0], acc[1]
    cur.execute("UPDATE paid_accounts SET is_sold = TRUE, buyer_id = %s WHERE id = %s", (cid, acc_id))
    cur.execute("UPDATE users SET balance = balance - %s WHERE chat_id = %s", (GMAIL_PRICE, cid))
    conn.commit()
    conn.close()
    
    msg = f"🎉 **تمت عملية الشراء بنجاح!**\n\n💎 تفاصيل الحساب (Gmail):\n`{email_pass}`\n\n⚠️ يرجى تغيير كلمة المرور فوراً لتأمين حسابك."
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 العودة للقائمة", callback_data="main_menu"))
    bot.edit_message_text(msg, cid, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    
    try:
        ch_msg = f"🛒 **عملية شراء جديدة!**\n\n👤 قام أحد عملائنا بشراء حساب Gmail دائم بنجاح 💎\n\n✨ انضم الآن واستفد من خدماتنا المضمونة 🚀"
        markup_ch = types.InlineKeyboardMarkup()
        bot_username = bot.get_me().username
        markup_ch.add(types.InlineKeyboardButton("شراء حسابك الآن 🛒", url=f"https://t.me/{bot_username}"))
        bot.send_message(LOG_CHANNEL_ID, ch_msg, reply_markup=markup_ch, parse_mode="Markdown")
    except: pass

# ==================== 8. الحساب ولوحة التحكم ====================
@bot.callback_query_handler(func=lambda call: call.data == "invite")
def invite_link(call):
    cid = call.message.chat.id
    try: bot_username = bot.get_me().username
    except: bot_username = "bot"
    link = f"https://t.me/{bot_username}?start={cid}"
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
    users_count = get_total_users()
    cur.execute("SELECT chat_id, COUNT(*) as mail_count FROM email_history GROUP BY chat_id ORDER BY mail_count DESC LIMIT 10")
    top_users = cur.fetchall()
    conn.close()
    
    top_text = ""
    if top_users:
        for idx, u in enumerate(top_users, 1): top_text += f"{idx}- أيدي: `{u[0]}` | استخرج: **{u[1]}** إيميل\n"
    else: top_text = "لا يوجد بيانات بعد.\n"
    
    msg = f"👮 **لوحة التحكم**\n👥 إجمالي المنضمين للبوت: `{users_count}` مستخدم\n📦 مخزون الجيميلات: `{stock_count}`\n\n🏆 **أكثر المستخدمين استخراجاً:**\n{top_text}\nاختر إجراء:"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📢 إذاعة", callback_data="adm_broadcast"),
        types.InlineKeyboardButton("➕ إضافة جيميل للمخزون", callback_data="adm_add_gmail"),
        types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")
    )
    bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

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
    bot.send_message(ADMIN_ID, "✅ تم إضافة الحساب للمخزون بنجاح.")

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
