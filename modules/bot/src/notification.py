import tabulate
from sqlalchemy import select
from sqlalchemy.orm import Session
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from modules.bot.src import user_orders
from modules.database import config as dbc
from utils import constants as uc

single_ordr_hdr = ['Name', 'Quantity', 'Price']  # create header for the table with one order description

async def sendOrderRequest(update: Update, order_id: int):
    '''Sends order request in the notification chat'''
    msg = update.message  # shortcut for message

    with Session(dbc.engine) as session:
        stmt = (
            select(dbc.Order)
                .where(
                    dbc.Order.id==order_id  # message text is order number
                )
        )
        order = session.scalar(stmt)  # get order instance
        location = [float(value) for value in order.location.split(',')]  # get order delivery location
        restaurant = order.cart_dish[0].dish.restaurant  # get restaurant instance

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
            f"\n\nOrder Number: {order_id}\n"
            f"Restaurant: {restaurant.name}\n"
            f"Status: {order.status.name}\n"
            f"Order Date: {order_date.hour:02}:{order_date.minute:02} "
            f"{order_date.day:02}.{order_date.month:02}.{order_date.year:04}"
        )

    table_bytes = user_orders.create_image(table)  # create image in bytes

    kbrd = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text='✅ Confirm',
                    callback_data={
                        'value': '-ORDER_CONFIRM-',
                        'order_id': order_id
                    }
                ),
                InlineKeyboardButton(
                    text='❌ Cancel',
                    callback_data={
                        'value': '-ORDER_CANCEL-',
                        'order_id': order_id
                    }
                ),
            ],
            [
                InlineKeyboardButton(
                    text='Chat with user',
                    url=f"tg://user?id={update.effective_user.id}"
                )
            ]
        ]
    )  # crate keyboard to respond on order request

    try:
        bot_in_chat = await update._bot.get_chat_member(uc.CHAT_ID, update._bot.id)  # try to get bot in chat to ensure that he can send message
        if bot_in_chat:  # if bot is in chat
            chat_id = uc.CHAT_ID  # set target chat
        else:  # if bot is not found in chat
            chat_id = uc.DEVELOPER_ID  # set target chat
            await update._bot.send_message(
                chat_id=uc.DEVELOPER_ID,
                text='Bot not found in chat'
            )  # send error to developer
    except Exception as er:
        chat_id = uc.DEVELOPER_ID  # set target chat
        await update._bot.send_message(
            chat_id=uc.DEVELOPER_ID,
            text=str(er)
        )  # send error to developer

    await update._bot.send_photo(
        chat_id,
        photo=table_bytes,
        caption=(
            f"Order Number: {order_id}\n"
            "Location:"
        ),
        reply_markup=kbrd
    )  # send message with photo
    await update._bot.send_location(
        chat_id,
        latitude=location[0],
        longitude=location[1]
    )  # send delivery location

    return None

async def requestButton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Confirms or cancels order'''
    query = update.callback_query  # shortcut for callback query
    order_id = query.data['order_id']  # get order id from query
    user = update.effective_user  # get user from update

    if query.data['value'] == '-ORDER_CONFIRM-':
        new_status_name = uc.ORDER_STATUSES[1]  # get status name from list
        btn_txt = f"Open user\n✅ {new_status_name}"  # create text for button
    elif query.data['value'] == '-ORDER_CANCEL-':
        new_status_name = uc.ORDER_STATUSES[-1]  # get status name from list
        btn_txt = f"Open user\n❌ {new_status_name}"  # create text for button
    else:
        raise Exception('Order request managing unknown value')
    
    with Session(dbc.engine) as session:
        user_manager = session.scalar(
            select(dbc.User)
                .where(
                    (dbc.User.id==user.id)
                    & (dbc.User.manager==True)
                )
        )  # check if update user is manager by getting from DB

        if not user_manager:
            await query.answer('You are not manager', show_alert=True)  # notify pressed button person
            return None  # return from function without changing

        new_status = session.scalar(
            select(dbc.Status)
                .where(dbc.Status.name==new_status_name)
        )  # get status

        order = session.scalar(
            select(dbc.Order)
                .where(dbc.Order.id==order_id)
        )  # get order
        order.status_id = new_status.id  # set new status
        order.manager_id = user.id  # set manager for order
        user_id = order.user_id # get user_id from order

        session.commit()  # save changes
    
    kbrd = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(btn_txt, url=f"tg://user?id={user_id}")
            ]
        ]
    )

    await query.edit_message_reply_markup(kbrd)  # edit keyboard for request message
    return None  # return from function without changing
