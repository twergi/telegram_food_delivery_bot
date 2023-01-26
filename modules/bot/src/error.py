import html
import json
import logging
import traceback

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from utils import constants as uc
from utils import text as ut


txt_dct = ut.messages  # dictionary of message texts

async def messageHandler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message  # shortcut to use update message

    await msg.reply_text(txt_dct['message_not_recognized'])  # send message to user that message is not recognized

async def invalidCallbackDataHandler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Notifies user of broken keyboard and deletes it'''
    query = update.callback_query  # shortcut for callback query

    await query.answer(txt_dct['keyboard_unavailable'], True)  # notify user
    await query.edit_message_reply_markup(None)  # delete invalid keyboard
    return None  # not changing state

async def uncatchedCallbackHandler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Answers uncatched callback and notifies user of wrong state'''
    query = update.callback_query  # shortcut for callback query

    await query.answer(txt_dct['uncatched_callback'], True)  # Notify user
    return None  # not changing state

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log the error and send a telegram message to notify the developer."""
    # Log the error before we do anything else, so we can see it even if something breaks.
    logger = logging.getLogger(__name__)
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

    # traceback.format_exception returns the usual python message about an exception, but as a
    # list of strings rather than a single string, so we have to join them together.
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)

    # Build the message with some markup and additional information about what happened.
    # You might need to add some logic to deal with messages longer than the 4096 character limit.
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        f"An exception was raised while handling an update\n"
        f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
        "</pre>\n\n"
    )
    await context.bot.send_message(
        chat_id=uc.DEVELOPER_ID, text=message, parse_mode=ParseMode.HTML
    )

    message = (
        f"Chat data\n"
        f"<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n"
    )
    await context.bot.send_message(
        chat_id=uc.DEVELOPER_ID, text=message, parse_mode=ParseMode.HTML
    )

    message = (
        f"User data\n"
        f"<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n"
    )
    await context.bot.send_message(
        chat_id=uc.DEVELOPER_ID, text=message, parse_mode=ParseMode.HTML
    )

    message = (
        f"Traceback\n"
        f"<pre>{html.escape(tb_string)}</pre>"
    )
    await context.bot.send_message(
        chat_id=uc.DEVELOPER_ID, text=message, parse_mode=ParseMode.HTML
    )