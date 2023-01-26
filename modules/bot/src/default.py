from sqlalchemy import select
from sqlalchemy.orm import Session
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import ContextTypes

from modules.bot import config as bc
from modules.bot.src import cart, lobby, order
from modules.database import config as dbc
from utils import text as ut


txt_dct = ut.messages  # dictionary of message texts

async def startHandler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message  # shortcut to use update message
    user = update.effective_user  # shortcut for user

    if user.is_bot:  # if message from bot, ignore it
        return

    #----------CHECKING USER IN DATABASE----------
    with Session(dbc.engine) as session:
        db_user = session.scalar(
            select(dbc.User)
                .where(dbc.User.id==user.id)
        )  # find user in database
        if not db_user:  # if user is None
            db_user = dbc.User(
                id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
            )  # create new user object
            session.add(db_user)  # add new user to session

            txt = txt_dct['welcome_message']  # text for welcome message
            await msg.reply_text(txt)  # send welcome message

        else:
            db_user.username = user.username  # update username
            db_user.first_name = user.first_name  # update first_name
            db_user.last_name = user.last_name  # update last_name
        session.commit()  # commit chages
    #----------END OF CHECKING USER IN DATABASE----------
    
    txt = txt_dct['input_value']  # text for action message
    kbrd = ReplyKeyboardMarkup(
        lobby.LOBBY_KEYBOARD
    )  # keyboard for user

    await msg.reply_text(txt, reply_markup=kbrd)  # send message 
    return bc.LOBBY  # return next state for conversation handler

async def navigationButton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Handles messages from static keyboards'''
    msg = update.message  # shortcut to use update message

    if msg.text == txt_dct['back_to_menu']:
        return await startHandler(update, context)  # return to lobby

    elif msg.text == txt_dct['cart']:
        return await cart.showCart(update, context)  # show cart

    elif msg.text == txt_dct['place_order']:
        return await order.startOrdering(update, context )  # start order process

    else:
        raise Exception('Navigation button unknown value')

async def cancelHandler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Ends conversation by command /cancel'''
    msg = update.message  # shortcut to use update message
    txt = txt_dct['come_again']  # text for message
    kbrd = ReplyKeyboardRemove()

    context.user_data.clear()  # clear user data

    await msg.reply_text(txt, reply_markup=kbrd)  # send message
    return bc.END  # end conversation

async def endConversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Ends conversation by another command'''
    context.user_data.clear()  # clear user data
    return bc.END  # end conversation

async def helpMessage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Sends help message'''
    user = update.effective_user  # get update user

    if user.is_bot:
        return  # ignore if bot
    
    txt = txt_dct['help_user'] # text for help message

    with Session(dbc.engine) as session:
        manager = session.scalar(
            select(dbc.User)
                .where(
                    (dbc.User.id==user.id)  # current user
                    & (dbc.User.manager==True)  # is manager
                )
        )
    
    await user.send_message(txt)  # send message with help for user

    if manager:
        txt = txt_dct['help_manager'] # text for next message
        await user.send_message(txt) # send message with help for manager
    
    return None