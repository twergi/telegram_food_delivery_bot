import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session
from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes, filters

from modules.bot import config as bc
from modules.bot.src import dish
from modules.database import config as dbc
from utils import constants as uc
from utils import text as ut
from utils import utility as uu


txt_dct = ut.messages  # dictionary of message texts
RESTAURANT_KEYBOARD: list = [
    [txt_dct['place_order']],
    [txt_dct['back_to_menu'], txt_dct['cart']]
]

class RestaurantFilter(filters.MessageFilter):  # custom filter class
    def filter(self, message):
        with Session(dbc.engine) as session:
            restaurant = session.scalar(
                select(dbc.Restaurant)
                    .where(
                        (dbc.Restaurant.name==message.text)
                        & (dbc.Restaurant.enabled==True)
                    )
                )
            return True if restaurant else False

async def isRestaurantWorking(restaurant_name: str, alert: bool = False, update: Update = None):
    '''Checks if restaurant is working, returns bool. If alert is True, sends message to update user'''
    restaurant_works = True  # set flag
    with Session(dbc.engine) as session:
    # ---------- GETTING RESTAURANTS SCHEDULE ----------
        stmt = (
            select(dbc.RestaurantSchedule)
                .join(dbc.RestaurantSchedule.restaurant)
                .where(
                    (dbc.Restaurant.name==restaurant_name)
                    & (dbc.Restaurant.enabled==True)
                )
                .order_by(dbc.RestaurantSchedule.day_of_week)
        )
        schedule = session.scalars(stmt).all()  # get schedule of the selected restaurant

        if not schedule:
            return False

    # ---------- END OF GETTING RESTAURANTS SCHEDULE ----------
    schedule_dict = {}  # creating dictionary that stores all days in schedule
    for row in schedule:
        schedule_dict[row.day_of_week] = (row.start, row.end)
    
    current_datetime = uu.current_server_time().astimezone(uc.PLACE_TIMEZONE)  # get current datetime to check if restaurant is working
    current_day_of_week = current_datetime.weekday() + 1  #  + 1 because 0 is monday, but in database 1 is monday
    current_time = current_datetime.time()  # get current time

    works_today = True if schedule_dict.get(current_day_of_week) else False  # set flag if today in schedule
    if works_today:
        start_time = schedule_dict[current_day_of_week][0]  # work starting time
        end_time = schedule_dict[current_day_of_week][1]  # work ending time
        if end_time == dt.time(00,00,00):
            end_time = dt.time(23,59,59)  # datetime converts 24 to 00, so current time will be bigger than end time

    if (
        not works_today
        or start_time > current_time
        or end_time < current_time
    ):  # if restaurant doesn't work
        restaurant_works = False  # change flag
        if alert:
            weekday_name = [
                'Monday', 'Tuesday', 'Wednesday',
                'Thursday', 'Friday', 'Saturday',
                'Sunday',
            ]  # list to convert int weekday to str
            txt = (
                "Currently restaurant doesn't work.\n"
                "Working hours:\n"
            )
            for day in schedule_dict:
                txt = txt + (
                    f"{weekday_name[day-1]}: "
                    f"{schedule_dict[day][0].hour:02}:{schedule_dict[day][0].minute:02} - "
                    f"{schedule_dict[day][1].hour:02}:{schedule_dict[day][1].minute:02}\n"
                )  # create message text with working schedule
            
            await update.effective_user.send_message(txt)  # send message
    return restaurant_works  # return restaurant state

async def showDishCategories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message  # shortcut to use update message

    with Session(dbc.engine) as session:
        # ---------- GETTING RESTAURANTS DISH CATEGORIES ----------
        stmt = (
            select(dbc.DishCategory.name)
                .join(dbc.Dish, onclause=(
                    dbc.Dish.dish_category_id==dbc.DishCategory.id
                ))
                .join(
                    dbc.Dish.restaurant
                )
                .where(
                    (dbc.Restaurant.name==msg.text)
                    & (dbc.Dish.enabled==True)
                )
                .group_by(dbc.DishCategory.name)
                .order_by(dbc.DishCategory.name)
        )
        categories = session.scalars(stmt).all()  # get all dish categories in the selected restaurant
        # ---------- END OF GETTING RESTAURANTS DISH CATEGORIES ----------

    await isRestaurantWorking(
        restaurant_name=msg.text,
        alert=True,
        update=update
    )
    
    context.user_data['restaurant_name'] = msg.text  # save viewed restaurant for cart
    context.user_data['dish_categories'] = categories  # adding list of categories to check it in the next state
    if not context.user_data.get('cart'):  # create if doesn't exist
        context.user_data['cart'] = {
            'dishes':{}
        }  # dictionary for cart


    kbrd = ReplyKeyboardMarkup(
        uu.list_split(
            lst=categories,
            cols=2
        )
        + dish.DISH_KEYBOARD  # Add bottom buttons
    )  # create keyboard
    txt = msg.text  # reply text will be the name of the restaurant

    await msg.reply_text(
        text=txt,
        reply_markup=kbrd
    )  # send message
    return bc.DISH  # return next state for conversation handler