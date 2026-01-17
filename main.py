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
# تأكد من تطابق الأسماء في Render Environment Variables
BOT_TOKEN = os.environ.get('TOKEN')
ADMIN_ID = int(os.environ.get('ADMIN_ID')) 
API_KEY = os.environ.get('API_KEY') # مفتاح 5sim
SUPABASE_URL = os.environ.get('SUPABASE_URL') # رابط الداتابيز المعدل (%40)

# إعدادات القناة والربح
CHANNEL_ID = -1003316907453 
PROFIT_MARGIN = 1.30 # نسبة الربح 30%
REFERRAL_REWARD = 0.02 # مكافأة الإحالة (دولار)

# محافظ الدفع اليدوي
WALLETS = {
    'vodafone': '01020755609',
    'stc': '01005016893',
    'payeer_manual': 'P1090134'
}

# قوائم الدول والخدمات (السوق العالمي)
COUNTRIES = {
    'egypt': '🇪🇬 مصر', 'saudiarabia': '🇸🇦 السعودية', 'usa': '🇺🇸 أمريكا',
    'russia': '🇷🇺 روسيا', 'china': '🇨🇳 الصين', 'morocco': '🇲🇦 المغرب',
    'algeria': '🇩🇿 الجزائر', 'iraq': '🇮🇶 العراق', 'unitedkingdom': '🇬🇧 بريطانيا',
    'yemen': '🇾🇪 اليمن', 'brazil': '🇧🇷 البرازيل', 'france': '🇫🇷 فرنسا'
}

SERVICES = {
    'whatsapp': '💚 WhatsApp', 'telegram': '💙 Telegram', 'facebook': '💙 Facebook',
    'instagram': '🩷 Instagram', 'tiktok': '🖤 TikTok', 'google': '❤️ Gmail',
    'twitter': '🖤 X (Twitter)', 'snapchat': '💛 Snapchat'
}

# ==================== 2. الاتصال بقاعدة البيانات ====================
def get_db_connection():
    # نستخدم اتصال جديد لكل عملية لتجنب المشاكل
    return psycopg2.connect(SUPABASE_URL)

def init_db():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # جدول المستخدمين (مع عمود من دعاني referrer)
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
        conn.close()
        print("✅ Database Ready")
    except Exception as e:
        print(f"❌ Database Error: {e}")

init_db()

# ==================== 3. دوال إدارة المستخدمين ====================
def get_user(chat_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE chat_id = %s", (chat_id,))
    user = cur.fetchone()
    conn.close()
    return user

def add_user(chat_id, username, referrer_id=0):
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

def update_balance(chat_id, amount):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET balance = balance + %s WHERE chat_id = %s", (amount, chat_id))
    conn.commit()
    conn.close()

# ==================== 4. البوت والسيرفر ====================
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
user_captchas = {} # تخزين الكابتشا مؤقتاً
user_selections = {} # تخزين اختيارات الشراء مؤقتاً

# --- توليد كابتشا هجينة ---
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
    text = message.text
    
    # 1. فحص الإحالة (هل دخل عن طريق صديق؟)
    referrer_id = 0
    if len(text.split()) > 1:
        try:
            ref_candidate = int(text.split()[1])
            if ref_candidate != cid:
                referrer_id = ref_candidate
        except: pass

    # 2. تسجيل مبدئي (بدون مكافأة حتى يجتاز الكابتشا)
    is_new = add_user(cid, username, referrer_id)
    
    if is_new:
        bot.send_message(ADMIN_ID, f"🔔 مشترك جديد: @{username}")
    
    # 3. إرسال الكابتشا
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
        check_sub_and_reward(cid)
    else:
        bot.send_message(cid, "❌ كود خطأ، حاول مرة أخرى.")

def check_sub_and_reward(cid):
    # 1. التحقق من الاشتراك في القناة
    try:
def check_sub_and_reward(cid):
    # التحقق من الاشتراك في القناة
    try:
        # انتبه: هنا نستخدم CHANNEL_ID (حروف كبيرة) لتطابق المتغير اللي فوق
        stat = bot.get_chat_member(CHANNEL_ID, cid).status
        if stat not in ['member', 'administrator', 'creator']:
            raise Exception("Not Subscribed")

        # --- (نفس كود المكافأة القديم كما هو) ---
        user = get_user(cid)
        if user and user[3] != 0: 
            referrer = user[3]
            update_balance(referrer, REFERRAL_REWARD)
            bot.send_message(referrer, f"🎉 حصلت على {REFERRAL_REWARD}$ مكافأة دعوة!")
            # تصفير المرجع عشان ما ياخدش عليه تاني
            # (تعديل بسيط في الداتابيز مطلوب لو عايز تمنع التكرار، بس خليه كدة دلوقتي)

        main_menu(cid)

    except Exception as e:
        # هنا كان في خطأ لأن CHANNEL_USER اتمسحت، استبدلناها برابط القناة
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 اشترك في القناة", url="https://t.me/kma_c"))
        markup.add(types.InlineKeyboardButton("🔄 تحقق من الاشتراك", callback_data="check_sub_callback"))
        
        # لاحظ مسحنا {CHANNEL_USER} وحطينا نص عادي عشان ما يحصلش خطأ
        bot.send_message(cid, "⚠️ يجب الاشتراك في القناة أولاً لاستخدام البوت!", reply_markup=markup, parse_mode="Markdown")
        
        # 2. مكافأة الإحالة (تتم مرة واحدة فقط عند التسجيل الناجح)
        user = get_user(cid)
        if user and user[3] != 0: # user[3] هو referrer_id
            # نتأكد أننا لم نكافئه سابقاً (يمكن إضافة عمود check للدقة)
            referrer = user[3]
            update_balance(referrer, REFERRAL_REWARD)
            bot.send_message(referrer, f"🎉 قام صديقك بالاشتراك! حصلت على {REFERRAL_REWARD}$")
            # نصفر المرجعي عشان ما ياخدش عليه تاني (اختياري)
            
        main_menu(cid)
        
    except:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("تحقق من الاشتراك 🔄", callback_data="check_sub"))
        # بدل المتغير المحذوف، حطينا الرابط مباشر
bot.send_message(cid, "⚠️ يجب الاشتراك في القناة أولاً: @kma_c", reply_markup=markup) 


@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def recheck(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)
    check_sub_and_reward(call.message.chat.id)

# ==================== 5. القائمة الرئيسية والسوق ====================
def main_menu(cid):
    user = get_user(cid)
    balance = round(user[2], 3)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🛒 شراء رقم", callback_data="buy"),
        types.InlineKeyboardButton("💰 شحن رصيد", callback_data="deposit"),
        types.InlineKeyboardButton("👤 حسابي", callback_data="profile"),
        types.InlineKeyboardButton("🎁 اربح مجاناً", callback_data="referral")
    )
    if cid == ADMIN_ID:
        markup.add(types.InlineKeyboardButton("👮 لوحة الأدمن", callback_data="admin_panel"))
        
    bot.send_message(cid, f"👋 أهلاً بك\n💰 رصيدك: `{balance}$`", reply_markup=markup, parse_mode="Markdown")

# --- عرض الدول ---
@bot.callback_query_handler(func=lambda call: call.data == "buy")
def show_countries(call):
    markup = types.InlineKeyboardMarkup(row_width=3)
    buttons = []
    for key, name in COUNTRIES.items():
        buttons.append(types.InlineKeyboardButton(name, callback_data=f"cnt:{key}"))
    markup.add(*buttons)
    bot.edit_message_text("🌍 اختر الدولة:", call.message.chat.id, call.message.message_id, reply_markup=markup)

# --- عرض الخدمات ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("cnt:"))
def show_services(call):
    country = call.data.split(":")[1]
    user_selections[call.from_user.id] = country
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for key, name in SERVICES.items():
        buttons.append(types.InlineKeyboardButton(name, callback_data=f"srv:{key}"))
    markup.add(*buttons)
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="buy"))
    
    bot.edit_message_text(f"اختر الخدمة لـ {COUNTRIES[country]}:", call.message.chat.id, call.message.message_id, reply_markup=markup)

# --- تنفيذ الشراء ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("srv:"))
def execute_order(call):
    cid = call.message.chat.id
    service = call.data.split(":")[1]
    country = user_selections.get(cid)
    
    if not country:
        bot.answer_callback_query(call.id, "انتهت الجلسة، ابدأ من جديد")
        return

    # 1. جلب السعر الحقيقي وحساب التكلفة
    try:
        headers = {'Authorization': 'Bearer ' + API_KEY, 'Accept': 'application/json'}
        # نطلب السعر فقط أولاً
        price_url = f"https://5sim.net/v1/guest/products/{country}/{service}"
        r_price = requests.get(price_url, headers=headers).json()
        
        cost_price = r_price.get(service, {}).get('Category', 0)
        if cost_price == 0: cost_price = r_price.get('Price', 0.5) # احتياطي
        
        final_price = float(cost_price) * PROFIT_MARGIN # إضافة الربح
        
        user_balance = get_user(cid)[2]
        
        if user_balance >= final_price:
            # 2. خصم الرصيد والشراء
            update_balance(cid, -final_price)
            bot.send_message(cid, f"🔄 جاري شراء {SERVICES[service]} من {COUNTRIES[country]}...\nسعر الخدمة: {round(final_price, 2)}$")
            
            # طلب الشراء الفعلي
            buy_url = f"https://5sim.net/v1/user/buy/activation/{country}/any/{service}"
            r_buy = requests.get(buy_url, headers=headers)
            
            if r_buy.status_code == 200:
                data = r_buy.json()
                if 'phone' in data:
                    phone = data['phone']
                    oid = data['id']
                    
                    msg = f"✅ **تم بنجاح!**\n📱 الرقم: `{phone}`\n⏳ انتظر الكود..."
                    bot.send_message(cid, msg, parse_mode="Markdown")
                    threading.Thread(target=check_sms, args=(cid, oid, headers, final_price)).start()
                else:
                    update_balance(cid, final_price) # استرجاع
                    bot.send_message(cid, "⚠️ لا توجد أرقام متاحة، تم استرجاع الرصيد.")
            else:
                update_balance(cid, final_price)
                bot.send_message(cid, "⚠️ خطأ من المصدر، تم استرجاع الرصيد.")
        else:
            bot.answer_callback_query(call.id, f"رصيدك غير كافي! السعر: {round(final_price, 2)}$", show_alert=True)
            
    except Exception as e:
        bot.send_message(cid, f"خطأ تقني: {e}")

# --- فحص الرسائل القصيرة ---
def check_sms(cid, oid, headers, price):
    for _ in range(30): # 2.5 دقيقة
        time.sleep(5)
        try:
            r = requests.get(f'https://5sim.net/v1/user/check/{oid}', headers=headers)
            data = r.json()
            if data['status'] == 'RECEIVED':
                code = data['sms'][0]['code']
                bot.send_message(cid, f"📬 **وصل الكود!**\nCode: `{code}`", parse_mode="Markdown")
                return
        except: pass
    
    # إذا فشل، إلغاء واسترجاع
    requests.get(f'https://5sim.net/v1/user/cancel/{oid}', headers=headers)
    update_balance(cid, price)
    bot.send_message(cid, "⏰ انتهى الوقت. تم إلغاء الطلب واسترجاع الرصيد.")

# ==================== 6. نظام الإيداع (يدوي وتلقائي) ====================
@bot.callback_query_handler(func=lambda call: call.data == "deposit")
def deposit_menu(call):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("USDT (تلقائي) ⚡", callback_data="auto_usdt"),
        types.InlineKeyboardButton("فودافون كاش (يدوي) 🇪🇬", callback_data="man_voda"),
        types.InlineKeyboardButton("STC Pay (يدوي) 🇸🇦", callback_data="man_stc"),
        types.InlineKeyboardButton("Payeer (يدوي) 🅿️", callback_data="man_payeer")
    )
    bot.edit_message_text("💳 اختر طريقة الشحن:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("man_"))
def manual_pay(call):
    method = call.data.split("_")[1]
    wallet = WALLETS.get('vodafone')
    if method == 'stc': wallet = WALLETS['stc']
    if method == 'payeer': wallet = WALLETS['payeer_manual']
    
    msg = f"💰 **الدفع اليدوي**\nحول المبلغ إلى: `{wallet}`\n📸 ثم أرسل صورة التحويل هنا."
    bot.send_message(call.message.chat.id, msg, parse_mode="Markdown")

@bot.message_handler(content_types=['photo'])
def handle_receipt(message):
    cid = message.chat.id
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ 1$", callback_data=f"add_{cid}_1"),
        types.InlineKeyboardButton("✅ 5$", callback_data=f"add_{cid}_5"),
        types.InlineKeyboardButton("✅ 10$", callback_data=f"add_{cid}_10"),
        types.InlineKeyboardButton("❌ رفض", callback_data=f"rej_{cid}")
    )
    bot.forward_message(ADMIN_ID, cid, message.message_id)
    bot.send_message(ADMIN_ID, f"إيصال من `{cid}`", reply_markup=markup)
    bot.reply_to(message, "✅ تم الاستلام وجاري المراجعة.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("add_") or call.data.startswith("rej_"))
def admin_decision(call):
    if call.from_user.id != ADMIN_ID: return
    action, uid, amount = call.data.split("_")
    
    if action == "add":
        update_balance(uid, float(amount))
        bot.send_message(uid, f"✅ تم شحن رصيدك بـ {amount}$")
        bot.edit_message_text(f"تم الشحن {amount}$ ✅", call.message.chat.id, call.message.message_id)
    else:
        bot.send_message(uid, "❌ تم رفض الإيصال.")
        bot.edit_message_text("تم الرفض ❌", call.message.chat.id, call.message.message_id)

# ==================== 7. نظام الإحالة ====================
@bot.callback_query_handler(func=lambda call: call.data == "referral")
def my_referral(call):
    cid = call.message.chat.id
    bot_username = bot.get_me().username
    link = f"https://t.me/{bot_username}?start={cid}"
    msg = f"🎁 **اربح رصيداً مجانياً!**\n\nشارك رابطك الخاص:\n`{link}`\n\nستحصل على {REFERRAL_REWARD}$ لكل صديق يسجل ويشترك في القناة."
    bot.send_message(cid, msg, parse_mode="Markdown")

# ==================== 8. لوحة الأدمن والإذاعة ====================
@bot.callback_query_handler(func=lambda call: call.data == "admin_panel" and call.from_user.id == ADMIN_ID)
def admin_panel(call):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    count = cur.fetchone()[0]
    conn.close()
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📢 إذاعة للكل", callback_data="broadcast"))
    bot.edit_message_text(f"📊 عدد المستخدمين: {count}", call.message.chat.id, call.message.message_id, reply_markup=markup)

broadcast_mode = False
@bot.callback_query_handler(func=lambda call: call.data == "broadcast")
def start_broadcast(call):
    global broadcast_mode
    broadcast_mode = True
    bot.send_message(ADMIN_ID, "أرسل الرسالة الآن لتتم إذاعتها للجميع:")

@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and broadcast_mode)
def do_broadcast(message):
    global broadcast_mode
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT chat_id FROM users")
    users = cur.fetchall()
    conn.close()
    
    success = 0
    for u in users:
        try:
            bot.copy_message(u[0], message.chat.id, message.message_id)
            success += 1
        except: pass
    
    broadcast_mode = False
    bot.reply_to(message, f"✅ تمت الإذاعة لـ {success} مستخدم.")

# ==================== 9. تشغيل الويب سيرفر ====================
@app.route('/')
def home():
    return "Bot is Alive"

def run_flask():
    app.run(host='0.0.0.0', port=5000)

if __name__ == "__main__":
    t = threading.Thread(target=run_flask)
    t.start()
    bot.infinity_polling(skip_pending=True)
