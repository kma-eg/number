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
# تأكد أن هذه المتغيرات موجودة في Environment Variables في Render
BOT_TOKEN = os.environ.get('TOKEN')
ADMIN_ID = int(os.environ.get('ADMIN_ID'))
API_KEY = os.environ.get('API_KEY') # مفتاح 5sim
SUPABASE_URL = os.environ.get('SUPABASE_URL') # رابط قاعدة البيانات

# إعدادات القناة (التي سببت المشاكل سابقاً - تم تثبيتها الآن)
CHANNEL_ID = -1003316907453  # الآيدي الرقمي للقناة
CHANNEL_LINK = "https://t.me/kma_c" # رابط القناة للأزرار

# إعدادات الأرباح
PROFIT_MARGIN = 1.30 # نسبة الربح (30%)
REFERRAL_REWARD = 0.02 # مكافأة الدعوة بالدولار

# ==================== 2. إعدادات المحافظ (الجديدة) ====================
WALLETS = {
    'vodafone': '01020755609',      # رقمك الأساسي
    'vodafone2': '01005016893',     # رقم إضافي للتجربة (عدله براحتك)
    'usdt': 'TJuoPbUQepNx8SyUKNnxCU3ti4FeKZsZQx', # عنوان USDT تجريبي (TRC20)
    'payeer_manual': 'P1090134'     # محفظة بايير اليدوية
}

# ==================== 3. الاتصال بقاعدة البيانات ====================
def get_db_connection():
    # دالة لفتح اتصال جديد في كل مرة لضمان عدم انقطاع الشبكة
    return psycopg2.connect(SUPABASE_URL)

def init_db():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # إنشاء جدول المستخدمين إذا لم يكن موجوداً
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                chat_id BIGINT PRIMARY KEY,
                username TEXT,
                balance FLOAT DEFAULT 0,
                referrer_id BIGINT DEFAULT 0,
                joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        cur.close()
        conn.close()
        print("✅ Database Connected & Ready")
    except Exception as e:
        print(f"❌ Database Error: {e}")

init_db() # تشغيل عند البداية

# ==================== 4. دوال إدارة المستخدمين والرصيد ====================
def get_user(chat_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE chat_id = %s", (chat_id,))
        user = cur.fetchone()
        conn.close()
        return user
    except: return None

def add_user(chat_id, username, referrer_id=0):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO users (chat_id, username, referrer_id) VALUES (%s, %s, %s)", (chat_id, username, referrer_id))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def update_balance(chat_id, amount):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET balance = balance + %s WHERE chat_id = %s", (amount, chat_id))
    conn.commit()
    conn.close()

def get_balance(chat_id):
    user = get_user(chat_id)
    return user[2] if user else 0.0

# ==================== 5. تشغيل البوت ====================
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
user_captchas = {} # تخزين مؤقت للكابتشا

# --- دوال مساعدة ---
def gen_captcha():
    a, b = random.randint(1, 9), random.randint(1, 9)
    return {'q': f"{a} + {b} = ?", 'a': str(a+b)}

def check_sub(chat_id):
    # دالة التحقق من الاشتراك (باستخدام الآيدي لتجنب الأخطاء)
    try:
        member = bot.get_chat_member(CHANNEL_ID, chat_id)
        if member.status in ['creator', 'administrator', 'member']:
            return True
    except Exception as e:
        print(f"Sub Check Error: {e}") # طباعة الخطأ في اللوج للمراجعة
        return False # لو حصل خطأ نعتبره غير مشترك احتياطياً
    return False

# ==================== 6. بداية البوت (/start) ====================
@bot.message_handler(commands=['start'])
def start_msg(message):
    cid = message.chat.id
    username = message.from_user.username
    text_split = message.text.split()
    
    # جلب معرف الإحالة لو موجود (/start 12345)
    referrer_id = 0
    if len(text_split) > 1 and text_split[1].isdigit():
        ref_candidate = int(text_split[1])
        if ref_candidate != cid: # عشان ما يعملش دعوة لنفسه
            referrer_id = ref_candidate

    # تسجيل المستخدم
    is_new = add_user(cid, username, referrer_id)
    if is_new:
        bot.send_message(ADMIN_ID, f"🔔 **مستخدم جديد:** {username} (`{cid}`)", parse_mode="Markdown")
        # لو فيه إحالة، نعطي المكافأة للموكل
        if referrer_id != 0:
            update_balance(referrer_id, REFERRAL_REWARD)
            bot.send_message(referrer_id, f"🎉 قام شخص بالدخول عبر رابطك! تمت إضافة {REFERRAL_REWARD}$ لرصيدك.")

    # إرسال الكابتشا
    captcha = gen_captcha()
    user_captchas[cid] = captcha['a']
    bot.send_message(cid, f"🔒 **التحقق الأمني:**\n{captcha['q']}")

# --- التحقق من الكابتشا والاشتراك ---
@bot.message_handler(func=lambda m: m.chat.id in user_captchas)
def verify_captcha_func(message):
    cid = message.chat.id
    text = message.text
    
    if text.strip() == user_captchas[cid]:
        del user_captchas[cid]
        # بعد الكابتشا، نتحقق من الاشتراك
        check_sub_flow(cid)
    else:
        bot.send_message(cid, "❌ كود خطأ، حاول مرة أخرى.")

def check_sub_flow(cid):
    if check_sub(cid):
        main_menu(cid)
    else:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 اشترك في القناة", url=CHANNEL_LINK))
        markup.add(types.InlineKeyboardButton("🔄 تحقق من الاشتراك", callback_data="check_sub_btn"))
        bot.send_message(cid, "⚠️ **يجب الاشتراك في القناة أولاً لاستخدام البوت!**", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "check_sub_btn")
def recheck_sub(call):
    if check_sub(call.message.chat.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        main_menu(call.message.chat.id)
    else:
        bot.answer_callback_query(call.id, "❌ لم تشترك بعد!", show_alert=True)

# ==================== 7. القائمة الرئيسية ====================
def main_menu(cid):
    user = get_user(cid)
    balance = user[2] if user else 0.0
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🛒 شراء أرقام", callback_data="buy_numbers"),
        types.InlineKeyboardButton("💰 شحن رصيد", callback_data="deposit"),
        types.InlineKeyboardButton("👤 حسابي", callback_data="profile"),
        types.InlineKeyboardButton("🎁 دعوة أصدقاء", callback_data="referral")
    )
    if cid == ADMIN_ID:
        markup.add(types.InlineKeyboardButton("👮 لوحة الأدمن", callback_data="admin_panel"))
        
    msg = f"👋 **أهلاً بك في بوت الأرقام**\n💰 رصيدك الحالي: `{balance:.2f}$`\n👇 اختر من القائمة:"
    bot.send_message(cid, msg, reply_markup=markup, parse_mode="Markdown")

# ==================== 8. نظام الشراء (العالمي) ====================
COUNTRIES = {
    'egypt': '🇪🇬 مصر', 'saudiarabia': '🇸🇦 السعودية', 'usa': '🇺🇸 أمريكا',
    'russia': '🇷🇺 روسيا', 'china': '🇨🇳 الصين', 'morocco': '🇲🇦 المغرب'
}
SERVICES = {
    'whatsapp': '💚 WhatsApp', 'telegram': '💙 Telegram', 'facebook': '💙 Facebook',
    'instagram': '🩷 Instagram', 'google': '❤️ Gmail', 'tiktok': '🖤 TikTok'
}
user_selections = {}

@bot.callback_query_handler(func=lambda call: call.data == "buy_numbers")
def show_countries(call):
    markup = types.InlineKeyboardMarkup(row_width=3)
    btns = [types.InlineKeyboardButton(name, callback_data=f"ct:{code}") for code, name in COUNTRIES.items()]
    markup.add(*btns)
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu_back"))
    bot.edit_message_text("🌍 **اختر الدولة:**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("ct:"))
def show_services(call):
    country = call.data.split(":")[1]
    user_selections[call.from_user.id] = {'country': country}
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btns = [types.InlineKeyboardButton(name, callback_data=f"srv:{code}") for code, name in SERVICES.items()]
    markup.add(*btns)
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="buy_numbers"))
    bot.edit_message_text(f"تم اختيار: {COUNTRIES[country]}\n👇 **اختر الخدمة:**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("srv:"))
def execute_buy(call):
    cid = call.message.chat.id
    service = call.data.split(":")[1]
    selection = user_selections.get(call.from_user.id)
    if not selection: return
    country = selection['country']
    
    # سعر تقريبي (يمكنك ربطه بالـ API لجلب السعر الحقيقي)
    cost = 0.5 
    
    if get_balance(cid) >= cost:
        update_balance(cid, -cost)
        bot.send_message(cid, "🔄 جاري طلب الرقم...")
        
        # طلب من API
        headers = {'Authorization': 'Bearer ' + API_KEY, 'Accept': 'application/json'}
        try:
            url = f'https://5sim.net/v1/user/buy/activation/{country}/any/{service}'
            r = requests.get(url, headers=headers)
            if r.status_code == 200:
                data = r.json()
                if 'phone' in data:
                    phone = data['phone']
                    oid = data['id']
                    bot.send_message(cid, f"✅ **تم الشراء!**\n📱: `{phone}`\n⏳ انتظر الكود...", parse_mode="Markdown")
                    threading.Thread(target=check_sms, args=(cid, oid, headers)).start()
                else:
                    update_balance(cid, cost)
                    bot.send_message(cid, "⚠️ لا توجد أرقام متاحة، تم استرداد الرصيد.")
            else:
                update_balance(cid, cost)
                bot.send_message(cid, f"⚠️ خطأ من المصدر: {r.text}")
        except Exception as e:
            update_balance(cid, cost)
            bot.send_message(cid, f"خطأ: {e}")
    else:
        bot.answer_callback_query(call.id, "❌ رصيدك غير كافي!", show_alert=True)

def check_sms(cid, oid, headers):
    for _ in range(30): # محاولة لمدة دقيقتين ونصف
        time.sleep(5)
        try:
            r = requests.get(f'https://5sim.net/v1/user/check/{oid}', headers=headers)
            data = r.json()
            if data['status'] == 'RECEIVED':
        
