"""
Telegram Bot для "Вкусные традиции" — версия с базой данных
============================================================
Возможности:
  • Принимает заказы из мини-приложения
  • Сохраняет заказы в базу данных (SQLite)
  • Клиент получает кнопку "Подтвердить получение" → заказ завершается автоматически
  • Команда /myorders — клиент видит свои заказы
  • Команда /orders — администратор видит все заказы
  • Работает 24/7 на сервере

Установка:  pip install pyTelegramBotAPI
Запуск:     python bot.py
"""

import telebot
from telebot.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo,
    ReplyKeyboardMarkup, KeyboardButton
)
import json
import os
import sqlite3
from datetime import datetime

# ======================================================
# НАСТРОЙКИ
# ======================================================
# Значения берутся из переменных окружения (для сервера),
# если их нет — используются значения по умолчанию (для компьютера).
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8863108783:AAE_I3Tp2ELGxsUukOvmG6i9ymswiJgz9rc")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "370006281")
WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://velvety-sawine-bfe1f5.netlify.app/")

# Путь к базе данных. На сервере с диском (volume) можно указать /data/orders.db
DB_PATH = os.environ.get("DB_PATH", "orders.db")
# ======================================================

bot = telebot.TeleBot(BOT_TOKEN)


# ---------- БАЗА ДАННЫХ ----------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_num   INTEGER PRIMARY KEY,
            user_id     INTEGER,
            name        TEXT,
            phone       TEXT,
            mode        TEXT,
            delivery    TEXT,
            payment     TEXT,
            items_json  TEXT,
            total       INTEGER,
            status      TEXT,
            created_at  TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_order(order):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO orders
        (order_num, user_id, name, phone, mode, delivery, payment, items_json, total, status, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (
        order['order_num'], order['user_id'], order['name'], order['phone'],
        order['mode'], order['delivery'], order['payment'],
        json.dumps(order['items'], ensure_ascii=False),
        order['total'], order['status'], order['created_at']
    ))
    conn.commit()
    conn.close()


def set_status(order_num, status):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE orders SET status=? WHERE order_num=?", (status, order_num))
    conn.commit()
    conn.close()


def get_order(order_num):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM orders WHERE order_num=?", (order_num,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_orders(user_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM orders WHERE user_id=? ORDER BY order_num DESC", (user_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_orders(limit=30):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM orders ORDER BY order_num DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------- ВСПОМОГАТЕЛЬНОЕ ----------
PAYMENT_LABELS = {
    'cash': '💵 Наличными при получении',
    'card_online': '💳 Картой онлайн',
    'card_delivery': '🏧 Картой при получении'
}
DELIVERY_LABELS = {'delivery': '🚚 Доставка', 'pickup': '🏪 Самовывоз'}


def open_shop_markup():
    # ВАЖНО: магазин открывается через кнопку-клавиатуру (KeyboardButton),
    # иначе Telegram не передаёт заказ боту (ограничение Telegram).
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("🛒 Открыть магазин", web_app=WebAppInfo(url=WEBAPP_URL)))
    return markup


# ---------- КОМАНДЫ ----------
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        "👋 Добро пожаловать в *«Вкусные традиции»*!\n\n"
        "🥐 Мы — производитель свежей халяль-выпечки с собственным цехом.\n\n"
        "🤝 *Работаем с оптовиками* — это наш приоритет:\n"
        "• Крупные объёмы и стабильные поставки\n"
        "• Лучшие цены для постоянных партнёров\n"
        "• Свежие партии каждые 2 часа\n"
        "• Работаем круглосуточно\n\n"
        "🚚 Доставка по городу и области • Самовывоз\n\n"
        "Команды:\n"
        "/myorders — мои заказы\n\n"
        "Нажмите кнопку ниже, чтобы открыть каталог 👇",
        parse_mode='Markdown',
        reply_markup=open_shop_markup()
    )


@bot.message_handler(commands=['menu'])
def menu(message):
    bot.send_message(message.chat.id, "Открыть наш магазин:", reply_markup=open_shop_markup())


@bot.message_handler(commands=['myorders'])
def my_orders(message):
    orders = get_user_orders(message.chat.id)
    if not orders:
        bot.send_message(message.chat.id, "У вас пока нет заказов 📋", reply_markup=open_shop_markup())
        return
    for o in orders:
        send_order_card(message.chat.id, o, for_admin=False)


@bot.message_handler(commands=['orders'])
def admin_orders(message):
    if str(message.chat.id) != str(ADMIN_CHAT_ID):
        return  # команда только для администратора
    orders = get_all_orders()
    if not orders:
        bot.send_message(message.chat.id, "Заказов пока нет.")
        return
    bot.send_message(message.chat.id, f"📋 Последние заказы ({len(orders)}):")
    for o in orders:
        send_order_card(message.chat.id, o, for_admin=True)


def send_order_card(chat_id, o, for_admin=False):
    items = json.loads(o['items_json'])
    status_emoji = "✅" if o['status'] == 'Завершён' else "⏳"
    text = f"{status_emoji} *Заказ #{o['order_num']}* — {o['status']}\n"
    text += f"📅 {o['created_at']}\n"
    text += f"🏷 {o['mode']} • {DELIVERY_LABELS.get(o['delivery'], o['delivery'])}\n"
    if for_admin:
        text += f"👤 {o['name']} • 📞 {o['phone']}\n"
    text += f"💳 {PAYMENT_LABELS.get(o['payment'], o['payment'])}\n\n"
    for i in items:
        text += f"  • {i['name']} × {i['qty']} = {i['price'] * i['qty']} ₽\n"
    text += f"\n💰 *ИТОГО: {o['total']} ₽*"

    markup = InlineKeyboardMarkup()
    if o['status'] != 'Завершён':
        # Кнопка подтверждения получения (для клиента)
        markup.add(InlineKeyboardButton(
            "✅ Подтвердить получение",
            callback_data=f"confirm_{o['order_num']}"
        ))
    bot.send_message(chat_id, text, parse_mode='Markdown', reply_markup=markup)


# ---------- ПРИЁМ ЗАКАЗА ИЗ МИНИ-ПРИЛОЖЕНИЯ ----------
@bot.message_handler(content_types=['web_app_data'])
def handle_order(message):
    try:
        data = json.loads(message.web_app_data.data)
        order_num = data.get('order_number', 0)
        name = data.get('name', '—')
        phone = data.get('phone', '—')
        mode = 'ОПТ' if data.get('mode') == 'opt' else 'Розница'
        delivery = data.get('delivery', '—')
        payment = data.get('payment', '—')
        items = data.get('items', [])
        total = data.get('total', 0)
        order_text = data.get('order_text', '')

        # Сохраняем заказ в базу
        order = {
            'order_num': order_num,
            'user_id': message.chat.id,
            'name': name,
            'phone': phone,
            'mode': mode,
            'delivery': delivery,
            'payment': payment,
            'items': items,
            'total': total,
            'status': 'В обработке',
            'created_at': datetime.now().strftime('%d.%m.%Y %H:%M')
        }
        save_order(order)

        # Подтверждение клиенту с кнопкой "Подтвердить получение"
        client_msg = (
            f"✅ *Заказ #{order_num} принят!*\n\n"
            f"Мы получили ваш заказ и скоро свяжемся с вами.\n\n"
            f"📋 *Итого:* {total} ₽\n"
            f"📦 *Получение:* {DELIVERY_LABELS.get(delivery, delivery)}\n"
            f"💳 *Оплата:* {PAYMENT_LABELS.get(payment, payment)}\n"
        )
        if payment == 'card_online':
            client_msg += (
                "\n💳 *Реквизиты для перевода:*\n"
                "Карта: `2202 2085 3984 7781`\n"
                "Телефон (СБП): `8 (925) 467-51-19`\n"
                "Получатель: Меликсетян Роман Рафаелович (Сбербанк)\n\n"
                "_После оплаты отправьте чек в этот чат._"
            )
        client_msg += (
            "\n\n📦 Когда получите заказ — нажмите кнопку ниже, "
            "чтобы подтвердить получение.\n\n"
            "Спасибо, что выбрали «Вкусные традиции»! 🥐"
        )

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(
            "✅ Подтвердить получение",
            callback_data=f"confirm_{order_num}"
        ))
        bot.send_message(message.chat.id, client_msg, parse_mode='Markdown', reply_markup=markup)

        # Уведомление администратору
        admin_msg = f"🔔 *НОВЫЙ ЗАКАЗ!*\n\n{order_text}"
        bot.send_message(ADMIN_CHAT_ID, admin_msg, parse_mode='Markdown')

    except Exception as e:
        print(f"Ошибка обработки заказа: {e}")
        bot.send_message(message.chat.id, "✅ Заказ получен! Мы скоро свяжемся с вами.")


# ---------- ОБРАБОТКА КНОПКИ "ПОДТВЕРДИТЬ ПОЛУЧЕНИЕ" ----------
@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_"))
def confirm_received(call):
    order_num = int(call.data.split("_")[1])
    order = get_order(order_num)

    if not order:
        bot.answer_callback_query(call.id, "Заказ не найден.")
        return

    if order['status'] == 'Завершён':
        bot.answer_callback_query(call.id, "Этот заказ уже завершён ✅")
        return

    # Меняем статус на "Завершён"
    set_status(order_num, 'Завершён')
    bot.answer_callback_query(call.id, "Спасибо! Заказ завершён ✅")

    # Убираем кнопку и обновляем текст у клиента
    try:
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        bot.send_message(
            call.message.chat.id,
            f"✅ *Заказ #{order_num} завершён!*\n\nСпасибо за покупку! Будем рады видеть вас снова 🥐",
            parse_mode='Markdown'
        )
    except Exception as e:
        print(f"Не удалось обновить сообщение: {e}")

    # Уведомляем администратора
    try:
        bot.send_message(
            ADMIN_CHAT_ID,
            f"✅ Клиент подтвердил получение заказа *#{order_num}*\n"
            f"👤 {order['name']} • 📞 {order['phone']}\n"
            f"💰 {order['total']} ₽",
            parse_mode='Markdown'
        )
    except Exception as e:
        print(f"Не удалось уведомить админа: {e}")


# ---------- ЛЮБЫЕ ДРУГИЕ СООБЩЕНИЯ ----------
@bot.message_handler(func=lambda m: True)
def echo(message):
    bot.send_message(
        message.chat.id,
        "Нажмите кнопку, чтобы открыть наш магазин 👇\n\n"
        "Или используйте команду /myorders, чтобы посмотреть свои заказы.",
        reply_markup=open_shop_markup()
    )


if __name__ == '__main__':
    init_db()
    print("🥐 Бот 'Вкусные традиции' запущен (с базой данных)!")
    print("База данных:", DB_PATH)
    print("Нажми Ctrl+C чтобы остановить")
    bot.infinity_polling()
