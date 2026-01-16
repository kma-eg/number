import telebot
from telebot import types
import requests
import psycopg2
import threading
import time
import random
import string
from flask import Flask, request, jsonify
from datetime import datetime

# ==================== ⚙️ إعدادات البوت والمفاتيح ⚙️ ====================
BOT_TOKEN = "6058936352:AAFuc7sf304xcmRWkniHRIZNpV4oNglfTIk" # توكن البوت
ADMIN_ID =6318333901 # الأيدي الخاص بك
CHANNEL_USER = "@kma_c" # قناة الاشتراك الإجباري
API_5SIM = "eyJhbGciOiJSUzUxMiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE4MDAxMjk3MzIsImlhdCI6MTc2ODU5MzczMiwicmF5IjoiYjI1MDRmNzVlYzI2MTAzZmQ4MDVhNmZjNTU1OTNlMDgiLCJzdWIiOjM3NDE4NTl9.fChnApox83L626jS4ZajT1Sg0fEiYdqySUDJ9-AWEsNiHDJWv2hRaCk_MAtYJCa3nu1uo4HdTz-y4ug1EsAUbziQJncz5Q91Fh9ADt7LLgm8UyKzP4uFif5XY9rHpQ5zGiA8MN8HNIhtf-bHsJZxBNU0S8GT4VseKb1bbl3PEYB3H6IDSbH3csom0rWzYoySt9RPfOTuqJQlFk5T7TE_h4NjZhFvpt7_chzF2HQoLy0Js1esOyALhyX7D0xjCVet7df3CySYNn70sdJsPYRyEepetjsbq5lzHWg4zE4MOqB7_Q7iFPhQE_-t1v3J1yR1ARq9kMnzgH00I7cKcU0_Fg" # مفتاح الموقع الروسي
PAYEER_SECRET = "YOUR_PAYEER_SECRET" # مفتاح التاجر في بايير
SUPABASE_URL = "postgres://user:pass@db.supabase.co:5432/postgres" # رابط الداتابيز

# إعدادات المحافظ اليدوية
WALLETS = {
    'vodafone': '01020755609',
    'stc': '05XXXXXXXX'
}

# ==================== 🗄️ الاتصال بقاعدة البيانات 🗄️ ====================
conn = psycopg2.connect(SUPABASE_URL)
cur = conn.cursor()

# إنشاء الجداول لو مش موجودة (أول مرة فقط)
def init_db():
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            chat_id BIGINT PRIMARY KEY,
            username TEXT,
            balance FLOAT DEFAULT 0,
            joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_blocked BOOLEAN DEFAULT FALSE
        );
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            chat_id BIGINT,
            phone TEXT,
            status TEXT,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()

init_db()

# ==================== 🛠️ دوال مساعدة (DB & API) 🛠️ ====================
def get_user(chat_id):
    cur.execute("SELECT * FROM users WHERE chat_id = %s", (chat_id,))
    return cur.fetchone()

def add_user(chat_id, username):
    try:
        cur.execute("INSERT INTO users (chat_id, username) VALUES (%s, %s)", (chat_id, username))
        conn.commit()
        return True # مستخدم جديد
    except:
        conn.rollback()
        return False # مستخدم موجود

def update_balance(chat_id, amount):
    cur.execute("UPDATE users SET balance = balance + %s WHERE chat_id = %s", (amount, chat_id))
    conn.commit()

def check_sub(chat_id):
    try:
        member = bot.get_chat_member(CHANNEL_USER, chat_id)
        if member.status in ['creator', 'administrator', 'member']: return True
    except: pass
    return False

# ==================== 🤖 بدء البوت والسيرفر 🤖 ====================
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# --- 1. نظام الكابتشا (Hybrid) ---
user_captchas = {}

def gen_captcha():
    if random.choice(['math', 'text']) == 'math':
        a, b = random.randint(1, 9), random.randint(1, 9)
        return {'q': f"{a} + {b} = ?", 'a': str(a+b), 'type': 'math'}
    else:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
        return {'q': f"اكتب الكود: {code}", 'a': code, 'type': 'text'}

# --- 2. نقطة البداية /start ---
@bot.message_handler(commands=['start'])
def start_msg(message):
    cid = message.chat.id
    name = message.from_user.first_name
    username = message.from_user.username
    
    # تسجيل المستخدم وإشعار الأدمن
    is_new = add_user(cid, username)
    
    if is_new:
        # إشعار دخول جديد
        msg = f"🔔 **مستخدم جديد!**\nالاسم: {name}\nاليوزر: @{username}\nالآيدي: `{cid}`"
        bot.send_message(ADMIN_ID, msg, parse_mode="Markdown")
    else:
        # المستخدم موجود (عاد للبوت)
        # هنا يمكننا استنتاج أنه كان محظوراً أو توقف عن الاستخدام
        bot.send_message(ADMIN_ID, f"♻️ **مستخدم عاد للبوت:** @{username} ({cid})")

    # بدء الكابتشا
    captcha = gen_captcha()
    user_captchas[cid] = captcha['a']
    bot.send_message(cid, f"🔒 **التحقق الأمني**\n{captcha['q']}")

# --- 3. التحقق من الكابتشا والاشتراك ---
@bot.message_handler(func=lambda m: m.chat.id in user_captchas)
def verify_captcha(message):
    cid = message.chat.id
    text = message.text
    
    if text.strip() == user_captchas[cid]:
        del user_captchas[cid] # مسح الكابتشا
        
        # فحص الاشتراك الإجباري
        if not check_sub(cid):
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("اشتركت ✅", callback_data="check_sub"))
            bot.send_message(cid, f"⚠️ يجب الاشتراك في القناة أولاً: {CHANNEL_USER}", reply_markup=markup)
        else:
            main_menu(cid)
    else:
        bot.send_message(cid, "❌ كود خطأ، حاول مرة أخرى.")

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def recheck_sub(call):
    if check_sub(call.message.chat.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        main_menu(call.message.chat.id)
    else:
        bot.answer_callback_query(call.id, "❌ لم تشترك بعد!", show_alert=True)

# --- 4. القائمة الرئيسية ---
def main_menu(cid):
    markup = types.InlineKeyboardMarkup(row_width=2)
    b1 = types.InlineKeyboardButton("🛒 شراء رقم", callback_data="buy")
    b2 = types.InlineKeyboardButton("💰 شحن رصيد", callback_data="deposit")
    b3 = types.InlineKeyboardButton("👤 حسابي", callback_data="profile")
    markup.add(b1, b2, b3)
    
    # لو أدمن يظهر له زر الإدارة
    if cid == ADMIN_ID:
        markup.add(types.InlineKeyboardButton("👮 لوحة الأدمن", callback_data="admin_panel"))
        
    bot.send_message(cid, "👋 أهلاً بك في بوت الأرقام.\nاختر ما تريد:", reply_markup=markup)

# ==================== 💰 نظام الدفع (Auto + Manual) 💰 ====================

@bot.callback_query_handler(func=lambda call: call.data == "deposit")
def deposit_methods(call):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("Payeer (تلقائي) 🅿️", callback_data="pay_auto_payeer"),
        types.InlineKeyboardButton("USDT (تلقائي) ⚡", callback_data="pay_auto_usdt"),
        types.InlineKeyboardButton("فودافون كاش 🇪🇬", callback_data="pay_manual_voda"),
        types.InlineKeyboardButton("STC Pay 🇸🇦", callback_data="pay_manual_stc")
    )
    bot.edit_message_text("💳 اختر وسيلة الدفع:", call.message.chat.id, call.message.message_id, reply_markup=markup)

# معالجة الدفع اليدوي (Vodafone / STC)
@bot.callback_query_handler(func=lambda call: "pay_manual" in call.data)
def manual_pay_info(call):
    wallet = WALLETS['vodafone'] if 'voda' in call.data else WALLETS['stc']
    msg = f"💰 حول المبلغ إلى: `{wallet}`\n📸 ثم أرسل صورة التحويل هنا."
    bot.send_message(call.message.chat.id, msg, parse_mode="Markdown")

# استقبال صور التحويل (لليدوي)
@bot.message_handler(content_types=['photo'])
def handle_receipt(message):
    cid = message.chat.id
    # إرسال للأدمن
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ قبول 1$", callback_data=f"add_{cid}_1"),
               types.InlineKeyboardButton("✅ قبول 5$", callback_data=f"add_{cid}_5"),
               types.InlineKeyboardButton("❌ رفض", callback_data=f"rej_{cid}"))
    
    bot.forward_message(ADMIN_ID, cid, message.message_id)
    bot.send_message(ADMIN_ID, f"إيصال جديد من: {cid}", reply_markup=markup)
    bot.reply_to(message, "تم الاستلام وجاري المراجعة...")

# --- Webhook لباير (تلقائي) ---
@app.route('/payeer_callback', methods=['POST'])
def payeer_webhook():
    # هذا الرابط تضعه في إعدادات Payeer Merchant
    if request.form.get('m_status') == 'success':
        # تحقق من التوقيع (Signature) هنا للأمان
        user_id = request.form.get('m_orderid').split('_')[0] # بنكون باعتين الآيدي في رقم الطلب
        amount = request.form.get('m_amount')
        
        update_balance(user_id, float(amount))
        bot.send_message(user_id, f"✅ تم شحن رصيدك تلقائياً بـ {amount}$")
        return "OK"
    return "Error"

# ==================== 🛒 الشراء من الموقع الروسي 🛒 ====================
@bot.callback_query_handler(func=23345678lambda call: call.data == "buy")
def buy_menu(call):
    # مثال لدولة واحدة للتبسيط (مصر)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Whatsapp 🇪🇬 (0.5$)", callback_data="buy_eg_wa"))
    bot.edit_message_text("اختر الخدمة:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "buy_eg_wa")
def execute_buy(call):
    cid = call.message.chat.id
    user = get_user(cid)
    price = 0.5 # السعر اللي أنت بتبيعه بيه
    
    if user[2] >= price: # user[2] هو الرصيد
        # 1. طلب الرقم من 5sim
        headers = {'Authorization': 'Bearer ' + API_5SIM, 'Accept': 'application/json'}
        # رابط شراء واتساب مصري
        resp = requests.get('https://5sim.net/v1/user/buy/activation/egypt/any/whatsapp', headers=headers)
        
        if resp.status_code == 200:
            data = resp.json()
            phone = data['phone']
            order_id = data['id']
            
            # خصم الرصيد
            update_balance(cid, -price)
            
            bot.send_message(cid, f"✅ تم الشراء!\nرقمك: `{phone}`\nجاري انتظار الكود...", parse_mode="Markdown")
            
            # تشغيل خيط (Thread) لانتظار الكود عشان البوت ما يعلقش
            threading.Thread(target=check_sms_code, args=(cid, order_id, headers)).start()
        else:
            bot.send_message(cid, "⚠️ لا توجد أرقام متاحة حالياً، حاول لاحقاً.")
    else:
        bot.send_message(cid, "❌ رصيدك غير كافي!")

def check_sms_code(cid, order_id, headers):
    for _ in range(20): # يحاول 20 مرة (لمدة دقيقة ونصف تقريباً)
        time.sleep(5)
        resp = requests.get(f'https://5sim.net/v1/user/check/{order_id}', headers=headers)
        data = resp.json()
        if data['status'] == 'RECEIVED':
            code = data['sms'][0]['code']
            bot.send_message(cid, f"📬 الكود وصل!\nCode: `{code}`", parse_mode="Markdown")
            return
    bot.send_message(cid, "⏰ انتهى الوقت ولم يصل الكود. تم إلغاء الطلب وإرجاع الرصيد.")
    # هنا كود إرجاع الرصيد للمستخدم

# ==================== 👮 لوحة التحكم (الأدمن) 👮 ====================
@bot.callback_query_handler(func=lambda call: call.data == "admin_panel" and call.from_user.id == ADMIN_ID)
def admin_dash(call):
    cur.execute("SELECT COUNT(*) FROM users")
    count = cur.fetchone()[0]
    
    msg = f"📊 **إحصائيات البوت**\nعدد المستخدمين: {count}\n"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📢 إذاعة رسالة", callback_data="broadcast"))
    bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

# إذاعة الرسائل
user_broadcasting = {}
@bot.callback_query_handler(func=lambda call: call.data == "broadcast")
def ask_broadcast(call):
    user_broadcasting[call.from_user.id] = True
    bot.send_message(call.message.chat.id, "أرسل الرسالة التي تريد إذاعتها للجميع:")

@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and user_broadcasting.get(m.from_user.id))
def send_broadcast(message):
    cur.execute("SELECT chat_id FROM users")
    users = cur.fetchall()
    count = 0
    for user in users:
        try:
            bot.copy_message(user[0], message.chat.id, message.message_id)
            count += 1
        except: pass # المستخدم حظر البوت
    
    bot.reply_to(message, f"✅ تمت الإذاعة لـ {count} مستخدم.")
    user_broadcasting[ADMIN_ID] = False

# ==================== 🚀 التشغيل 🚀 ====================
def run_flask():
    app.run(host='0.0.0.0', port=5000)

def run_bot():
    bot.infinity_polling(skip_pending=True)

if __name__ == "__main__":
    t1 = threading.Thread(target=run_flask)
    t2 = threading.Thread(target=run_bot)
    t1.start()
    t2.start()
