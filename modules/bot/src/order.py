from sqlalchemy import select
from sqlalchemy.orm import Session
from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes

from modules.bot import config as bc
from modules.bot.src import cart, default, lobby, notification, restaurant
from modules.database import config as dbc
from utils import text as ut


txt_dct = ut.messages  # dictionary of message texts
ORDER_KEYBOARD: list = [
    [txt_dct['back_to_menu']],
]

async def startOrdering(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Function to check cart and ask user to proceed with ordering'''
    msg = update.message  # shortcut for message
    
    if (
        not context.user_data.get('cart')  # if cart is not created
        or context.user_data['cart']['dishes'] == {}  # if cart is empty
    ):
        await msg.reply_text(txt_dct['cart_is_empty'])
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

    txt += (
        f"\n{txt_dct['total_price']}: {cart_sum} {currency}\n\n"  # line with cart price
        f"{txt_dct['order_confirmation']}"
    )  # add last lines
    kbrd = ReplyKeyboardMarkup(ORDER_KEYBOARD, True)

    await msg.reply_text(txt, reply_markup=kbrd)  # send message with cart

    return bc.ORDER  # return next state

async def makeOrder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Function to get location and make create order in database'''
    msg = update.message  # shortcut for message
    user = update.effective_user  # get update user
    dishes = context.user_data['cart']['dishes']  # get dishes dictionary

    delivery_location = f"{msg.location.latitude},{msg.location.longitude}"  # get delivery location from message

    #----------SAVING ORDER TO THE DATABASE----------
    with Session(dbc.engine) as session:
        new_order = dbc.Order(
            location=delivery_location,
            user_id=user.id
        )  # create new order
        session.add(new_order)  # add new order to session
        session.flush()  #  flush session
        session.refresh(new_order)  # refresh new order to get its id in DB
        new_order_id = new_order.id
        
        dishes_db = session.scalars(
            select(dbc.Dish)
                .where(dbc.Dish.id.in_(dishes.keys()))
        )
    
        if not await restaurant.isRestaurantWorking(context.user_data['cart']['restaurant_name']):
            await msg.reply_text(txt_dct['cart_restaurant_closed'])  # notify that restaurant is now closed
            return await default.startHandler(update, context)  # redirect to lobby

        for dish in dishes_db:
            if not dish.enabled:
                await msg.reply_text(txt_dct['cart_irrelevant_items'])  # notify that cart contains irrelevant items
                return await cart.showCart(update, context)  # redirect to cart

            new_cart_dish = dbc.CartDish(
                quantity=dishes[dish.id]['quantity'],
                dish_id=dish.id,
                order_id=new_order_id
            )
            session.add(new_cart_dish)  # add cart_dish to session
        session.commit()  # commit changes
    #----------END OF SAVING ORDER TO THE DATABASE----------
    
    txt = (
        f"{txt_dct['order_completion']}\n\n"
        f"{txt_dct['order_number']}: {new_order_id}"
    )  # create text for confirmation message
    kbrd = ReplyKeyboardMarkup(lobby.LOBBY_KEYBOARD)  # keyboard for lobby

    await notification.sendOrderRequest(update, new_order_id)  # send oerder request message in the notification chat

    await msg.reply_text(txt, reply_markup=kbrd)  # send confirmation message to user

    context.user_data.clear()  # clear user data

    return bc.LOBBY  # return to lobby