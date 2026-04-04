"""SQLAlchemy read-only models for lead scoring"""
from sqlalchemy import BigInteger, Column, Date, DateTime, ForeignKey, Integer, Numeric, String

from app.utils.db import Base


class Client(Base):
    """Client (customer) profile"""
    __tablename__ = "clients"

    id = Column(BigInteger, primary_key=True)
    name = Column(String(128))
    email = Column(String(128))
    phone = Column(String(32))
    status = Column(String(20))         # ACTIVE / INACTIVE
    total_purchases = Column(Integer, default=0)  # actual DB column name
    last_purchase = Column(Date)                  # actual DB column name, type date
    created_at = Column(DateTime)
    updated_at = Column(DateTime)


class Sale(Base):
    """Vehicle sale record"""
    __tablename__ = "sales"

    id = Column(BigInteger, primary_key=True)
    client_id = Column(BigInteger, ForeignKey("clients.id"))
    car_id = Column(BigInteger, nullable=True)
    motorcycle_id = Column(BigInteger, nullable=True)
    sale_price = Column(Numeric(12, 2))
    sale_date = Column(DateTime)   # datetime in DB
    created_at = Column(DateTime)


class Reservation(Base):
    """Vehicle reservation record"""
    __tablename__ = "reservations"

    id = Column(BigInteger, primary_key=True)
    client_id = Column(BigInteger, ForeignKey("clients.id"))
    car_id = Column(BigInteger, nullable=True)
    motorcycle_id = Column(BigInteger, nullable=True)
    status = Column(String(20))   # PENDING / CONFIRMED / EXPIRED / CANCELLED
    expiry_date = Column(DateTime)  # datetime in DB
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
