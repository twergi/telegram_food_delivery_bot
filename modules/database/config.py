import datetime
import os
from typing import Optional

from sqlalchemy import ForeignKey, create_engine, select
from sqlalchemy.orm import (DeclarativeBase, Mapped, Session, mapped_column,
                            relationship)
from sqlalchemy.types import (BigInteger, Boolean, DateTime, Float, Integer,
                              String, Time, Unicode)

from utils import constants as uc
from utils import utility as uu


# Get login and password for PostgreSQL
# (example: admin:password)
DBLOGIN = os.environ.get('DBLOGIN')

# Get address of PostgreSQL
# (example: localhost:5432)
DBADDR = os.environ.get('DBADDR')

# Create engine with database
engine = create_engine(f"{uc.DBDIALECT}://{DBLOGIN}@{DBADDR}/{uc.DBNAME}", echo=uc.DEBUG)

def default_status_id():
    '''Function that returns default status id for every new order'''
    with Session(engine) as session:
        status_id = session.scalar(
            select(Status)
                .where(Status.name==uc.ORDER_STATUSES[0])  # First status for order is kept under index 0 in statuses list
        ).id
    return status_id

# Create Base class that inherits from main ORM class
class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__: str = 'user'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(String(32))
    first_name: Mapped[str] = mapped_column(Unicode(64))
    last_name: Mapped[Optional[str]] = mapped_column(Unicode(64))
    date_registered: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now)
    admin: Mapped[bool] = mapped_column(Boolean, default=False)  # can add managers and has manager permissions
    manager: Mapped[bool] = mapped_column(Boolean, default=False)  # can manage orders, add or disable restaurants, categories and dishes

    orders: Mapped['Order'] = relationship(foreign_keys='Order.user_id', back_populates='user')
    managed_orders: Mapped['Order'] = relationship(foreign_keys='Order.manager_id', back_populates='manager')

    def __repr__(self):
        return f"[USER] username: {self.username}, id: {self.id}"

class Restaurant(Base):
    __tablename__: str = 'restaurant'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(32), unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)  # manages if could be seen by users
    
    currency: Mapped[str] = mapped_column(String(32))

    dishes: Mapped[list['Dish']] = relationship(back_populates='restaurant')
    schedule: Mapped[list['RestaurantSchedule']] = relationship(back_populates='restaurant')

    def __repr__(self):
        return f"[RESTAURANT] {self.name}"

class RestaurantSchedule(Base):
    __tablename__: str = 'restaurant_schedule'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day_of_week: Mapped[int] = mapped_column(Integer)
    start: Mapped[datetime.time] = mapped_column(Time)
    end: Mapped[datetime.time] = mapped_column(Time)

    restaurant_id: Mapped[int] = mapped_column(ForeignKey('restaurant.id'))

    restaurant: Mapped['Restaurant'] = relationship(back_populates='schedule')

    def __repr__(self):
        return f"[RESTAURANT_SCHEDULE] of {self.restaurant.name}"

class DishCategory(Base):
    __tablename__: str = 'dish_category'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(32), unique=True)

    def __repr__(self):
        return f"[DISH_CATEGORY] {self.name}"

class Dish(Base):
    __tablename__: str = 'dish'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(String(128))
    file_id: Mapped[Optional[str]] = mapped_column(String)
    price: Mapped[float] = mapped_column(Float)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)  # manages if could be seen by users

    dish_category_id: Mapped[int] = mapped_column(ForeignKey('dish_category.id'))
    restaurant_id: Mapped[int] = mapped_column(ForeignKey('restaurant.id'))

    dish_category: Mapped['DishCategory'] = relationship()
    restaurant: Mapped['Restaurant'] = relationship(back_populates='dishes')

    def __repr__(self):
        return f"[DISH] {self.name}"

class Status(Base):
    __tablename__: str = 'status'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(32), unique=True)

    def __repr__(self):
        return f"[STATUS] {self.name}"

class Order(Base):
    __tablename__: str = 'order'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date_ordered: Mapped[datetime.datetime] = mapped_column(DateTime, default=uu.current_utc_time)
    location: Mapped[str] = mapped_column(String(64))

    user_id: Mapped[int] = mapped_column(ForeignKey('user.id'))
    manager_id: Mapped[Optional[int]] = mapped_column(ForeignKey('user.id'))
    status_id: Mapped[int] = mapped_column(ForeignKey('status.id'), default=default_status_id)

    user: Mapped['User'] = relationship(foreign_keys='Order.user_id', back_populates='orders')
    manager: Mapped['User'] = relationship(foreign_keys='Order.manager_id', back_populates='managed_orders')
    status: Mapped['Status'] = relationship()
    cart_dish: Mapped[list['CartDish']] = relationship(back_populates='order')

    def __repr__(self):
        return f"[ORDER] id: {self.id}"

class CartDish(Base):
    __tablename__: str = 'cart_dish'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quantity: Mapped[int] = mapped_column(Integer)

    dish_id: Mapped[int] = mapped_column(ForeignKey('dish.id'))
    order_id: Mapped[int] = mapped_column(ForeignKey('order.id'))

    dish: Mapped['Dish'] = relationship()
    order: Mapped['Order'] = relationship(back_populates='cart_dish')

    def __repr__(self):
        return f"[CART_DISH] id: {self.id}"
    