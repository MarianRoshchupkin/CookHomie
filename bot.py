import logging
import os
import uuid
import urllib3
import requests

from datetime import datetime
from dotenv import load_dotenv

from telegram import (Update)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters
)
from telegram.constants import ParseMode

from models import SessionLocal, User, Allergy, Diet, Ingredient, init_db

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GIGACHAT_AUTHORIZATION_KEY = os.getenv("GIGACHAT_AUTHORIZATION_KEY")
GIGACHAT_CLIENT_ID = os.getenv("GIGACHAT_CLIENT_ID")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class GigaChatAPI:
    def __init__(self, authorization_key):
        self.authorization_key = authorization_key
        self.access_token = None
        self.token_expiry = datetime.utcnow()

    def get_access_token(self):
        if not self.access_token or datetime.utcnow() >= self.token_expiry:
            self.request_access_token()
        return self.access_token

    def request_access_token(self):
        url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "Authorization": f"Basic {self.authorization_key}",
            "RqUID": str(uuid.uuid4())
        }
        data = {"scope": "GIGACHAT_API_PERS"}
        try:
            response = requests.post(url, headers=headers, data=data, verify=False)
            response.raise_for_status()
            token_info = response.json()
            self.access_token = token_info["access_token"]
            self.token_expiry = datetime.utcfromtimestamp(token_info["expires_at"] / 1000)
            logger.info("GigaChat access token obtained.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error obtaining GigaChat token: {e}")
            raise

    def generate_recipe(self, user_message):
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.get_access_token()}",
            "Content-Type": "application/json",
            "X-Client-ID": GIGACHAT_CLIENT_ID,
            "X-Request-ID": str(uuid.uuid4()),
            "X-Session-ID": str(uuid.uuid4())
        }
        payload = {
            "model": "GigaChat",
            "messages": [
                {"role": "system", "content": "Ты — помощник по рецептам."},
                {"role": "user", "content": user_message}
            ],
            "max_tokens": 500,
            "temperature": 0.7
        }

        try:
            response = requests.post(url, headers=headers, json=payload, verify=False)
            response.raise_for_status()
            response_data = response.json()
            return response_data["choices"][0]["message"]["content"].strip()
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при обращении к GigaChat API: {e}")
            return "Извините, я не смог обработать ваш запрос в данный момент."

giga_chat_api = GigaChatAPI(GIGACHAT_AUTHORIZATION_KEY)


def get_or_create_user(update: Update):
    db = SessionLocal()
    try:
        telegram_id = update.effective_user.id
        username = update.effective_user.username
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            user = User(telegram_id=telegram_id, username=username)
            db.add(user)
            db.commit()
        return user
    except Exception as e:
        logger.error(f"Error retrieving/creating user: {e}")
        return None
    finally:
        db.close()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_or_create_user(update)
    if user:
        await update.message.reply_text(
            "Добро пожаловать в MealPlanner Bot!\n"
            "Введите /help, чтобы узнать о доступных командах."
        )
    else:
        await update.message.reply_text(
            "Произошла ошибка при регистрации пользователя. Попробуйте позже."
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "Доступные команды:\n"
        "/start - Запустить или перезапустить бота\n"
        "/help - Показать это справочное сообщение\n"
        "/setallergies - Указать или обновить список своих аллергий\n"
        "/setdiets - Указать или обновить свои пищевые предпочтения\n"
        "/setingredients - Указать или обновить список ингредиентов в холодильнике\n"
        "/getrecipe - Получить рецепт на основе ваших предпочтений\n"
        "/cancel - Отменить текущую операцию\n"
    )
    await update.message.reply_text(help_text)


SET_ALLERGIES, SET_DIETS, SET_INGREDIENTS = range(3)


async def set_allergies_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Пожалуйста, перечислите свои аллергии через запятую.\n"
        "Например: молоко, яйца, арахис"
    )
    return SET_ALLERGIES

async def allergies_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_or_create_user(update)
    if not user:
        await update.message.reply_text("Ошибка при получении данных пользователя.")
        return ConversationHandler.END

    allergy_list = [a.strip() for a in update.message.text.split(",") if a.strip()]
    db = SessionLocal()
    try:
        db.query(Allergy).filter(Allergy.user_id == user.id).delete()
        for allergy in allergy_list:
            db.add(Allergy(user_id=user.id, allergy_name=allergy))
        db.commit()
        await update.message.reply_text(f"Ваши аллергии обновлены: {', '.join(allergy_list)}")
    except Exception as e:
        logger.error(f"Ошибка при обновлении аллергий: {e}")
        await update.message.reply_text("Произошла ошибка при обновлении списка аллергий.")
    finally:
        db.close()
    return ConversationHandler.END  # Завершить беседу


async def set_diets_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Пожалуйста, перечислите свои диетические предпочтения через запятую.\n"
        "Например: вегетарианская, кето, безглютеновая"
    )
    return SET_DIETS

async def diets_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_or_create_user(update)
    if not user:
        await update.message.reply_text("Ошибка при получении данных пользователя.")
        return ConversationHandler.END

    diet_list = [d.strip() for d in update.message.text.split(",") if d.strip()]
    db = SessionLocal()
    try:
        db.query(Diet).filter(Diet.user_id == user.id).delete()
        for diet in diet_list:
            db.add(Diet(user_id=user.id, diet_name=diet))
        db.commit()
        await update.message.reply_text(f"Ваши диетические предпочтения обновлены: {', '.join(diet_list)}")
    except Exception as e:
        logger.error(f"Ошибка при обновлении диет: {e}")
        await update.message.reply_text("Произошла ошибка при обновлении диет.")
    finally:
        db.close()
    return ConversationHandler.END  # Завершить беседу

async def set_ingredients_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Пожалуйста, перечислите ингредиенты в вашем холодильнике через запятую.\n"
        "Например: курица, морковь, лук"
    )
    return SET_INGREDIENTS  # Перейти к состоянию установки ингредиентов

async def ingredients_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_or_create_user(update)
    if not user:
        await update.message.reply_text("Ошибка при получении данных пользователя.")
        return ConversationHandler.END

    ingredients_list = [i.strip() for i in update.message.text.split(",") if i.strip()]
    db = SessionLocal()
    try:
        # Удаляем существующие ингредиенты пользователя
        db.query(Ingredient).filter(Ingredient.user_id == user.id).delete()
        # Добавляем новые ингредиенты
        for ing in ingredients_list:
            db.add(Ingredient(user_id=user.id, ingredient_name=ing))
        db.commit()
        await update.message.reply_text(f"Список ингредиентов обновлён: {', '.join(ingredients_list)}")
    except Exception as e:
        logger.error(f"Ошибка при обновлении ингредиентов: {e}")
        await update.message.reply_text("Произошла ошибка при обновлении списка ингредиентов.")
    finally:
        db.close()
    return ConversationHandler.END  # Завершить беседу

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Действие отменено.")
    return ConversationHandler.END

async def get_recipe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_or_create_user(update)
    if not user:
        await update.message.reply_text("Ошибка при получении данных пользователя.")
        return

    db = SessionLocal()
    try:
        user_allergies = db.query(Allergy).filter(Allergy.user_id == user.id).all()
        user_diets = db.query(Diet).filter(Diet.user_id == user.id).all()
        user_ingredients = db.query(Ingredient).filter(Ingredient.user_id == user.id).all()

        allergies_str = ", ".join(a.allergy_name for a in user_allergies) or "нет"
        diets_str = ", ".join(d.diet_name for d in user_diets) or "нет"
        ingredients_str = ", ".join(i.ingredient_name for i in user_ingredients) or "нет"

        prompt = (
            "Параметры пользователя:\n"
            f"- Аллергии: {allergies_str}\n"
            f"- Диетические предпочтения: {diets_str}\n"
            f"- Доступные ингредиенты: {ingredients_str}\n\n"
            "Пожалуйста, предложи рецепт, который учитывает все эти ограничения."
        )

        recipe = giga_chat_api.generate_recipe(prompt)
        await update.message.reply_text(recipe, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Ошибка при генерации рецепта: {e}")
        await update.message.reply_text("Произошла ошибка при создании рецепта.")
    finally:
        db.close()

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик для всех остальных текстовых сообщений,
    которые не распознаны как команды или находятся вне беседы.
    """
    await update.message.reply_text("Я не понял сообщение. Используйте /help, чтобы увидеть список команд.")

def main():
    init_db()

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    allergies_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('setallergies', set_allergies_command)],
        states={
            SET_ALLERGIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, allergies_handler)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    diets_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('setdiets', set_diets_command)],
        states={
            SET_DIETS: [MessageHandler(filters.TEXT & ~filters.COMMAND, diets_handler)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    ingredients_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('setingredients', set_ingredients_command)],
        states={
            SET_INGREDIENTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ingredients_handler)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    # Добавляем ConversationHandlers в приложение
    application.add_handler(allergies_conv_handler)
    application.add_handler(diets_conv_handler)
    application.add_handler(ingredients_conv_handler)

    # Обработчик команды /getrecipe
    application.add_handler(CommandHandler("getrecipe", get_recipe))

    # Обработчик всех остальных текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Запуск бота
    application.run_polling()

if __name__ == "__main__":
    main()