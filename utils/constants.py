import datetime as dt
import os


# If True, enables SQL logging, all notifications are sent to developer
DEBUG: bool = True

# Name of the database
DBNAME: str = os.environ.get('DBNAME')

# Directory of project
BASE_DIR: str = os.path.dirname(os.path.realpath(__file__))

# Font configuration for orders image
FONT_SIZE: int = 24
FONT_FILENAME: str = 'consolas.ttf'  # name of chosen font file in utils/resources
FONT_PATH: str = os.path.join(BASE_DIR, 'resources', FONT_FILENAME)  # Path to default font

# Chat ID where orders notifications will be sent
CHAT_ID: int = os.environ.get('CHAT_ID')

# Developer ID for errors
DEVELOPER_ID: int = os.environ.get('DEVELOPER_ID')

# This account will be displayed in "About Us" menu as help contact
MANAGER_ID: int = os.environ.get('MANAGER_ID')

# Set time deltas for server timezone
SHOURS: int = 3
SMINUTES: int = 0
SERVER_TIMEZONE: dt.timezone = dt.timezone(
    dt.timedelta(
        hours=SHOURS,
        minutes=SMINUTES
    )
)  # UTC+SHOURS:SMINUTES

# Set time deltas for place timezone
PHOURS:int  = 3
PMINUTES: int = 0
PLACE_TIMEZONE: dt.timezone = dt.timezone(
    dt.timedelta(
        hours=PHOURS,
        minutes=PMINUTES
    )
)  # UTC+PHOURS:PMINUTES

# Statuses to be added on database creation and used in order creation and management
# It is allowed to change all status names
# Names must be either changed before DB creation or changed here and in DB manually
# To add new status, just add it to this list with index [1, -2)
# Custom statuses must be handled by manager
# Maximum status name length is 32
ORDER_STATUSES: list = [
    'Awaiting Response',  # Default status for every new order, before manager accepted or declined it. Must be kept with index 0
    'In Progress',  # Status under index 1 will be used as default after manager confirmation
    'Completed',  # Default status for every completed order. Must be kept with index -2
    'Cancelled',  # Default status for every cancelled order. Must be kept with index -1
]