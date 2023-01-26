import datetime as dt
import tempfile

import tabulate
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from telegram import (InlineKeyboardButton, InlineKeyboardMarkup,
                      ReplyKeyboardMarkup, ReplyKeyboardRemove, Update)
from telegram.ext import ContextTypes

from modules.bot import config as bc
from modules.bot.src import error, user_orders
from modules.database import config as dbc
from utils import constants as uc
from utils import text as ut


users_list_header = ['ID', 'Username', 'First Name', 'Last Name', 'Admin', 'Manager', 'Date Registered']  # header for users list
single_ordr_hdr = ['Name', 'Quantity', 'Price']  # create header for the table with one order description
many_ordrs_hdr = ['Order Number', 'Date', 'Status', 'Total Price']  # create header for the table with many orders
txt_dct = ut.messages  # dictionary of message texts

async def findOrder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message  # shortcut to use update message
    u_usr = update.effective_user  # shortcut for user

    try:
        order_id = int(context.args[0])  # get order id from message context

        with Session(dbc.engine) as session:
            query_user = session.scalar(
                select(dbc.User)
                    .where(
                        (dbc.User.id==u_usr.id)
                        & (dbc.User.manager==True)
                    )
            )
            if query_user is None:
                await msg.reply_text('You are not manager')
                return bc.END  # end conversation

            order = session.scalar(
                select(dbc.Order)
                    .where(dbc.Order.id == order_id)
            )

            if order is None:
                await msg.reply_text(txt_dct['order_not_found'])  # send message
                return None  # return None to not change state

            restaurant = order.cart_dish[0].dish.restaurant
            location = [float(value) for value in order.location.split(',')]  # get order delivery location

            txt = str(order.id)  # caption for message

            order_dishes = []  # create list for dishes in order
            total_price = 0  # total price of the order
            for cart_dish in order.cart_dish:
                order_dishes.append(
                    [cart_dish.dish.name, cart_dish.quantity, f"{cart_dish.dish.price} {restaurant.currency}"]
                )
                total_price += cart_dish.dish.price*cart_dish.quantity  # add price to total
            
            order_dishes.append(
                ['Total', None, f"{total_price} {restaurant.currency}"]  # add total price to list
            )

            table = tabulate.tabulate(order_dishes, headers=single_ordr_hdr)  # create beautiful table for order
            order_date = order.date_ordered.astimezone(uc.PLACE_TIMEZONE)  # convert timezone from UTC to local
            table += (
                f"\n\nOrder Number: {order.id}\n"
                f"Restaurant: {restaurant.name}\n"
                f"Status: {order.status.name}\n"
                f"Order Date: {order_date.hour:02}:{order_date.minute:02} "
                f"{order_date.day:02}.{order_date.month:02}.{order_date.year:04}"
            )  # add bottom information to the table

            table_bytes = user_orders.create_image(table)  # create image in bytes

            kbrd = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(f"Status: {order.status.name}", callback_data={
                            'value': '-CHANGE_STATUS-',
                            'order_id': order.id
                        })
                    ],
                    [
                        InlineKeyboardButton(f"Contact user ({order.user_id})", url=f"tg://user?id={order.user_id}")
                    ],
                    [
                        InlineKeyboardButton(f"Contact manager ({order.manager_id})", url=f"tg://user?id={order.manager_id}")
                    ],
                ]
            )  # inline keyboard
            
            await u_usr.send_photo(table_bytes, caption=txt, reply_markup=kbrd)  # send message with photo

            kbrd = ReplyKeyboardMarkup([[f"/user {order.user_id}"]], True)  # text keyboard
            await u_usr.send_location(
                latitude=location[0],
                longitude=location[1],
                reply_markup=kbrd
            )  # send delivery location
    
            # Session now may be closed
    
    except Exception as er:
        await msg.reply_text((
            f"Error: {er}\n"
            "To use this command: /order <ORDER_NUMBER>"
        ))  # send message with error
        return None  # return None to not change state
    
    context.user_data.clear()  # clear manager's dictionary  
    return bc.M_ORDER  # return next state for conversation handler

async def showOrders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Sends user file with last orders, quantity provided as argument'''
    u_usr = update.effective_user  # user from update

    with Session(dbc.engine) as session:
        # ---------- CHECKING IF UPDATE USER IS MANAGER ----------
        user_manager = session.scalar(
            select(dbc.User)
                .where(
                    (dbc.User.id==u_usr.id)
                    & (dbc.User.manager==True)
                )
        )

        if not user_manager:
            await u_usr.send_message('You are not manager')  # notify of prohibited action
            return bc.END  # end conversation
        # ---------- END OF CHECKING IF UPDATE USER IS MANAGER ----------

        try:
            quantity = int(context.args[0])  # get quantity from message
        except Exception as er:
            await u_usr.send_message(f"Error: {er}\nTry: /orders 10")
            return None  # not changing state

        stmt = (
            select(
                dbc.Order.id,
                dbc.Order.date_ordered,
                dbc.Status.name,
                func.sum(dbc.Dish.price*dbc.CartDish.quantity),  # cart total price
                dbc.Restaurant.currency
            )
                .join(dbc.Order.status)
                .join(dbc.Order.cart_dish)
                .join(dbc.CartDish.dish)
                .join(dbc.Dish.restaurant)
                .group_by(
                    dbc.Order.id,
                    dbc.Status.name,
                    dbc.Restaurant.currency
                )
                .order_by(dbc.Order.date_ordered.desc())  # order orders descending
                .limit(quantity)
        )
        orders = session.execute(stmt).all()

        orders_list = []  # create list for all orders
        for order in orders:
            order_date = order[1].astimezone(uc.PLACE_TIMEZONE)  # convert timezone from UTC to local
            orders_list.append(
                [
                    f"{order[0]:02}",  # order id
                    f"{order_date.hour:02}:{order_date.minute:02} {order_date.day:02}.{order_date.month:02}.{order_date.year:04}",  # time and date
                    order[2],  # status name
                    f"{order[3]} {order[4]}"  # total price
                ]
            )
        if orders_list:
            table = tabulate.tabulate(orders_list, headers=many_ordrs_hdr)  # create beautiful table for orders
            tmp_file = tempfile.NamedTemporaryFile(suffix='.txt')  # create temporary file to be sent
            tmp_file.write(table.encode('utf-8'))  # add table to the file
            tmp_file.seek(0)

            await u_usr.send_document(tmp_file, f'Last {quantity} orders')  # send file
        else:
            await u_usr.send_message('Orders list is empty')
    return None  # not changing state

async def showStatuses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Edits message keyboard to show available statuses for order'''
    query = update.callback_query  # shortcut for query
    order_id = query.data['order_id']  # getting order id from callback query

    with Session(dbc.engine) as session:
        statuses = session.scalars(
            select(dbc.Status)
        ).all()  # get statuses list from database

        kbrd = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        status.name,
                        callback_data={
                            'value': '-NEW_STATUS-',
                            'status_id': status.id,
                            'order_id': order_id
                        }
                    )
                ] for status in statuses
            ]
        )  # create new inline keyboard

    await query.edit_message_reply_markup(kbrd)  # update keyboard
    return None  # not chaning state

async def setStatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Sets new status to order'''
    query = update.callback_query  # shortcut for query
    u_usr = update.effective_user  # get user
    order_id = query.data['order_id']  # getting order id from callback query
    status_id = query.data['status_id'] # getting status id from callback query

    with Session(dbc.engine) as session:
        user_manager = session.scalar(
            select(dbc.User)
                .where(
                    (dbc.User.id==u_usr.id)
                    & (dbc.User.manager==True)
                )
            )
        if not user_manager:
            await query.answer('You are not manager', show_alert=True)  # notify pressed button person
            return bc.END  # end conversation

        order = session.scalar(select(dbc.Order).where(dbc.Order.id==order_id))  # get order
        order.status_id = status_id  # set new status
        order.manager_id = u_usr.id  # update manager for order

        session.commit()  # save changes

        new_status_name = order.status.name  # get new status name
        user_id = order.user_id # get user
    
    kbrd = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(f"Status: {new_status_name}", callback_data={
                    'value': '-CHANGE_STATUS-',
                    'order_id': order_id
                })
            ],
            [
                InlineKeyboardButton(f"Contact user ({user_id})", url=f"tg://user?id={user_id}")
            ],
            [
                InlineKeyboardButton(f"Contact manager ({u_usr.id})", url=f"tg://user?id={u_usr.id}")
            ],
        ]
    )  # inline keyboard

    await query.edit_message_reply_markup(kbrd)  # update keyboard
    return None  # not chaning state

def create_user_keyboard(user: dbc.User, query_user: dbc.User):
    '''Creates InlineKeyboardMarkup for user message'''
    kbrd = [
        [
            InlineKeyboardButton('Contact user', url=f"tg://user?id={user.id}")
        ]
    ]

    if (
        query_user.id != user.id  # if manager is not viewing himself
        and query_user.admin  # and manager is admin
    ):
        kbrd.append(
            [
                InlineKeyboardButton(
                    "✅ admin" if user.admin else "❌ admin",
                    callback_data={
                        'value': '-ADMIN_STATUS-',
                        'user_id': user.id
                    }
                ),
                InlineKeyboardButton(
                    "✅ manager" if user.manager else "❌ manager",
                    callback_data={
                        'value': '-MANAGER_STATUS-',
                        'user_id': user.id
                    }
                )
            ]
        )
    kbrd = InlineKeyboardMarkup(kbrd)  # create Inline keyboard
    
    return kbrd

def create_user_text(user: dbc.User):
    '''Return str of user data for message'''
    return (
        f"ID: {user.id}\n"
        f"username: {user.username}\n"
        f"first name: {user.first_name}\n"
        f"last name: {user.last_name}\n"
        f"date registered: {user.date_registered.astimezone(uc.PLACE_TIMEZONE)}"
    )

async def findUser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Shows user information'''
    msg = update.message  # shortcut for message
    u_usr = update.effective_user  # get update user

    with Session(dbc.engine) as session:
        query_user = session.scalar(
            select(dbc.User)
                .where(
                    (dbc.User.id==u_usr.id)
                    & (dbc.User.manager==True)
                )
        )  # get manager

        if not query_user:
            await msg.reply_text('You are not manager')
            return bc.END  # end conversation
        
        try:
            arg = context.args[0]  # get user id or username from message context
            if arg[0] == '@':
                where_clause = dbc.User.username == arg[1:]  # if username is provided
            else:
                where_clause = dbc.User.id == int(arg)  # if id is provided

        except Exception as er:
            await msg.reply_text((
                f"Error: {er}\n"
                "To use this command: /user <USER_ID> or /user <@USERNAME>"
            ))  # send message with error
            return None  # return None to not change state

        user = session.scalar(select(dbc.User).where(where_clause))

        if user is None:
                await msg.reply_text(txt_dct['user_not_found'])  # send message
                return None  # return None to not change state

        kbrd = create_user_keyboard(
            user,
            query_user
        )  # create keyboard for message
        txt = create_user_text(user)  # create text for message

    await msg.reply_text(txt, reply_markup=kbrd)  # send message with user information
    return bc.M_USER  # return state for conversation handler

async def lastUsers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Shows last users, quantity provided as argument'''
    u_usr = update.effective_user  # user from update
    
    with Session(dbc.engine) as session:
        # ---------- CHECKING IF UPDATE USER IS MANAGER ----------
        user_manager = session.scalar(
            select(dbc.User)
                .where(
                    (dbc.User.id==u_usr.id)
                    & (dbc.User.manager==True)
                )
        )

        if not user_manager:
            await u_usr.send_message('You are not manager')  # notify of prohibited action
            return bc.END  # end conversation
        # ---------- END OF CHECKING IF UPDATE USER IS MANAGER ----------

        try:
            quantity = int(context.args[0])  # get quantity from message
        except Exception as er:
            await u_usr.send_message(f"Error: {er}\nTry: /users 10")
            return None  # not changing state
        
        last_users = session.scalars(
            select(dbc.User)
                .order_by(dbc.User.date_registered.desc())
                .limit(quantity)
        )

        users_list = []
        for user in last_users:
            users_list.append(
                [
                    str(user.id),
                    str(user.username),
                    str(user.first_name),
                    str(user.last_name),
                    str(user.admin),
                    str(user.manager),
                    str(user.date_registered.astimezone(uc.PLACE_TIMEZONE)),
                ]
            )
        if users_list:
            table = tabulate.tabulate(users_list, headers=users_list_header)  # create beautiful table for orders
            tmp_file = tempfile.NamedTemporaryFile(suffix='.txt')  # create temporary file to be sent
            tmp_file.write(table.encode('utf-8'))  # add table to the file
            tmp_file.seek(0)

            await u_usr.send_document(tmp_file, f'Last {quantity} users')  # send file
        else:
            await u_usr.send_message('Users list is empty')
    return None  # not changing state
        
async def changePermission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Changes admin and manager permission in database'''
    query = update.callback_query  # shortcut for query
    u_usr = update.effective_user  # get user
    user_id = query.data['user_id']  # getting user id from callback query

    if u_usr == user_id:  # if user tries to change self permissions
        await query.answer('You cannot change permissions of yourself', show_alert=True)  # notify of prohibited action
        return None  # return from function

    with Session(dbc.engine) as session:
        query_user = session.scalar(
            select(dbc.User)
                .where(
                    (dbc.User.id==u_usr.id)
                    & (dbc.User.admin==True)
                )
            )  # get query user from update

        if not query_user:
            await query.answer('You are not admin', show_alert=True)  # notify of prohibited action
            return bc.END  # end conversation
        
        user = session.scalar(select(dbc.User).where(dbc.User.id==user_id))  # get user from update

        if query.data['value'] == '-ADMIN_STATUS-':
            if user.admin:
                await query.answer('User now cannot create new managers', show_alert=True)
                user.admin = False  # change permission
            else:
                await query.answer('User now can create new managers and has manager rights', show_alert=True)
                user.admin = True
                user.manager = True  # user cannot be admin without manager rights
        else:
            if user.manager:
                await query.answer('User now has no permissions', show_alert=True)
                user.admin = False  # user cannot be admin without manager rights
                user.manager = False
            else:
                await query.answer('User now is manager and can manage orders, restaurants and categories and dishes', show_alert=True)
                user.manager = True  # change permission
        
        session.commit()  # save changes

        kbrd = create_user_keyboard(user, query_user)  # create keyboard for message

    await query.edit_message_reply_markup(kbrd)  # edit keyboard
    return None  # do not change state

async def findRestaurant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Sends user message and reply keyboard to manage restaurant and its content'''
    msg = update.message  # shortcut for message
    u_usr = update.effective_user  # get user

    with Session(dbc.engine) as session:
        # ---------- CHECKING IF UPDATE USER IS MANAGER ----------
        user_manager = session.scalar(
            select(dbc.User)
                .where(
                    (dbc.User.id==u_usr.id)
                    & (dbc.User.manager==True)
                )
        )

        if not user_manager:
            await msg.reply_text('You are not manager')  # notify of prohibited action
            return bc.END  # end conversation
        # ---------- END OF CHECKING IF UPDATE USER IS MANAGER ----------
        
        # ---------- CHECKING FOR RESTAURANT IN DATABASE ----------
        try:
            assert len(context.args), 'Arguments are not provided'
            restaurant_name = ' '.join(context.args)  # get argument from message
        except Exception as er:
            await msg.reply_text((
                f"Error: {er}\n"
                "To use this command: /restaurant <RESTAURANT_NAME>"
            ))  # send message with error
            return None  # return None to not change state

        context.user_data.clear()  # clear manager's dictionary 

        restaurant = session.scalar(
            select(dbc.Restaurant)
                .where(func.lower(dbc.Restaurant.name)==restaurant_name.lower())
        )

        if not restaurant:
            await msg.reply_text(f'Restaurant with name {restaurant_name} not found')  # send message with information
            return None  # return None to not change state
        # ---------- END OF CHECKING FOR RESTAURANT IN DATABASE ----------

        # ---------- GETTING RESTAURANT SCHEDULE ----------
        stmt = (
            select(dbc.RestaurantSchedule)
                .join(dbc.RestaurantSchedule.restaurant)
                .where(dbc.Restaurant.id==restaurant.id)
                .order_by(dbc.RestaurantSchedule.day_of_week)
        )
        schedule = session.scalars(stmt).all()  # get schedule of the selected restaurant

        weekday_name = [
            'Monday', 'Tuesday', 'Wednesday',
            'Thursday', 'Friday', 'Saturday',
            'Sunday',
        ]  # list to convert int weekday to str
        
        txt = (
            f"Name: {restaurant.name}\n"
            f"Currency: {restaurant.currency}\n\n"
            f"Schedule:\n"
        )  # text for message
        for row in schedule:
            txt += (
                f"{weekday_name[row.day_of_week-1]}: "
                f"{row.start.hour:02}:{row.start.minute:02} "
                f"- {row.end.hour:02}:{row.end.minute:02}\n"
            )  # for every working day add to message text
        # ---------- END OF GETTING RESTAURANT SCHEDULE ----------

        kbrd = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="✅ enabled" if restaurant.enabled else "❌ disabled",
                        callback_data={
                            'value': '-CHANGE_RESTAURANT_STATUS-',
                            'restaurant_id': restaurant.id
                        }
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="Change schedule",
                        callback_data={
                            'value': '-CHANGE_RESTAURANT_SCHEDULE-',
                            'restaurant_id': restaurant.id
                        }
                    )
                ]
            ]
        )  # inline keyboard for message

        # ---------- GETTING RESTAURANT DISH CATEGORIES ----------
        stmt = (
            select(dbc.DishCategory.name)
                .join(dbc.Dish, onclause=(
                    dbc.Dish.dish_category_id==dbc.DishCategory.id
                ))
                .join(
                    dbc.Dish.restaurant
                )
                .where(dbc.Restaurant.id==restaurant.id)
                .group_by(dbc.DishCategory.name)
                .order_by(dbc.DishCategory.name)
        )
        categories = session.scalars(stmt).all()  # get all dish categories in the selected restaurant
        # ---------- END OF GETTING RESTAURANT DISH CATEGORIES ----------

        context.user_data['manage'] = {
            'restaurant_id': restaurant.id,
            'restaurant_name': restaurant.name,
            'dish_categories': categories  # to check next sent maeesage from user
        }
        
        await msg.reply_text(
            text=txt,
            reply_markup=kbrd
        )  # send message with restaurant information

        txt = 'Send dish category to view dishes'  # text for hint message
        kbrd = ReplyKeyboardMarkup([[category] for category in categories], True)  # keyboard for hint message

        await msg.reply_text(
            text=txt,
            reply_markup=kbrd
        )  # send hint message
    
    return bc.M_RESTAURANT  # return state for conversation handler

async def changeRestaurantStatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Changes restaurant visibility status'''
    query = update.callback_query  # shortcut for callback query
    u_usr = update.effective_user  # user from update
    restaurant_id = query.data['restaurant_id']  # get restaurant id from button

    with Session(dbc.engine) as session:
        # ---------- CHECKING IF UPDATE USER IS MANAGER ----------
        user_manager = session.scalar(
            select(dbc.User)
                .where(
                    (dbc.User.id==u_usr.id)
                    & (dbc.User.manager==True)
                )
        )

        if not user_manager:
            await query.answer('You are not manager', show_alert=True)  # notify of prohibited action
            return bc.END  # end conversation
        # ---------- END OF CHECKING IF UPDATE USER IS MANAGER ----------

        restaurant = session.scalar(
            select(dbc.Restaurant)
                .where(dbc.Restaurant.id==restaurant_id)
        )
        restaurant.enabled=not restaurant.enabled  # change to opposite
        session.commit()  # save changes

        if restaurant.enabled:
            await query.answer('Restaurant now can be seen to users', show_alert=True)
        else:
            await query.answer('Restaurant now cannot be seen to users', show_alert=True)

        kbrd = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="✅ enabled" if restaurant.enabled else "❌ disabled",
                        callback_data={
                            'value': '-CHANGE_RESTAURANT_STATUS-',
                            'restaurant_id': restaurant.id
                        }
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="Change schedule",
                        callback_data={
                            'value': '-CHANGE_RESTAURANT_SCHEDULE-',
                            'restaurant_id': restaurant.id
                        }
                    )
                ]
            ]
        )  # updated keyboard
    
    await query.edit_message_reply_markup(kbrd)  # update keyboard

    return None  # returning None to not change state

async def changeRestaurantSchedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Sends hint message'''
    await update.callback_query.answer()  # answer query
    user = update.effective_user  # user from update
    
    txt = (
        f"Send new schedule for {context.user_data['manage']['restaurant_name']} in single message:\n"
        'Day of the week (1-7) - Start Time (HH.MM) - End Time (HH.MM)\n\n'
        'Example:\n'
        '1 - 09.00 - 18.00\n'
        '2 - 09.00 - 00.00\n'
    )
    kbrd = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton('Cancel', callback_data={'value': '-CANCEL_SCHEDULE_CHANGE-'})
            ]
        ]
    )

    await user.send_message(txt, reply_markup=kbrd)  # send message
    return bc.M_RESTAURANT_SCHEDULE  # next state

async def cancelScheduleChange(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Returns manager back to restaurant state'''
    await update.callback_query.answer('Schedule change has been cancelled', show_alert=True)
    return bc.M_RESTAURANT

async def setRestaurantSchedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Set sent schedule for restaurant in current restaurant from context data'''
    msg = update.message  # shortcut for message
    u_usr = update.effective_user  # get user from update

    # ---------- CREATING SCHEDULE DICTIONARY ----------
    try:
        new_schedule = {}  # create dictionary for new schedule
        restaurant_id = context.user_data['manage']['restaurant_id']  # get restaurant id from context
        restaurant_name = context.user_data['manage']['restaurant_name']  # get restaurant name from context
        for st in msg.text.split('\n'):
            fields = st.replace(' ', '').split('-')
            assert len(fields) == 3  # each line of message must contain 3 values
            new_schedule[int(fields[0])] = (
                dt.time(*[int(x) for x in fields[1].split('.')]),  # start time
                dt.time(*[int(x) for x in fields[2].split('.')]),  # end time
              )  # add working day to dictionary

    except Exception as er:
        await msg.reply_text(
            (
                f"Error: {er}\n"
                "Try: Day of the week (1-7) - Start Time (HH.MM) - End Time (HH.MM)"
            )
        )
        return None  # return from function
    # ---------- END OF CREATING SCHEDULE DICTIONARY ----------

    # ---------- GETTING RESTAURANT SCHEDULE ----------
    with Session(dbc.engine) as session:
        # ---------- CHECKING IF UPDATE USER IS MANAGER ----------
        user_manager = session.scalar(
            select(dbc.User)
                .where(
                    (dbc.User.id==u_usr.id)
                    & (dbc.User.manager==True)
                )
        )

        if not user_manager:
            await msg.reply_text('You are not manager')  # notify of prohibited action
            return bc.END  # end conversation
        # ---------- END OF CHECKING IF UPDATE USER IS MANAGER ----------


        stmt = (
            select(dbc.RestaurantSchedule)
                .join(dbc.RestaurantSchedule.restaurant)
                .where(dbc.Restaurant.id==restaurant_id)
                .order_by(dbc.RestaurantSchedule.day_of_week)
        )
        schedule = session.scalars(stmt).all()  # get schedule of the selected restaurant

        existing_schdule = {}  # dictionary to store existing schedule
        for day in schedule:
            existing_schdule[day.day_of_week] = day  # add every working day to dictionary
    # ---------- END GETTING RESTAURANT SCHEDULE ----------
    
        for day in new_schedule:
            if existing_schdule.get(day):
                existing_schdule[day].start = new_schedule[day][0]  # update RestaurantSchedule instance
                existing_schdule[day].end = new_schedule[day][1]  # update RestaurantSchedule instance
                existing_schdule.pop(day)  # delete from dictionary
            else:
                new_day = dbc.RestaurantSchedule(
                    day_of_week=day,
                    start=new_schedule[day][0],
                    end=new_schedule[day][1],
                    restaurant_id=restaurant_id
                )  # create new instance of RestaurantSchedule
                session.add(new_day)  # add to session
        
        for day in existing_schdule:
            session.delete(existing_schdule[day])  # delete from DB RestaurantSchedule instances that are left in dictionary
        
        session.commit()  # save changes
    
    txt = 'Changes has been made. Update restaurant to view changes'  # text for message
    kbrd = ReplyKeyboardMarkup([[f"/restaurant {restaurant_name}"]], True)  # keyboard to request updated information of restaurant

    await msg.reply_text(txt, reply_markup=kbrd)  # send message
    return bc.M_RESTAURANT  # return manager back to 

async def showDish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message  # shortcut to use update message

    if msg.text not in context.user_data['manage']['dish_categories']:  # filter text here, because filters module doesn't have access to context
        return error.messageHandler(update, context)

    with Session(dbc.engine) as session:
        stmt = (
            select(dbc.Dish.id, dbc.Dish.name, dbc.Dish.file_id, dbc.Dish.price, dbc.Dish.description, dbc.Restaurant.currency, dbc.Dish.enabled)
                .join(dbc.Dish.restaurant)
                .join(dbc.Dish.dish_category)
                .where(dbc.Restaurant.id==context.user_data['manage']['restaurant_id'])
                .where(dbc.DishCategory.name==msg.text)
                .order_by(dbc.Dish.name)
        )
        dishes = session.execute(stmt).all()  # getting all dishes by selected restaurant and category
    
    for dish in dishes:  # for every dish send message with it
        kbrd = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="✅ enabled" if dish.enabled else "❌ disabled",
                        callback_data={
                            'value': '-CHANGE_DISH_STATUS-',
                            'dish_id': dish.id,
                            'enabled': dish.enabled
                        }
                    )
                ]
            ]
        )

        txt = (
            f"{dish.name}\n\n"
            f"{dish.description}\n\n"
            f"Price: {dish.price} {dish.currency}"
        )  # text for the message
        
        if dish.file_id:
            await msg.reply_photo(photo=dish.file_id, caption=txt, reply_markup=kbrd, disable_notification=True)  # send photo with caption if dish has file_id
        else:
            await msg.reply_text(txt, reply_markup=kbrd, disable_notification=True)  # send text message file_id is None
    return None  # returning None to not change the state

async def changeDishState(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Disables or enables dish'''
    query = update.callback_query  # shortcut for callback query
    u_usr = update.effective_user  # user from update
    dish_id = query.data['dish_id']
    dish_enabled = query.data['enabled']

    with Session(dbc.engine) as session:
        # ---------- CHECKING IF UPDATE USER IS MANAGER ----------
        user_manager = session.scalar(
            select(dbc.User)
                .where(
                    (dbc.User.id==u_usr.id)
                    & (dbc.User.manager==True)
                )
        )

        if not user_manager:
            await query.answer('You are not manager', show_alert=True)  # notify of prohibited action
            return bc.END  # end conversation
        # ---------- END OF CHECKING IF UPDATE USER IS MANAGER ----------

        dish = session.scalar(
            select(dbc.Dish)
                .where(dbc.Dish.id==dish_id)
        )
        dish.enabled = not dish.enabled  # change state

        session.commit()  # save changes

    kbrd = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text="✅ enabled" if not dish_enabled else "❌ disabled",
                    callback_data={
                        'value': '-CHANGE_DISH_STATUS-',
                        'dish_id': dish_id,
                        'enabled': not dish_enabled
                    }
                )
            ]
        ]
    )
    await query.edit_message_reply_markup(kbrd)  # update keyboard
    return None  # not changing state

async def createNewRestaurant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Starts process of creating new restaurant in DB'''
    msg = update.message  # shortcut for message
    u_usr = update.effective_user  # user from update

    with Session(dbc.engine) as session:
        # ---------- CHECKING IF UPDATE USER IS MANAGER ----------
        user_manager = session.scalar(
            select(dbc.User)
                .where(
                    (dbc.User.id==u_usr.id)
                    & (dbc.User.manager==True)
                )
        )

        if not user_manager:
            await msg.reply_text('You are not manager')  # notify of prohibited action
            return bc.END  # end conversation
        # ---------- END OF CHECKING IF UPDATE USER IS MANAGER ----------

    context.user_data.clear()  # clear manager's dictionary 
    await msg.reply_text(
        (
            'New Restaurant:\n\n'
            '-> Name:\n'
            'Currency:\n'
            'Schedule:\n\n'
            'Send name of the new restaurant'
        ),
        reply_markup=ReplyKeyboardRemove()
    )  # send message

    return bc.N_RESTAURANT  # next state for conversation handler

async def nameNewRestaurant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Sets name for new restaurant'''
    msg = update.message  # shortcut for message

    if len(msg.text) > dbc.Restaurant.name.type.length:
        await msg.reply_text('Name is too long')
        return None  # not changing state

    # ---------- CHECK IF NAME EXISTS IN DB ----------
    with Session(dbc.engine) as session:
        existing_restaurant = session.scalar(
            select(dbc.Restaurant)
                .where(func.lower(dbc.Restaurant.name)==msg.text.lower())
        )
        if existing_restaurant:
            await msg.reply_text('Restaurant under this name already exists')
            return None  # not changing state
    # ---------- END OF CHECK IF NAME EXISTS IN DB ----------

    context.user_data['manage'] = {
        'new_restaurant': {
            'restaurant_name': msg.text
        }
    }

    txt = (
        "New Restaurant:\n\n"
        f"Name: {msg.text}\n"
        '-> Currency:\n'
        'Schedule:\n\n'
        "Send restaurant currency (will be set for all dishes of this restaurant)"
    )

    await msg.reply_text(txt)  # send message
    return bc.C_RESTAURANT  # return next state

async def currencyNewRestaurant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Sets currency for new restaurant'''
    msg = update.message  # shortcut for message

    if len(msg.text) > dbc.Restaurant.currency.type.length:
        await msg.reply_text('Name is too long')
        return None  # not changing state

    context.user_data['manage']['new_restaurant']['currency'] = msg.text

    txt = (
        "New Restaurant:\n\n"
        f"Name: {context.user_data['manage']['new_restaurant']['restaurant_name']}\n"
        f"Currency: {msg.text}\n"
        '-> Schedule:\n\n'
        "Send restaurant schedule in single message to complete creation:\n"
        'Day of the week (1-7) - Start Time (HH.MM) - End Time (HH.MM)\n\n'
        'Example:\n'
        '1 - 09.00 - 18.00\n'
        '2 - 09.00 - 00.00\n'
    )

    await msg.reply_text(txt)  # send message
    return bc.S_RESTAURANT  # return next state

async def scheduleNewRestaurant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Sets schedule for new restaurant and creates it in database'''
    msg = update.message  # shortcut for message
    u_usr = update.effective_user  # get user from update

    # ---------- CREATING SCHEDULE DICTIONARY ----------
    try:
        new_schedule = {}  # create dictionary for new schedule
        for st in msg.text.split('\n'):
            fields = st.replace(' ', '').split('-')
            assert len(fields) == 3  # each line of message must contain 3 values
            new_schedule[int(fields[0])] = (
                dt.time(*[int(x) for x in fields[1].split('.')]),  # start time
                dt.time(*[int(x) for x in fields[2].split('.')]),  # end time
              )  # add working day to dictionary

    except Exception as er:
        await msg.reply_text(
            (
                f"Error: {er}\n"
                "Try: Day of the week (1-7) - Start Time (HH.MM) - End Time (HH.MM)"
            )
        )
        return None  # return from function
    # ---------- END OF CREATING SCHEDULE DICTIONARY ----------

    with Session(dbc.engine) as session:
        user_manager = session.scalar(
            select(dbc.User)
                .where(
                    (dbc.User.id==u_usr.id)
                    & (dbc.User.manager==True)
                )
        )

        if not user_manager:
            await msg.reply_text('You are not manager')  # notify of prohibited action
            return bc.END  # end conversation
        
        new_restaurant = dbc.Restaurant(
            name=context.user_data['manage']['new_restaurant']['restaurant_name'],
            currency=context.user_data['manage']['new_restaurant']['currency']
        )  # create new Restaurant instance
        session.add(new_restaurant)  # add to session
        session.flush()
        session.refresh(new_restaurant)  # refresh to get id

        for day in new_schedule:
            new_day = dbc.RestaurantSchedule(
                restaurant_id=new_restaurant.id,
                day_of_week=day,
                start=new_schedule[day][0],
                end=new_schedule[day][1]
            )  # create new RestaurantSchedule instance
            session.add(new_day)  # add to session
        
        session.commit()

    txt = (
        f"New restaurant {context.user_data['manage']['new_restaurant']['restaurant_name']} has been created successfully\n"
        'By default, all new restaurants are disabled and cannot be seen by users\n\n'
        'Please, choose next action'
    )  # text for message

    kbrd = ReplyKeyboardMarkup(
        [
            [f"/restaurant {context.user_data['manage']['new_restaurant']['restaurant_name']}"],
            ['/new_category'],
            ['/new_dish'],
        ]
    )  # keyboard for user

    await msg.reply_text(txt, reply_markup=kbrd)  # send message
    return bc.END  # end conversation

async def createNewDishCategory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Starts creation of new DishCategory'''
    msg = update.message  # shortcut for message
    u_usr = update.effective_user  # user of update

    with Session(dbc.engine) as session:
        # ---------- CHECKING IF UPDATE USER IS MANAGER ----------
        user_manager = session.scalar(
            select(dbc.User)
                .where(
                    (dbc.User.id==u_usr.id)
                    & (dbc.User.manager==True)
                )
        )

        if not user_manager:
            await msg.reply_text('You are not manager')  # notify of prohibited action
            return bc.END  # end conversation
        # ---------- END OF CHECKING IF UPDATE USER IS MANAGER ----------

    context.user_data.clear()  # clear manager's dictionary 
    await msg.reply_text(
        (
            'New Dish Category:\n\n'
            '-> Name:\n\n'
            'Send name of the new dish category (e.g. Burgers 🍔)'
        ),
        reply_markup=ReplyKeyboardRemove()
    )  # send message

    return bc.N_CATEGORY  # next state for conversation handler

async def nameNewDishCategory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Creates new Dish Category in DB'''
    msg = update.message  # shortcut for message
    u_usr = update.effective_user  # user of update

    if len(msg.text) > dbc.DishCategory.name.type.length:
        await msg.reply_text('Name is too long')
        return None  # not changing state

    with Session(dbc.engine) as session:
        # ---------- CHECKING IF UPDATE USER IS MANAGER ----------
        user_manager = session.scalar(
            select(dbc.User)
                .where(
                    (dbc.User.id==u_usr.id)
                    & (dbc.User.manager==True)
                )
        )

        if not user_manager:
            await msg.reply_text('You are not manager')  # notify of prohibited action
            return bc.END  # end conversation
        # ---------- END OF CHECKING IF UPDATE USER IS MANAGER ----------

        existing_category = session.scalar(
            select(dbc.DishCategory)
                .where(
                    func.lower(dbc.DishCategory.name)==msg.text
                )
        )
        if existing_category:
            await msg.reply_text(
                'Dish Category under this name already exists'
            )  # send message
            return None # not changing state
        
        new_dish_category = dbc.DishCategory(
            name=msg.text
        )  # create new DishCategory instance
        session.add(new_dish_category)  # add to session
        session.commit()  # save changes
    
    txt = (
        f"New dish category with name {msg.text} has been successfully created"
    )  # text for message
    kbrd = ReplyKeyboardMarkup(
        [
            [
                '/new_dish'
            ]
        ],
        True
    )  # keyboard with suggestions
    await msg.reply_text(txt, reply_markup=kbrd)  # send message
    return bc.END  # end conversation

async def createNewDish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Starts process of Dish creation'''
    msg = update.message  # shortcut for message
    u_usr = update.effective_user  # user from update

    with Session(dbc.engine) as session:
        # ---------- CHECKING IF UPDATE USER IS MANAGER ----------
        user_manager = session.scalar(
            select(dbc.User)
                .where(
                    (dbc.User.id==u_usr.id)
                    & (dbc.User.manager==True)
                )
        )

        if not user_manager:
            await msg.reply_text('You are not manager')  # notify of prohibited action
            return bc.END  # end conversation
        # ---------- END OF CHECKING IF UPDATE USER IS MANAGER ----------

        restaurants = session.scalars(
            select(dbc.Restaurant.name)
                .order_by(dbc.Restaurant.name)
        ).all()  # get all restaurants

        txt = (
            'New Dish:\n\n'
            '-> Restaurant:\n'
            'Category:\n'
            'Name:\n'
            'Description:\n'
            'Price:\n'
            'Photo:\n\n'
            'Select restaurant for new dish'
        )
        kbrd = ReplyKeyboardMarkup([[restaurant_name] for restaurant_name in restaurants])  # create keyboard with all restaurants
    context.user_data.clear()  # clear context dictionary
    await msg.reply_text(txt, reply_markup=kbrd)  # send message
    return bc.R_DISH  # return next state

async def restaurantNewDish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Sets restaurant for new dish'''
    msg = update.message  # shortcut for message

    with Session(dbc.engine) as session:
        restaurant = session.scalar(
            select(dbc.Restaurant)
                .where(
                    func.lower(dbc.Restaurant.name)==msg.text.lower()
                )
        )

        if not restaurant:
            await msg.reply_text(
                f"Restaurant with name {msg.text} has not been found"
            )
            return None  # not changing state
        
        context.user_data['manage'] = {
            'new_dish': {
                'restaurant_name': restaurant.name,
                'currency': restaurant.currency
            }
        }  # save to manager's dictionary

        categories = session.scalars(
            select(dbc.DishCategory.name)
                .order_by(dbc.DishCategory.name)
        ).all()  # get all categories

        txt = (
            'New Dish:\n\n'
            f'Restaurant: {restaurant.name}\n'
            '-> Category:\n'
            'Name:\n'
            'Description:\n'
            f'Price: {restaurant.currency}\n'
            'Photo:\n\n'
            'Select category for new dish'
        )
        kbrd = ReplyKeyboardMarkup([[category_name] for category_name in categories])  # create keyboard with all categories

    await msg.reply_text(txt, reply_markup=kbrd)  # send message
    return bc.C_DISH  # next state

async def categoryNewDish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Sets category for new dish'''
    msg = update.message  # shortcut for message

    with Session(dbc.engine) as session:
        category = session.scalar(
            select(dbc.DishCategory)
                .where(
                    func.lower(dbc.DishCategory.name)==msg.text.lower()
                )
        )

        if not category:
            await msg.reply_text(
                f"Category with name {msg.text} has not been found"
            )
            return None  # not changing state
        
        context.user_data['manage']['new_dish']['category_name'] = category.name  # save to manager's dictionary

    txt = (
        'New Dish:\n\n'
        f"Restaurant: {context.user_data['manage']['new_dish']['restaurant_name']}\n"
        f"Category: {msg.text}\n"
        '-> Name:\n'
        'Description:\n'
        f"Price: {context.user_data['manage']['new_dish']['currency']}\n"
        'Photo:\n\n'
        'Send name for new dish'
    )
    kbrd = ReplyKeyboardRemove()

    await msg.reply_text(txt, reply_markup=kbrd)  # send message
    return bc.N_DISH  # next state

async def nameNewDish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Sets name for new dish'''
    msg = update.message  # shortcut for message

    if len(msg.text) > dbc.Dish.name.type.length:
        await msg.reply_text('Name is too long')
        return None  # not changing state

    context.user_data['manage']['new_dish']['name'] = msg.text  # save to manager's dictionary

    txt = (
        'New Dish:\n\n'
        f"Restaurant: {context.user_data['manage']['new_dish']['restaurant_name']}\n"
        f"Category: {context.user_data['manage']['new_dish']['category_name']}\n"
        f"Name: {msg.text}\n"
        '-> Description:\n'
        f"Price: {context.user_data['manage']['new_dish']['currency']}\n"
        'Photo:\n\n'
        'Send description for new dish'
    )

    await msg.reply_text(txt)  # send message
    return bc.D_DISH  # next state

async def descriptionNewDish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Sets description for new dish'''
    msg = update.message  # shortcut for message

    if len(msg.text) > dbc.Dish.description.type.length:
        await msg.reply_text('Description is too long')
        return None  # not changing state
    
    context.user_data['manage']['new_dish']['description'] = msg.text  # save to manager's dictionary

    txt = (
        'New Dish:\n\n'
        f"Restaurant: {context.user_data['manage']['new_dish']['restaurant_name']}\n"
        f"Category: {context.user_data['manage']['new_dish']['category_name']}\n"
        f"Name: {context.user_data['manage']['new_dish']['name']}\n"
        f"Description: {msg.text}\n"
        f"-> Price: {context.user_data['manage']['new_dish']['currency']}\n"
        'Photo:\n\n'
        'Send price for new dish (e.g. 12.50, 12)'
    )

    await msg.reply_text(txt)  # send message
    return bc.PR_DISH  # next state

async def priceNewDish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Sets price for new dish'''
    msg = update.message  # shortcut for message
    
    try:
        price = float(msg.text)
    except Exception as er:
        await msg.reply_text(
            f"Error: {er}\nTry: XX.XX or XX"
        )
        return None  # not changing state

    context.user_data['manage']['new_dish']['price'] = price  # save to manager's dictionary

    txt = (
        'New Dish:\n\n'
        f"Restaurant: {context.user_data['manage']['new_dish']['restaurant_name']}\n"
        f"Category: {context.user_data['manage']['new_dish']['category_name']}\n"
        f"Name: {context.user_data['manage']['new_dish']['name']}\n"
        f"Description: {msg.text}\n"
        f"Price: {msg.text} {context.user_data['manage']['new_dish']['currency']}\n"
        '-> Photo:\n\n'
        'To complete creation send single photo for new dish or "No" to leave empty'
    )
    kbrd = ReplyKeyboardMarkup([['No']], True)

    await msg.reply_text(txt, reply_markup=kbrd)  # send message
    return bc.PH_DISH  # next state

async def photoNewDish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Sets photo for new dish'''
    msg = update.message  # shortcut for message

    print(msg.text)

    if msg.text and msg.text=='No':
        file_id=None
    else:
        file_id = msg.photo[0].file_id  # get file id from sent photo

    with Session(dbc.engine) as session:
        restaurant = session.scalar(
            select(dbc.Restaurant)
                .where(dbc.Restaurant.name==context.user_data['manage']['new_dish']['restaurant_name'])
        )
        category = session.scalar(
            select(dbc.DishCategory)
                .where(dbc.DishCategory.name==context.user_data['manage']['new_dish']['category_name'])
        )

        new_dish = dbc.Dish(
            name=context.user_data['manage']['new_dish']['name'],
            restaurant_id=restaurant.id,
            dish_category_id=category.id,
            description=context.user_data['manage']['new_dish']['description'],
            file_id=file_id,
            price=context.user_data['manage']['new_dish']['price']
        )
        
        session.add(new_dish)
        session.commit()
    
    txt = f"Dish {context.user_data['manage']['new_dish']['name']} has been created successfully\n"
    kbrd = ReplyKeyboardMarkup(
        [
            ['/new_dish'],
            ['/new_category'],
            [f"/restaurant {context.user_data['manage']['new_dish']['restaurant_name']}"]
        ],
        True
    )
    await msg.reply_text(txt, reply_markup=kbrd)  # send message
    return bc.END  # end conversation