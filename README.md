![Python](https://img.shields.io/badge/-Python_v3.9.16-white?logo=python)
![python-telegram-bot](https://img.shields.io/badge/-Python_Telegram_Bot_v20.0-blue)
![SQLAlchemy](https://img.shields.io/badge/-SQLAlchemy_v2.0-red)
![Telegram](https://img.shields.io/badge/-Telegram-white?logo=telegram)
![Licence](https://img.shields.io/badge/License-GPLv3-blue.svg)

# Telegram Food Delivery Bot
This bot helps to create food delivery service from restaurants in city.

## Features
- All required DB management is done in bot
- Managers and Admin users
- Restaurants, Dishes and Dish Categories management
- Orders management

## Usage
1. Download project
2. Create virtual environment
3. Install required modules from `requirements.txt`, run in console `pip install -r requirements.txt`
4. Add required environment variables (specified in `.env.bat.example`) to your virtual environment
5. Configure statuses (optional), timezones and database dialect in `utils/constants.py`
6. Alter messages text according to your preferences in `utils/text.py`
7. Create database with `create_database.py` (you can always drop it with `drop_database.py`)
8. Start bot via `start_bot.py` in root directory
9. Provided `DEVELOPER_ID` will be used to create first admin user

To get `CHAT_ID`, bot can be started in `DEBUG` and added to group chat. After adding bot will reply with message information.

## Commands list
Commands list for users and for managers (if user is manager) can be viewed with `/help` command
