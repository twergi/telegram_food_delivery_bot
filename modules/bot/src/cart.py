from telegram import (InlineKeyboardButton, InlineKeyboardMarkup,
                      ReplyKeyboardMarkup, Update)
from telegram.ext import ContextTypes

from modules.bot import config as bc
from modules.bot.src import lobby
from utils import text as ut


txt_dct = ut.messages  # dictionary of message texts
CART_KEYBOARD: list = [
    [txt_dct['empty_the_cart']],
    [txt_dct['back_to_menu'], txt_dct['place_order']]
]

async def showCart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Replies with current cart'''
    user = update.effective_user  # shortcut for user of update
    
    if (
        not context.user_data.get('cart')  # if cart is not created
        or context.user_data['cart']['dishes'] == {}  # if cart is empty
    ):
        await user.send_message(txt_dct['cart_is_empty'])
        return None  # return None to not change the state

    restaurant_name = context.user_data['cart']['restaurant_name']  # get selected restaurant_name
    dishes = context.user_data['cart']['dishes']  # get dishes dictionary
    currency = context.user_data['cart']['currency']  # get currency

    cart_sum = 0  # create cart price
    txt = (
        f"{txt_dct['cart']}\n\n"
        f"{restaurant_name}:\n"
    )  # create text for message
    for dish_id in dishes:  # add line for each dish in cart
        txt += (
            f"{dishes[dish_id]['dish_name']} x{dishes[dish_id]['quantity']}: "
            f"{dishes[dish_id]['dish_price']*dishes[dish_id]['quantity']} {currency}\n"
        )
        cart_sum += dishes[dish_id]['dish_price'] * dishes[dish_id]['quantity']  # add dish price to cart price

    txt += f"\n{cart_sum} {currency}"  # add last line with cart price
    kbrd = ReplyKeyboardMarkup(CART_KEYBOARD, True)  # navigation keyboard

    await user.send_message(txt, reply_markup=kbrd)  # send message with cart

    txt = txt_dct['select_dish_to_change']  # text for the change message
    kbrd = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(text=dishes[dish_id]['dish_name'], callback_data={
                    'value': '-QUANTITY_CHANGE-',
                    'dish_id': dish_id,
                    'dish_name': dishes[dish_id]['dish_name'],
                    'quantity': dishes[dish_id]['quantity']
                })
            ] for dish_id in dishes
        ]
    )  # create Inline Keyboard for the change message

    await user.send_message(txt, reply_markup=kbrd)  # send messge with cart customization

    return bc.CART  # returning next state

async def changeDish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query  # shortcut for callback query

    txt = f"{query.data['dish_name']} x{query.data['quantity']}"
    kbrd = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton('-', callback_data={
                    'value': '-QUANTITY_MINUS-',
                    'dish_id': query.data['dish_id'],
                    'dish_name': query.data['dish_name'],
                    'quantity': (
                        (query.data['quantity'] - 1) if query.data['quantity'] - 1 >= 0 else query.data['quantity']  # check lower boundary
                    )  # passing new value
                }),
                InlineKeyboardButton('+', callback_data={
                    'value': '-QUANTITY_PLUS-',
                    'dish_id': query.data['dish_id'],
                    'dish_name': query.data['dish_name'],
                    'quantity': (
                        (query.data['quantity'] + 1) if query.data['quantity'] + 1 <= 60 else query.data['quantity']  # check upper boundary
                        )  # passing new value
                })
            ],
            [
                InlineKeyboardButton('OK', callback_data={
                    'value': '-QUANTITY_OK-',
                    'dish_id': query.data['dish_id'],
                    'dish_name': query.data['dish_name'],
                    'quantity': query.data['quantity']
                })
            ]
        ]
    )

    await query.edit_message_text(txt, reply_markup=kbrd)  # edit message
    return None  # return None to not change the state

async def confirmChange(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query  # shortcut for callback query

    dish_id = query.data['dish_id']  # get dish id from callback data
    new_quantity = query.data['quantity']  # get new quantity from callback data

    if new_quantity == 0:
        context.user_data['cart']['dishes'].pop(dish_id)  # delete dish form cart if new quantity is 0

    else:
        context.user_data['cart']['dishes'][dish_id]['quantity'] = new_quantity  # set new quantity

    txt = txt_dct['cart_changed']  # text for edited message
    kbrd = None  # remove Inline Keyboard

    await query.answer()
    await query.edit_message_text(txt, reply_markup=kbrd)  # edit the message

    return await showCart(update, context)  # show cart again

async def emptyCart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message  # shortcut to use update message

    context.user_data['cart'] = {
        'dishes':{}
    }  # set empty dictionary for cart
    txt = txt_dct['cart_is_empty']  # text for the message
    kbrd = ReplyKeyboardMarkup(lobby.LOBBY_KEYBOARD, True)  # lobby keyboard

    await msg.reply_text(txt, reply_markup=kbrd)  # send message 
    return bc.LOBBY  # return next state for conversation handler