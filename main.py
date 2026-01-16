import os
import telebot
from telebot import types
import requests
import psycopg2
import threading
import time
import random
import string
from flask import Flask, request

# ==================== 1. إعدادات البيئة (من Render) ====================
# هذه المتغيرات تسحب القيم من إعدادات Render مباشرة لضمان الأمان
BOT_TOKEN = os.environ.get('TOKEN')
ADMIN_ID = int(os.environ.get('ADMIN_ID')) # تحويل الآيدي لرقم
API_KEY = os.environ.get('API_KEY') # مفتاح الموقع الروسي
SUPABASE_URL = os.environ.get('SUPABASE_URL') # رابط قاعدة البيانات

# قناة الاشتراك الإجباري (عدلها باسم قناتك)
CHANNEL_USER = "@kma_c" 

# إعدادات المحافظ اليدوية (تظهر للمستخدم)
WALLETS = {
    'vodafone': '01020755609', # رقم فودافون كاش
    'stc': '05xxxxxxxxx',       # رقم STC
    'payeer_manual': 'P10xxxxxx' # محفظة بايير (تحويل يدوي)
}

# ==================== 2. الاتصال بقاعدة البيانات ====================
# دالة لفتح اتصال جديد في كل عملية لضمان عدم تعليق البوت
def get_db_connection():
    return psycopg2.connect(SUPABASE_URL)

# إنشاء الجداول تلقائياً عند بدء التشغيل
def init_db():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # جدول المستخدمين
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                chat_id BIGINT PRIMARY KEY,
                username TEXT,
                balance FLOAT DEFAULT 0,
                joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        cur.close()
        conn.close()
        print("✅ Database Tables Ready")
    except Exception as e:
        print(f"❌ Database Error: {e}")

init_db() # استدعاء الدالة عند التشغيل

# ==================== 3. دوال مساعدة (Dababase Helpers) ====================
def add_user(chat_id, username):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO users (chat_id, username) VALUES (%s, %s)", (chat_id, username))
        conn.commit()
        return True # مستخدم جديد
    except:
        return False # مستخدم موجود مسبقاً
    finally:
        conn.close()

def update_balance(chat_id, amount):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET balance = balance + %s WHERE chat_id = %s", (amount, chat_id))
    conn.commit()
    conn.close()

def get_balance(chat_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT balance FROM users WHERE chat_id = %s", (chat_id,))
    res = cur.fetchone()
    conn.close()
    return res[0] if res else 0.0

# ==================== 4. إعدادات البوت والسيرفر ====================
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# تخزين مؤقت للكابتشا (في الرام)
user_captchas = {}

# --- نظام الكابتشا الهجين ---
def gen_captcha():
    if random.choice(['math', 'text']) == 'math':
        a, b = random.randint(1, 9), random.randint(1, 9)
        return {'q': f"{a} + {b} = ?", 'a': str(a+b)}
    else:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
        return {'q': f"اكتب الكود: {code}", 'a': code}

# --- نقطة البداية /start ---
@bot.message_handler(commands=['start'])
def start_msg(message):
    cid = message.chat.id
    username = message.from_user.username
    
    # تسجيل المستخدم في الداتابيز
    is_new = add_user(cid, username)
    if is_new:
        bot.send_message(ADMIN_ID, f"🔔 مستخدم جديد: @{username} (`{cid}`)")

    # إرسال الكابتشا
    captcha = gen_captcha()
    user_captchas[cid] = captcha['a']
    bot.send_message(cid, f"🔒 **التحقق الأمني**\n{captcha['q']}", parse_mode="Markdown")

# --- التحقق من الكابتشا والاشتراك ---
@bot.message_handler(func=lambda m: m.chat.id in user_captchas)
def verify_captcha(message):
    cid = message.chat.id
    text = message.text
    
    if text.strip() == user_captchas[cid]:
        del user_captchas[cid] # مسح الكابتشا
        check_subscription_and_proceed(cid)
    else:
        bot.send_message(cid, "❌ كود خطأ، حاول مرة أخرى.")

def check_subscription_and_proceed(cid):
    # هنا يمكنك إضافة كود التحقق من الاشتراك في القناة (اختياري)
    # حالياً سنوجهه للقائمة الرئيسية مباشرة
    main_menu(cid)

# --- القائمة الرئيسية ---
def main_menu(cid):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🛒 شراء رقم", callback_data="buy"),
        types.InlineKeyboardButton("💰 شحن رصيد", callback_data="deposit"),
        types.InlineKeyboardButton("👤 حسابي", callback_data="profile")
    )
    if cid == ADMIN_ID:
        markup.add(types.InlineKeyboardButton("👮 لوحة الأدمن", callback_data="admin_panel"))
        
    bot.send_message(cid, "👋 أهلاً بك في بوت الأرقام.\nاختر ما تريد:", reply_markup=markup)

# ==================== 5. نظام الدفع (Payments) ====================

@bot.callback_query_handler(func=lambda call: call.data == "deposit")
def deposit_menu(call):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("USDT (تلقائي) ⚡", callback_data="pay_auto_usdt"),
        types.InlineKeyboardButton("فودافون كاش (يدوي) 🇪🇬", callback_data="pay_manual_voda"),
        types.InlineKeyboardButton("STC Pay (يدوي) 🇸🇦", callback_data="pay_manual_stc"),
        types.InlineKeyboardButton("Payeer (يدوي) 🅿️", callback_data="pay_manual_payeer")
    )
    bot.edit_message_text("💳 اختر وسيلة الدفع:", call.message.chat.id, call.message.message_id, reply_markup=markup)

# معالجة الدفع اليدوي
@bot.callback_query_handler(func=lambda call: "pay_manual" in call.data)
def manual_pay_info(call):
    method = call.data.split('_')[2]
    wallet = WALLETS.get(method, WALLETS['vodafone'])
    if method == 'payeer': wallet = WALLETS['payeer_manual']
    
    msg = f"💰 **الدفع عبر {method.upper()}**\n\n"
    msg += f"1️⃣ حول المبلغ إلى: `{wallet}`\n"
    msg += f"2️⃣ أرسل صورة التحويل (Screenshot) هنا في الشات."
    bot.send_message(call.message.chat.id, msg, parse_mode="Markdown")

# استلام الصور (للإيداع اليدوي)
@bot.message_handler(content_types=['photo'])
def handle_receipt(message):
    cid = message.chat.id
    # إرسال الصورة للأدمن للمراجعة
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ قبول 1$", callback_data=f"add_{cid}_1"),
        types.InlineKeyboardButton("✅ قبول 5$", callback_data=f"add_{cid}_5"),
        types.InlineKeyboardButton("✅ قبول 10$", callback_data=f"add_{cid}_10"),
        types.InlineKeyboardButton("❌ رفض", callback_data=f"rej_{cid}")
    )
    bot.forward_message(ADMIN_ID, cid, message.message_id)
    bot.send_message(ADMIN_ID, f"📩 إيصال جديد من: `{cid}`\nراجع الصورة واختر الإجراء:", reply_markup=markup)
    bot.reply_to(message, "✅ تم استلام الإيصال، سيتم مراجعته وإضافة الرصيد قريباً.")

# تنفيذ أمر الأدمن (إضافة الرصيد أو الرفض)
@bot.callback_query_handler(func=lambda call: call.data.startswith('add_') or call.data.startswith('rej_'))
def admin_action(call):
    if call.from_user.id != ADMIN_ID: return
    action, user_id, amount = call.data.split('_')
    
    if action == 'add':
        update_balance(user_id, float(amount))
        bot.send_message(user_id, f"🎉 تم شحن رصيدك بنجاح بمبلغ {amount}$")
        bot.edit_message_text(f"✅ تم إضافة {amount}$ للمستخدم.", call.message.chat.id, call.message.message_id)
    else:
        bot.send_message(user_id, "❌ نأسف، تم رفض عملية الشحن. تأكد من الإيصال.")
        bot.edit_message_text("❌ تم رفض الطلب.", call.message.chat.id, call.message.message_id)

# ==================== 6. الشراء من API (الروسي) ====================
@bot.callback_query_handler(func=lambda call: call.data == "buy")
def buy_menu_func(call):
    # قائمة الخدمات (مثال)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Whatsapp Egypt (0.5$)", callback_data="buy_eg_wa"))
    bot.edit_message_text("اختر الخدمة:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "buy_eg_wa")
def execute_buy(call):
    cid = call.message.chat.id
    price = 0.5
    balance = get_balance(cid)
    
    if balance >= price:
        # خصم الرصيد أولاً
        update_balance(cid, -price)
        bot.send_message(cid, "🔄 جاري طلب الرقم من السيرفر...")
        
        # طلب من API
        headers = {'Authorization': 'Bearer ' + API_KEY, 'Accept': 'application/json'}
        try:
            # رابط 5sim كمثال (تأكد من اختيار الدولة والمنتج الصحيح)
            r = requests.get('https://5sim.net/v1/user/buy/activation/egypt/any/whatsapp', headers=headers)
            if r.status_code == 200:
                data = r.json()
                phone = data['phone']
                oid = data['id']
                bot.send_message(cid, f"✅ تم شراء الرقم بنجاح!\n📱: `{phone}`\nجاري انتظار الكود...", parse_mode="Markdown")
                # تشغيل الانتظار في الخلفية
                threading.Thread(target=check_sms, args=(cid, oid, headers)).start()
            else:
                update_balance(cid, price) # إرجاع الرصيد
                bot.send_message(cid, "⚠️ لا توجد أرقام متاحة حالياً، تم إرجاع الرصيد.")
        except Exception as e:
            update_balance(cid, price)
            bot.send_message(cid, f"خطأ في الاتصال: {e}")
    else:
        bot.send_message(cid, "❌ رصيدك غير كافي!")

def check_sms(cid, oid, headers):
    # محاولة جلب الكود لمدة دقيقتين
    for _ in range(24):
        time.sleep(5)
        try:
            r = requests.get(f'https://5sim.net/v1/user/check/{oid}', headers=headers)
            if r.status_code == 200:
                data = r.json()
                if data['status'] == 'RECEIVED':
                    code = data['sms'][0]['code']
                    bot.send_message(cid, f"📬 **وصل الكود!**\nCode: `{code}`", parse_mode="Markdown")
                    return
        except: pass
    
    bot.send_message(cid, "⏰ انتهى الوقت ولم يصل الكود. (يمكنك إلغاء الطلب واسترداد الرصيد يدوياً)")

# ==================== 7. تشغيل السيرفر والبوت ====================
@app.route('/')
def home():
    return "Bot is Running!"

def run_flask():
    # تشغيل سيرفر Flask لاستقبال الـ Webhooks
    app.run(host='0.0.0.0', port=5000)

if __name__ == "__main__":
    # تشغيل السيرفر في خيط منفصل
    t = threading.Thread(target=run_flask)
    t.start()
    
    # تشغيل البوت
    print("🤖 Bot started...")
    bot.infinity_polling(skip_pending=True)
