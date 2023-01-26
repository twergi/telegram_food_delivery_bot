from sqlalchemy import select
from sqlalchemy.orm import Session
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from modules.bot.src import error, restaurant
from modules.database import config as dbc
from utils import text as ut
from utils import utility as uu


txt_dct = ut.messages  # dictionary of message texts
DISH_KEYBOARD: list = [
    [txt_dct['place_order']],
    [txt_dct['back_to_restaurant'], txt_dct['cart']],
    [txt_dct['back_to_menu']]
]

def create_quantity_keyboard(callback_data: dict, max_value: int):
    '''Function to create keyboard for dish quantity selection'''
    _markup = uu.list_split(
        lst=[
            InlineKeyboardButton(
                text=str(i),
                callback_data={
                    **callback_data,
                    'value': '-QUANTITY-',
                    'quantity': i
                }
            ) for i in range(max_value-5, max_value+1)
        ],  # list to be transformed
        cols=3  # number of columns
    )  # create 3x2 grid with quantity selection
    
    _navigation = [[]]
    if max_value > 6:  # if max value <= 6, previous button is not needed
        _navigation[0].append(
            InlineKeyboardButton(
                text='<<',
                callback_data={
                    **callback_data,
                    'max_value': max_value,  # must be passed to calculate next page
                    'value': '-QUANTITY_BACK-'
                }
            )
        )
    if max_value < 60:  # if max value >= 60, next button is not needed
        _navigation[0].append(
            InlineKeyboardButton(
                text='>>',
                callback_data={
                    **callback_data,
                    'max_value': max_value,  # must be passed to calculate next page
                    'value': '-QUANTITY_NEXT-'
                }
            )
        )
    _markup += _navigation  # append third row to keyboard
    _markup += [
        [
            InlineKeyboardButton(
                text='Cancel dish',
                callback_data={
                    **callback_data,
                    'value': '-CANCEL-'
                }
            )
        ]
    ]  # last row with cancel button
    _kbrd = InlineKeyboardMarkup(_markup)
    return _kbrd

def create_add_keyboard(restaurant_name: str, dish_id: int, dish_name: str, dish_price: float, currency: str):
    '''Function to create add dish keyboard'''
    _kbrd = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton('Add', callback_data={
                'value': '-ADD-',
                'restaurant_name': restaurant_name,
                'dish_id': dish_id,
                'dish_name': dish_name,
                'dish_price': dish_price,
                'currency' : currency
            })]
        ]
    )
    return _kbrd

def create_selected_dish_keyboard(restaurant_name: str, dish_id: int, dish_name: str, dish_price: float, quantity: int, currency: str):
    '''Function to create keyboard for selected dish'''
    _kbrd = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"✅ {quantity*dish_price} (x{quantity}) {currency}", callback_data={
                'value': '-CHANGE-',
                'restaurant_name': restaurant_name,
                'dish_id': dish_id,
                'dish_name': dish_name,
                'dish_price': dish_price,
                'currency' : currency
            })]
        ]
    )
    return _kbrd

async def showDish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message  # shortcut to use update message

    if msg.text not in context.user_data['dish_categories']:  # filter text here, because filters module doesn't have access to context
        return error.messageHandler(update, context)
    
    with Session(dbc.engine) as session:
        stmt = (
            select(dbc.Dish.id, dbc.Dish.name, dbc.Dish.file_id, dbc.Dish.price, dbc.Dish.description, dbc.Restaurant.currency)
                .join(dbc.Dish.restaurant)
                .join(dbc.Dish.dish_category)
                .where(dbc.Dish.enabled==True)
                .where(dbc.Restaurant.name==context.user_data['restaurant_name'])
                .where(dbc.DishCategory.name==msg.text)
                .order_by(dbc.Dish.name)
        )
        dishes = session.execute(stmt).all()  # getting all dishes by selected restaurant and category
    
    restaurant_works = await restaurant.isRestaurantWorking(
        restaurant_name=context.user_data['restaurant_name']
    )

    for dish in dishes:  # for every dish send message with it
        kbrd = create_add_keyboard(
            context.user_data['restaurant_name'],
            dish.id,
            dish.name,
            dish.price,
            dish.currency
        ) if restaurant_works else None  # creating keyboard for the message, checking restaurant schedule

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

async def showQuantityButton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Handles pressed -ADD- and -CHANGE- button'''
    query = update.callback_query  # shortcut for callback query

    if (
        context.user_data['cart'].get('restaurant_name')
        and (
            query.data['restaurant_name'] != context.user_data['cart']['restaurant_name']
            and context.user_data['cart']['dishes'] != {}
        )  # user can proceed of he emptied his cart by himself (another restaurant_name still in the cart)
    ):  # if user switched restaurants with not empty cart
        txt = txt_dct['cart_another_restaurant']  # create message text
        kbrd = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(txt_dct['leave_the_cart'], callback_data={'value': '-LEAVE_CART-'})
                ],
                [
                    InlineKeyboardButton(txt_dct['empty_the_cart'], callback_data={'value': '-EMPTY_CART-'})
                ]
            ]
        )  # create the keyboard
        await query.answer()  # answer the query
        await query.from_user.send_message(txt, reply_markup=kbrd)  # send message
        return None  # returning None to not change the state

    callback_data = {
        'restaurant_name': query.data['restaurant_name'],
        'dish_id': query.data['dish_id'],
        'dish_name': query.data['dish_name'],
        'dish_price': query.data['dish_price'],
        'currency': query.data['currency']
    }  # callback query data that will be present in each button

    kbrd = create_quantity_keyboard(
        callback_data=callback_data,
        max_value=6  # maximum value for quantity selection
    )

    await query.answer()  # answer the query
    if query.message.text:
        txt = query.message.text  # get message text
        txt += f"\n\n{txt_dct['select_quantity']}:"  # add last line to dish message text
        await query.edit_message_text(text=txt, reply_markup=kbrd)  # edit dish message
    elif query.message.caption:
        txt = query.message.caption  # get message caption if it has photo
        txt += f"\n\n{txt_dct['select_quantity']}:"  # add last line to dish message text
        await query.edit_message_caption(caption=txt, reply_markup=kbrd)  # edit dish message

    return None  # return None to not change the state

async def cancelDishButton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Handles pressed -CANCEL- button in dish quantity'''
    query = update.callback_query  # shortcut for callback query

    (
        context.user_data['cart']['dishes'].get(query.data['dish_id'])
        and context.user_data['cart']['dishes'].pop(query.data['dish_id'])
    )  # pop dish id from cart if exists

    kbrd = create_add_keyboard(
        query.data['restaurant_name'],
        query.data['dish_id'],
        query.data['dish_name'],
        query.data['dish_price'],
        query.data['currency']
    )  # create keyboard for the message
    await query.answer()  # answer the query
    if query.message.text:
        txt = query.message.text[:-(len(txt_dct['select_quantity']) + 1)]  # delete 'select_quantity:' from the text
        await query.edit_message_text(text=txt, reply_markup=kbrd)  # change the message
    elif query.message.caption:
        txt = query.message.caption[:-(len(txt_dct['select_quantity']) + 1)]  # delete 'select_quantity:' from the text
        await query.edit_message_caption(caption=txt, reply_markup=kbrd)  # change the message

    return None  # return None to not change the state

async def changeQuantityPage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Handles pressed -QUANTITY_NEXT- or -QUANTITY_BACK- button in dish quantity'''

    query = update.callback_query  # shortcut for callback query
    is_back = query.data['value'] == '-QUANTITY_BACK-'  # determine which button is pressed
    max_value = query.data['max_value']  # get max quantity in keyboard

    callback_data = {
        'restaurant_name': query.data['restaurant_name'],
        'dish_id': query.data['dish_id'],
        'dish_name': query.data['dish_name'],
        'dish_price': query.data['dish_price'],
        'currency': query.data['currency']
    }  # callback query data that will be present in each button
    max_value += 6 - 12 * is_back  # maximum value for quantity selection

    kbrd = create_quantity_keyboard(
        callback_data,
        max_value
    )

    await query.answer()  # answer the query
    await query.edit_message_reply_markup(kbrd)  # edit keyboard
    return None  # return None to not change the state

async def selectQuantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Handles pressed -QUANTITY- button in dish quantity'''

    query = update.callback_query  # shortcut for callback query

    restaurant_name = query.data['restaurant_name']  # get selected restaurant_name
    dish_id = query.data['dish_id']  # get dish id
    dish_name = query.data['dish_name']  # get dish name
    dish_price = query.data['dish_price']  # get dish price
    quantity = query.data['quantity']  # get selected quantity
    currency = query.data['currency']  # get currency

    context.user_data['cart']['restaurant_name'] = restaurant_name  # set restaurant name
    context.user_data['cart']['currency'] = currency  # set currency

    context.user_data['cart']['dishes'][dish_id] = {
        'dish_name': dish_name,
        'dish_price': dish_price,
        'quantity': quantity
    }  # set selected dish data

    kbrd = create_selected_dish_keyboard(
        restaurant_name,
        dish_id,
        dish_name,
        dish_price,
        quantity,
        currency
    )  # create keyboard for the message

    await query.answer()  # answer the query
    if query.message.text:
        txt = query.message.text[:-(len(txt_dct['select_quantity']) + 1)]  # delete 'select_quantity:' from the text
        await query.edit_message_text(text=txt, reply_markup=kbrd)  # edit message
    elif query.message.caption:
        txt = query.message.caption[:-(len(txt_dct['select_quantity']) + 1)]  # delete 'select_quantity:' from the text
        await query.edit_message_caption(caption=txt, reply_markup=kbrd)  # edit message
    
    return None  # return None to not change the state

async def emptyCart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Empties the cart'''
    query = update.callback_query  # shortcut for callback query

    context.user_data['cart'] = {
        'dishes':{}
    }  # set empty dictionary for cart

    txt = txt_dct['cart_is_empty']  # text for the message
    kbrd = None  # delete keyboard

    await query.answer()  # answer the query
    await query.edit_message_text(txt, reply_markup=kbrd)  # edit message

    return None  # return None to not change the state

async def leaveCart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Leaves the cart'''
    query = update.callback_query  # shortcut for callback query

    txt = txt_dct['cart_not_changed']  # text for the message
    kbrd = None  # delete keyboard

    await query.answer()  # answer the query
    await query.edit_message_text(txt, reply_markup=kbrd)  # edit message

    return None  # return None to not change the state