from sqlalchemy.orm import Session

from modules.database import config as dbc
from utils import constants as uc


def create_database():
    '''Function to create tables, described in config'''
    dbc.Base.metadata.create_all(dbc.engine)

    add_statuses()
    add_developer()

def drop_database():
    '''Function to delete tables, described in config'''
    dbc.Base.metadata.drop_all(dbc.engine)

def add_statuses():
    '''Function to add statuses to database'''

    with Session(dbc.engine) as session:
        for status_name in uc.ORDER_STATUSES:
            new_status = dbc.Status(
                name=status_name
            )
            session.add(new_status)
        session.commit()

def add_developer():
    '''Adds developer to database'''
    with Session(dbc.engine) as session:
        new_developer = dbc.User(
            first_name='DEV_TEMP',
            manager=True,
            admin=True,
            id=uc.DEVELOPER_ID
        )
        session.add(new_developer)
        session.commit()
