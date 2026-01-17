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

# ==================== 1. إعدادات البيئة ====================
BOT_TOKEN = os.environ.get('TOKEN')
ADMIN_ID = int(os.environ.get('ADMIN_ID'))
API_KEY = os.environ.get('API_KEY')
SUPABASE_URL = os.environ.get('SUPABASE_URL')

# إعدادات القناة (مهم جداً)
CHANNEL_ID = -1003316907453  # الآيدي الرقمي للقناة
CHANNEL_LINK = "https://t.me/kma_c" # رابط القناة

# إعدادات الأرباح
PROFIT_MARGIN = 1.30  # نسبة الربح (30%)
REFERRAL_REWARD = 0.02 # مكافأة الدعوة

# ==================== 2. بيانات المحافظ (تظهر للعميل) ====================
WALLETS = {
    'vodafone': '01020755609',
    'vodafone2': '01005016893',
    'payeer': 'P1090134',
    'usdt': 'TJuoPbUQepNx8SyUKNnxCU3ti4FeKZsZQx' # (TRC20)
}

# ==================== 3. قوائم الدول والخدمات ====================
COUNTRIES = {
    'egypt': '🇪🇬 مصر', 'saudiarabia': '🇸🇦 السعودية', 'usa': '🇺🇸 أمريكا',
    'russia': '🇷🇺 روسيا', 'china': '🇨🇳 الصين', 'morocco': '🇲🇦 المغرب',
    'algeria': '🇩🇿 الجزائر', 'iraq': '🇮🇶 العراق', 'unitedkingdom': '🇬🇧 بريطانيا',
    'brazil': '🇧🇷 البرازيل', 'germany': '🇩🇪 ألمانيا', 'france': '🇫🇷 فرنسا',
    'yemen': '🇾🇪 اليمن'
}

SERVICES = {
    'whatsapp': '💚 WhatsApp', 'telegram': '💙 Telegram', 'facebook': '💙 Facebook',
    'instagram': '🩷 Instagram', 'tiktok': '🖤 TikTok', 'google': '❤️ Gmail',
    'twitter': '🖤 X (Twitter)', 'snapchat': '💛 Snapchat'
}

# ==================== 4. الاتصال بقاعدة البيانات ====================
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
        cur.close()
        conn.close()
        print("✅ Database Connected & Ready")
    except Exception as e:
        print(f"❌ Database Error: {e}")

init_db()

# دوال التعامل مع القاعدة
def add_user(chat_id, username, referrer_id=None):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO users (chat_id, username, referrer_id) VALUES (%s, %s, %s)", (chat_id, username, referrer_id))
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()

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

# ==================== 5. تشغيل البوت ====================
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
user_captchas = {}
user_selections = {} # لتخزين اختيارات الشراء المؤقتة

# --- الكابتشا ---
def gen_captcha():
    a, b = random.randint(1, 9), random.randint(1, 9)
    return {'q': f"{a} + {b} = ?", 'a': str(a+b)}

# --- البداية /start ---
@bot.message_handler(commands=['start'])
def start_msg(message):
    cid = message.chat.id
    username = message.from_user.username
    
    # التحقق من وجود كود دعوة (Referral)
    args = message.text.split()
    referrer_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else 0
    if referrer_id == cid: referrer_id = 0 # منع دعوة النفس
    
    add_user(cid, username, referrer_id)
    
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
        del user_captchas[cid]
        check_sub_and_open_menu(cid)
    else:
        bot.send_message(cid, "❌ إجابة خاطئة، حاول مرة أخرى.")

def check_sub_and_open_menu(cid):
    try:
        # التحقق من الاشتراك باستخدام CHANNEL_ID الصحيح
        stat = bot.get_chat_member(CHANNEL_ID, cid).status
        if stat not in ['member', 'administrator', 'creator']:
            raise Exception("Not Subscribed")
            
        # إذا مشترك، افتح القائمة
        main_menu(cid)
        
    except Exception as e:
        # إذا غير مشترك
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 اشترك في القناة", url=CHANNEL_LINK))
        markup.add(types.InlineKeyboardButton("🔄 تحقق من الاشتراك", callback_data="check_sub"))
        bot.send_message(cid, "⚠️ **يجب الاشتراك في القناة أولاً لاستخدام البوت!**", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_sub_callback(call):
    check_sub_and_open_menu(call.message.chat.id)

# ==================== 6. القوائم والتحكم (الجزء المفقود سابقاً) ====================

# القائمة الرئيسية
def main_menu(cid):
    user = get_user(cid)
    balance = user[2] if user else 0.0
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🛒 شراء أرقام", callback_data="buy"),
        types.InlineKeyboardButton("💰 شحن رصيد", callback_data="deposit"),
        types.InlineKeyboardButton("👤 حسابي", callback_data="profile"),
        types.InlineKeyboardButton("🎁 دعوة أصدقاء", callback_data="invite")
    )
    if cid == ADMIN_ID:
        markup.add(types.InlineKeyboardButton("👮 لوحة الأدمن", callback_data="admin_panel"))
        
    bot.send_message(cid, f"👋 أهلاً بك! رصيدك الحالي: `{balance:.2f}$`\nاختر من القائمة:", reply_markup=markup, parse_mode="Markdown")

# --- زر شحن الرصيد ---
@bot.callback_query_handler(func=lambda call: call.data == "deposit")
def deposit_menu(call):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("Vodafone Cash 🇪🇬", callback_data="pay_info:vodafone"),
        types.InlineKeyboardButton("USDT (TRC20) ₮", callback_data="pay_info:usdt"),
        types.InlineKeyboardButton("Payeer 🅿️", callback_data="pay_info:payeer"),
        types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")
    )
    bot.edit_message_text("💳 **اختر وسيلة الدفع:**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_info:"))
def pay_info_msg(call):
    method = call.data.split(":")[1]
    wallet = WALLETS.get(method, "غير متوفر")
    
    msg = f"💰 **الدفع عبر {method.upper()}**\n\n"
    msg += f"1️⃣ حول المبلغ إلى: `{wallet}`\n"
    if method == 'vodafone':
        msg += f"أو الرقم البديل: `{WALLETS['vodafone2']}`\n"
    msg += f"2️⃣ خذ سكرين شوت للتحويل.\n"
    msg += f"3️⃣ أرسل الصورة هنا في الشات فوراً."
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="deposit"))
    bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

# --- زر حسابي ---
@bot.callback_query_handler(func=lambda call: call.data == "profile")
def profile_show(call):
    cid = call.message.chat.id
    user = get_user(cid)
    msg = f"👤 **ملفك الشخصي**\n🆔 ID: `{cid}`\n💰 الرصيد: `{user[2]}$`"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu"))
    bot.edit_message_text(msg, cid, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

# --- زر الدعوة ---
@bot.callback_query_handler(func=lambda call: call.data == "invite")
def invite_link(call):
    cid = call.message.chat.id
    bot_user = bot.get_me().username
    link = f"https://t.me/{bot_user}?start={cid}"
    msg = f"🎁 **اربح {REFERRAL_REWARD}$ مجاناً!**\nشارك الرابط مع أصدقائك:\n`{link}`"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu"))
    bot.edit_message_text(msg, cid, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

# --- استلام صور التحويل (للأدمن) ---
@bot.message_handler(content_types=['photo'])
def handle_receipt(message):
    cid = message.chat.id
    # إرسال الصورة للأدمن
    bot.forward_message(ADMIN_ID, cid, message.message_id)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ 1$", callback_data=f"add:{cid}:1"),
        types.InlineKeyboardButton("✅ 5$", callback_data=f"add:{cid}:5"),
        types.InlineKeyboardButton("✅ 10$", callback_data=f"add:{cid}:10"),
        types.InlineKeyboardButton("❌ رفض", callback_data=f"rej:{cid}")
    )
    bot.send_message(ADMIN_ID, f"📩 إيصال جديد من `{cid}`\nاختر المبلغ لإضافته:", reply_markup=markup)
    bot.reply_to(message, "✅ تم استلام الإيصال، سيتم مراجعته وإضافة الرصيد قريباً.")

# --- معالجة قبول/رفض الأدمن ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("add:") or call.data.startswith("rej:"))
def admin_process_payment(call):
    if call.from_user.id != ADMIN_ID: return
    
    action, uid, val = call.data.split(":")[0], call.data.split(":")[1], 0
    if len(call.data.split(":")) > 2: val = float(call.data.split(":")[2])
    
    if action == "add":
        update_balance(uid, val)
        bot.send_message(uid, f"🎉 تم شحن رصيدك بنجاح: {val}$")
        bot.edit_message_text(f"✅ تم إضافة {val}$ للمستخدم {uid}", call.message.chat.id, call.message.message_id)
    else:
        bot.send_message(uid, "❌ تم رفض عملية الشحن. تأكد من الإيصال.")
        bot.edit_message_text(f"❌ تم رفض الطلب للمستخدم {uid}", call.message.chat.id, call.message.message_id)

# ==================== 7. نظام الشراء (العالمي) ====================
@bot.callback_query_handler(func=lambda call: call.data == "buy")
def buy_countries(call):
    markup = types.InlineKeyboardMarkup(row_width=3)
    btns = [types.InlineKeyboardButton(n, callback_data=f"cnt:{k}") for k, n in COUNTRIES.items()]
    markup.add(*btns)
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu"))
    bot.edit_message_text("🌍 اختر الدولة:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("cnt:"))
def buy_services(call):
    country = call.data.split(":")[1]
    user_selections[call.from_user.id] = country
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btns = [types.InlineKeyboardButton(n, callback_data=f"srv:{k}") for k, n in SERVICES.items()]
    markup.add(*btns)
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="buy"))
    bot.edit_message_text(f"تم اختيار {COUNTRIES.get(country)}\n👇 اختر الخدمة:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("srv:"))
def execute_buy(call):
    cid = call.message.chat.id
    service = call.data.split(":")[1]
    country = user_selections.get(cid)
    
    if not country:
        bot.answer_callback_query(call.id, "حدث خطأ، ابدأ من جديد")
        return

    # سعر تقريبي (يمكنك ربطه بالـ API للحصول على السعر الدقيق)
    cost = 0.5 
    user_bal = get_user(cid)[2]
    
    if user_bal < cost:
        bot.answer_callback_query(call.id, "❌ رصيدك غير كافي!", show_alert=True)
        return
        
    # خصم الرصيد مبدئياً
    update_balance(cid, -cost)
    bot.send_message(cid, "🔄 جاري طلب الرقم...")
    
    try:
        headers = {'Authorization': 'Bearer ' + API_KEY, 'Accept': 'application/json'}
        url = f'https://5sim.net/v1/user/buy/activation/{country}/any/{service}'
        r = requests.get(url, headers=headers)
        
        if r.status_code == 200:
            data = r.json()
            if 'phone' in data:
                phone = data['phone']
                oid = data['id']
                bot.send_message(cid, f"✅ **تم شراء الرقم!**\n📱 `{phone}`\n⏳ انتظر الكود...", parse_mode="Markdown")
                threading.Thread(target=check_sms, args=(cid, oid, headers)).start()
            else:
                update_balance(cid, cost)
                bot.send_message(cid, "⚠️ لا توجد أرقام متاحة، تم استرداد الرصيد.")
        else:
            update_balance(cid, cost)
            bot.send_message(cid, f"❌ خطأ من المصدر: {r.text}")
            
    except Exception as e:
        update_balance(cid, cost)
        bot.send_message(cid, f"Error: {e}")

def check_sms(cid, oid, headers):
    for _ in range(30): # محاولة لمدة دقيقتين ونصف
        time.sleep(5)
        try:
            r = requests.get(f'https://5sim.net/v1/user/check/{oid}', headers=headers)
            data = r.json()
            if data['status'] == 'RECEIVED':
                code = data['sms'][0]['code']
                bot.send_message(cid, f"📬 **وصل الكود!**\nCode: `{code}`", parse_mode="Markdown")
                return
        except: pass
    bot.send_message(cid, "⏰ انتهى الوقت ولم يصل الكود.", parse_mode="Markdown")

# ==================== 8. تشغيل السيرفر ====================
@app.route('/')
def home():
    return "Bot is Running V3.0!"

def run_flask():
    app.run(host='0.0.0.0', port=5000)

if __name__ == "__main__":
    t = threading.Thread(target=run_flask)
    t.start()
    
    print("🤖 Bot started...")
    bot.infinity_polling(skip_pending=True)
