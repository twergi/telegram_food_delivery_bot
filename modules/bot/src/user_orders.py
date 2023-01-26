import io
import tempfile

import tabulate
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes

from modules.bot import config as bc
from modules.database import config as dbc
from utils import constants as uc
from utils import text as ut
from utils import utility as uu


txt_dct = ut.messages  # dictionary of message texts
USER_ORDERS_KEYBOARD: list = [
    [txt_dct['back_to_menu']],
]

font_size = uc.FONT_SIZE  # get font size
fnt = ImageFont.truetype(uc.FONT_PATH, font_size)  # set font for PIL
many_ordrs_hdr = ['Order Number', 'Date', 'Status', 'Total Price']  # create header for the table with many orders
single_ordr_hdr = ['Name', 'Quantity', 'Price']  # create header for the table with one order description

def create_image(table: str):
    '''Returns image in bytes with table content on it'''
    table_rows = table.split('\n')  # split to get number of rows, width of text in pixels
    l  = int(fnt.getlength(table_rows[1]))  # get width of longest line in pixels
    img = Image.new('1', (l+40, (font_size*len(table_rows))+40), 1)  # create blank image
    d_img = ImageDraw.Draw(img)  # create object to draw on
    d_img.text((20,20), table, font=fnt)  # input text on image

    byte_arr = io.BytesIO()
    img.save(byte_arr, 'png')

    return byte_arr.getvalue()  # return bytes

async def showOrders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Sends user information with current and previous orders'''
    user = update.effective_user  # shortcut for user

    current_orders = []  # list for in-work orders
    past_orders = []  # list for orders that were completed or cancelled

    with Session(dbc.engine) as session:
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
                .where(dbc.Order.user_id==user.id)
                .order_by(dbc.Order.date_ordered.desc())  # order orders descending
        )
        orders = session.execute(stmt).all()
    
    if not orders:  # if user haven't made any orders
        txt = txt_dct['no_past_orders']  # text that user haven't made any orders
        await user.send_message(txt)  # send message to user

        return None  # do not change current state

    orders_id = []  # list of ids for user's keyboard

    for row in orders:  # else if user has orders
        order_date = row[1].astimezone(uc.PLACE_TIMEZONE)  # convert timezone from UTC to local
        row = [
            f"{row[0]:02}",  # id
            f"{order_date.hour:02}:{order_date.minute:02} {order_date.day:02}.{order_date.month:02}.{order_date.year:04}",  # time and date
            row[2],  # status
            f"{row[3]} {row[4]}"  # total price
        ]  # refactor row

        if row[2] in uc.ORDER_STATUSES[-2:]:  # if order is cancelled or completed
            past_orders.append(row)  # append to past orders
        else:
            current_orders.append(row)  # append to current
        orders_id.append(str(row[0]))  # add id to list

    if past_orders:  # if user has past orders
        txt = f"{txt_dct['past_orders']}\n\n"  # create text for past orders message
        table = tabulate.tabulate(past_orders, headers=many_ordrs_hdr)  # create beautiful table for orders

        if len(past_orders) > 10:  # if there are too much for single message
            tmp_file = tempfile.NamedTemporaryFile(suffix='.txt')  # create temporary file to be sent
            tmp_file.write(table.encode('utf-8'))  # add table to the file
            tmp_file.seek(0)

            await user.send_document(tmp_file, txt)  # send file
        
        else:
            table_bytes = create_image(table)  # convert text table to image
        
            await user.send_photo(table_bytes, caption=txt)  # send message with photo
    
    if current_orders:
        txt = f"{txt_dct['current_orders']}\n\n"  # create text for current orders message
        table = tabulate.tabulate(current_orders, headers=many_ordrs_hdr)  # create beautiful table for orders
        
        table_bytes = create_image(table)  # convert text table to image
        
        await user.send_photo(table_bytes, caption=txt)  # send message with photo

    txt = txt_dct['enter_order']  # text for message
    kbrd = ReplyKeyboardMarkup(
        USER_ORDERS_KEYBOARD
        + uu.list_split(orders_id, 3),  # add list of orders
        True  #  resize keyboard
    )  # keyboard for the message

    await user.send_message(txt, reply_markup=kbrd)  # send message

    return bc.USER_ORDERS  # return next state for conversation handler

async def showSingleOrder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Sends message with single order description'''
    msg = update.message  # shortcut to use update message
    user = update.effective_user  # shortcut for user

    with Session(dbc.engine) as session:
        stmt = (
            select(dbc.Order)
                .where(
                    (dbc.Order.user_id==user.id)  # update user must be the one who ordered
                    & (dbc.Order.id==int(msg.text))  # message text is order number
                )
        )
        order = session.scalar(stmt)  # try to get order
        
        # Not closing session to get all data from order

        if not order:  # no order found
            txt = txt_dct['order_not_found']  # create text for message

            await msg.reply_text(txt)  # send message
            return None  # None to not change state
        
        restaurant = order.cart_dish[0].dish.restaurant

        txt = msg.text  # caption for message

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
            f"\n\nOrder Number: {msg.text}\n"
            f"Restaurant: {restaurant.name}\n"
            f"Status: {order.status.name}\n"
            f"Order Date: {order_date.hour:02}:{order_date.minute:02} "
            f"{order_date.day:02}.{order_date.month:02}.{order_date.year:04}"
        )

        # Session now may be closed

    table_bytes = create_image(table)  # create image in bytes

    await user.send_photo(table_bytes, caption=txt)  # send message with photo
    return None  # return None to not change the state
        