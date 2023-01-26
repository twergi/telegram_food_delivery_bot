from datetime import datetime, timezone

from utils import constants as uc


def list_split(lst: list, cols: int):
    '''Function to split provided list on provided cols'''
    result = []
    index = 0
    for element in lst:
        if index == 0:
            result.append([element])
            index = (index + 1) % cols
        else:
            result[-1].append(element)
            index = (index + 1) % cols
    return result

def current_server_time() -> datetime:
    '''Returns current server time with SERVER_TIMEZONE'''
    return datetime.now().replace(tzinfo=uc.SERVER_TIMEZONE)

def current_utc_time() -> datetime:
    '''Returns current time in UTC'''
    return current_server_time().astimezone(timezone.utc)