from sqlalchemy import select
from sqlalchemy.orm import Session
from telegram import (InlineKeyboardButton, InlineKeyboardMarkup,
                      ReplyKeyboardMarkup, Update)
from telegram.ext import ContextTypes

from modules.bot import config as bc
from modules.bot.src import restaurant
from modules.database import config as dbc
from modules.database import operations as dbo
from utils import constants as uc
from utils import text as ut
from utils import utility as uu


txt_dct = ut.messages  # dictionary of message texts
LOBBY_KEYBOARD: list = [
    [txt_dct['choose_restaurant']],
    [txt_dct['cart'], txt_dct['place_order']],
    [txt_dct['about_us']],
    [txt_dct['my_orders']]
]

async def showRestaurants(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message  # shortcut to use update message

    with Session(dbc.engine) as session:
        stmt = select(dbc.Restaurant).where(dbc.Restaurant.enabled==True)

        restaurants = session.scalars(stmt).all()

    txt = msg.text
    kbrd = ReplyKeyboardMarkup(
        uu.list_split(
            lst=[restaurant.name for restaurant in restaurants],
            cols=2
        )  # create list of names for ReplyKeyboard
        + restaurant.RESTAURANT_KEYBOARD  # Add bottom buttons
    )

    await msg.reply_text(txt, reply_markup=kbrd)  # send message 
    return bc.RESTAURANT  # return next state for conversation handler

async def showAboutUs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message  # shortcut to use update message

    txt = txt_dct['about_us_txt']  # about us text
    kbrd = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(txt_dct['contact_manager'], url=f"tg://user?id={uc.MANAGER_ID}")
            ]
        ]
    )

    await msg.reply_text(txt, reply_markup=kbrd)  # send message 
    return None  # returning None will not change current state
