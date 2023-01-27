import logging
import os

from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          ConversationHandler, InvalidCallbackData,
                          MessageHandler, filters)

from modules.bot.src import (cart, default, dish, error, lobby, manage_db,
                             notification, order, restaurant, user_orders)
from utils import text as ut


# Enable logging
logging.basicConfig(
    format='[%(levelname)s] %(asctime)s - %(name)s - %(message)s',
    level=logging.INFO
    )

# Token of telegram bot
TOKEN = os.environ.get('TOKEN')

# States for conversation
END = ConversationHandler.END
LOBBY, RESTAURANT, DISH, CART, ORDER, USER_ORDERS = range(6)  # states for user
M_USER, M_ORDER, M_RESTAURANT, M_RESTAURANT_SCHEDULE, N_RESTAURANT = range(6, 11)  # states for manager conversation
C_RESTAURANT, S_RESTAURANT, N_CATEGORY = range(11, 14)  # states for manager conversation
R_DISH, C_DISH, N_DISH, D_DISH, PR_DISH, PH_DISH = range(14, 20)  # states for manager conversation

def main():
    '''Run the bot'''
    application = (
        Application
            .builder()
            .token(TOKEN)
            .arbitrary_callback_data(True)
            .build()
    )

    fallbacks = [
        CommandHandler('cancel', default.cancelHandler),  # stops conversation
        MessageHandler(filters.COMMAND & ~filters.Text('/help'), default.endConversation),  # ends conversation if another command starts
        MessageHandler(~filters.COMMAND, error.messageHandler),  # message handler to notify user that text is not recognized
        CallbackQueryHandler(
            error.uncatchedCallbackHandler,
            pattern=lambda data: data['value'] not in ['-ORDER_CONFIRM-', '-ORDER_CANCEL-']
        )  # callback handler to catch all unanswered callbacks
    ]

    user_conversation = ConversationHandler(
        entry_points=[
            CommandHandler('start', default.startHandler)  # conversation starts by /start command
        ],
        states={
            LOBBY: [
                MessageHandler(
                    filters.Regex(ut.messages['choose_restaurant']),
                    lobby.showRestaurants
                ),
                MessageHandler(
                    filters.Regex(ut.messages['about_us']),
                    lobby.showAboutUs
                ),
                MessageHandler(
                    filters.Regex(ut.messages['my_orders']),
                    user_orders.showOrders
                ),
                MessageHandler(
                    filters.Text(
                        [
                            ut.messages['cart'],
                            ut.messages['place_order'],
                        ]
                    ),
                    default.navigationButton
                )
            ],
            RESTAURANT: [
                MessageHandler(
                    filters.Text(
                        [
                            ut.messages['place_order'],
                            ut.messages['cart'],
                            ut.messages['back_to_menu'],
                        ]
                    ),
                    default.navigationButton
                ),  # message handler for navigation
                MessageHandler(
                    restaurant.RestaurantFilter(),
                    restaurant.showDishCategories
                )  # message handler for restaurant selection
            ],
            DISH: [
                MessageHandler(
                    filters.Regex(ut.messages['back_to_restaurant']),
                    lobby.showRestaurants
                ),
                MessageHandler(
                    filters.Text(
                        [
                            ut.messages['place_order'],
                            ut.messages['cart'],
                            ut.messages['back_to_menu']
                        ]
                    ),
                    default.navigationButton
                ),  # message handler for navigation
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    dish.showDish
                ),  # message handler to show dishes of selected category
                CallbackQueryHandler(
                    dish.showQuantityButton,
                    pattern=lambda data: data.get('value') == '-ADD-' or data.get('value') == '-CHANGE-'
                ),  # query handler of dish -ADD- and -CHANGE- button
                CallbackQueryHandler(
                    dish.cancelDishButton,
                    pattern=lambda data: data.get('value') == '-CANCEL-'
                ),  # query handler of dish -CANCEL- button
                CallbackQueryHandler(
                    dish.changeQuantityPage,
                    pattern=lambda data: data.get('value') == '-QUANTITY_NEXT-' or data.get('value') == '-QUANTITY_BACK-'
                ),  # query handler of dish -QUANTITY_NEXT- or -QUANTITY_BACK- button
                CallbackQueryHandler(
                    dish.selectQuantity,
                    pattern=lambda data: data.get('value') == '-QUANTITY-'
                ),  # query handler of dish -QUANTITY- button
                CallbackQueryHandler(
                    dish.emptyCart,
                    pattern=lambda data: data.get('value') == '-EMPTY_CART-'
                ),  # query handler of dish -EMPTY_CART- button
                CallbackQueryHandler(
                    dish.leaveCart,
                    pattern=lambda data: data.get('value') == '-LEAVE_CART-'
                ),  # query handler of dish -LEAVE_CART- button
            ],
            CART: [
                MessageHandler(
                    filters.Regex(ut.messages['empty_the_cart']),
                    cart.emptyCart
                ),
                MessageHandler(
                    filters.Text(
                        [
                            ut.messages['place_order'],
                            ut.messages['back_to_menu']
                        ]
                    ),
                    default.navigationButton
                ),  # message handler for navigation
                CallbackQueryHandler(
                    cart.changeDish,
                    pattern=lambda data: (
                        data.get('value') == '-QUANTITY_CHANGE-'
                        or data.get('value') == '-QUANTITY_MINUS-'
                        or data.get('value') == '-QUANTITY_PLUS-'
                    )
                ),  # query handler of cart -QUANTITY_CHANGE-, -QUANTITY_MINUS- or -QUANTITY_PLUS- buttons
                CallbackQueryHandler(
                    cart.confirmChange,
                    pattern=lambda data: data.get('value') == '-QUANTITY_OK-'
                ),  # query handler of dish -QUANTITY_OK- button
            ],
            ORDER: [
                MessageHandler(
                    filters.Regex(ut.messages['back_to_menu']),
                    default.navigationButton
                ),  # message handler for navigation
                MessageHandler(
                    filters.LOCATION,
                    order.makeOrder
                ),  # message handler for sent location
            ],
            USER_ORDERS: [
                MessageHandler(
                    filters.Regex(ut.messages['back_to_menu']),
                    default.navigationButton
                ),  # message handler for navigation
                MessageHandler(
                    filters.Regex(r'^[0-9]+$'),
                    user_orders.showSingleOrder
                )  # one order description
            ]
        },
        fallbacks=fallbacks,
        allow_reentry=True
    )

    manager_conversation = ConversationHandler(
        entry_points=[
            CommandHandler('order', manage_db.findOrder),
            CommandHandler('orders', manage_db.showOrders),
            CommandHandler('user', manage_db.findUser),
            CommandHandler('users', manage_db.lastUsers),
            CommandHandler('restaurant', manage_db.findRestaurant),
            CommandHandler('new_restaurant', manage_db.createNewRestaurant),
            CommandHandler('new_category', manage_db.createNewDishCategory),
            CommandHandler('new_dish', manage_db.createNewDish)
        ],
        states={
            M_ORDER: [
                CallbackQueryHandler(
                    manage_db.showStatuses,
                    pattern=lambda data: data.get('value') == '-CHANGE_STATUS-'
                ),  # edit keyboard to show available statuses
                CallbackQueryHandler(
                    manage_db.setStatus,
                    pattern=lambda data: data.get('value') == '-NEW_STATUS-'
                )  # change order status and update keyboard
            ],
            M_USER: [
                CallbackQueryHandler(
                    manage_db.changePermission,
                    pattern=lambda data: data.get('value') in ['-ADMIN_STATUS-', '-MANAGER_STATUS-']
                )  # change user status
            ],
            M_RESTAURANT: [
                CallbackQueryHandler(
                    manage_db.changeRestaurantStatus,
                    pattern=lambda data: data.get('value') == '-CHANGE_RESTAURANT_STATUS-'
                ),  # change restaurant visibility status
                CallbackQueryHandler(
                    manage_db.changeRestaurantSchedule,
                    pattern=lambda data: data.get('value') == '-CHANGE_RESTAURANT_SCHEDULE-'
                ),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    manage_db.showDish
                ),
                CallbackQueryHandler(
                    manage_db.changeDishState,
                    pattern=lambda data: data.get('value') == '-CHANGE_DISH_STATUS-'
                )
            ],
            M_RESTAURANT_SCHEDULE: [
                CallbackQueryHandler(
                    manage_db.cancelScheduleChange,
                    pattern=lambda data: data.get('value') == '-CANCEL_SCHEDULE_CHANGE-'
                ),
                MessageHandler(
                    filters.Regex(r'^([1-7]\s?-\s?[0-2]?[0-9]\.[0-2]?[0-9]\s?-\s?[0-2]?[0-9]\.[0-2]?[0-9])'),
                    manage_db.setRestaurantSchedule
                ),
            ],
            N_RESTAURANT: [
                MessageHandler(
                    filters.TEXT & ~ filters.COMMAND,
                    manage_db.nameNewRestaurant
                )
            ],
            C_RESTAURANT: [
                MessageHandler(
                    filters.TEXT & ~ filters.COMMAND,
                    manage_db.currencyNewRestaurant
                )
            ],
            S_RESTAURANT: [
                MessageHandler(
                    filters.Regex(r'^([1-7]\s?-\s?[0-2]?[0-9]\.[0-2]?[0-9]\s?-\s?[0-2]?[0-9]\.[0-2]?[0-9])'),
                    manage_db.scheduleNewRestaurant
                )
            ],
            N_CATEGORY: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    manage_db.nameNewDishCategory
                )
            ],
            R_DISH: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    manage_db.restaurantNewDish
                )
            ],
            C_DISH: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    manage_db.categoryNewDish
                )
            ],
            N_DISH: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    manage_db.nameNewDish
                )
            ],
            D_DISH: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    manage_db.descriptionNewDish
                )
            ],
            PR_DISH: [
                MessageHandler(
                    filters.Regex(r'^[0-9]+\.?[0-9]*$'),
                    manage_db.priceNewDish
                )
            ],
            PH_DISH: [
                MessageHandler(
                    filters.PHOTO,
                    manage_db.photoNewDish
                ),
                MessageHandler(
                    filters.Regex('^No$'),
                    manage_db.photoNewDish
                )
            ]
        },
        fallbacks=fallbacks,
        allow_reentry=True,
    )

    # Register InvalidCallbackdata handler
    application.add_handler(
        CallbackQueryHandler(
            error.invalidCallbackDataHandler,
            pattern=lambda data: type(data) == InvalidCallbackData
        )
    )

    # Register user conversation handler
    application.add_handler(user_conversation, 1)

    # Register manager conversation handler
    application.add_handler(manager_conversation, 2)

    # Register callback query handler for incoming requests
    application.add_handler(
        CallbackQueryHandler(
            notification.requestButton,
            pattern=lambda data: (
                data.get('value') == '-ORDER_CONFIRM-'
                or data.get('value') == '-ORDER_CANCEL-'
            )
        )
    )
    
    # Handler to show help to users and managers
    application.add_handler(
        CommandHandler('help', default.helpMessage)
    )

    # Handler that sends messages to developer on errors
    application.add_error_handler(
        error.error_handler
    )
    
    # Run bot until Ctrl+C
    application.run_polling()