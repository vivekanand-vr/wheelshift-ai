"""SQLAlchemy models for vehicle entities (read-only)"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger, Boolean, Column, Date, DateTime, ForeignKey, Integer,
    Numeric, String, Text
)
from sqlalchemy.orm import relationship

from app.utils.db import Base


class CarModel(Base):
    """Car model catalog"""
    __tablename__ = "car_models"
    
    id = Column(BigInteger, primary_key=True)
    make = Column(String(64), nullable=False)
    model = Column(String(64), nullable=False)
    variant = Column(String(64))
    emission_norm = Column(String(32))
    body_type = Column(String(32))
    fuel_type = Column(String(32))
    transmission_type = Column(String(32))
    gears = Column(Integer)
    model_image_id = Column(String(64))
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    
    # Relationship
    cars = relationship("Car", back_populates="car_model")


class Car(Base):
    """Car inventory instance"""
    __tablename__ = "cars"
    
    id = Column(BigInteger, primary_key=True)
    vin_number = Column(String(17), unique=True)
    registration_number = Column(String(32), unique=True)
    car_model_id = Column(BigInteger, ForeignKey("car_models.id"))
    color = Column(String(32))
    mileage_km = Column(Integer)
    year = Column(Integer)
    engine_cc = Column(Integer)
    status = Column(String(20))
    storage_location_id = Column(BigInteger)
    purchase_price = Column(Numeric(12, 2))
    purchase_date = Column(Date)
    selling_price = Column(Numeric(12, 2))
    primary_image_id = Column(String(64))
    gallery_image_ids = Column(Text)
    document_file_ids = Column(Text)
    description = Column(String(600))
    
    # Merged from car_detailed_specs
    doors = Column(Integer)
    seats = Column(Integer)
    cargo_capacity_liters = Column(Integer)
    acceleration_0_100 = Column(Numeric(5, 2))   # DB column name (no "_to_")
    top_speed_kmh = Column(Integer)
    features = Column(Text)  # JSON column — stored as Text, parsed in Python
    
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    
    # Relationship
    car_model = relationship("CarModel", back_populates="cars")


class MotorcycleModel(Base):
    """Motorcycle model catalog"""
    __tablename__ = "motorcycle_models"
    
    id = Column(BigInteger, primary_key=True)
    make = Column(String(100), nullable=False)
    model = Column(String(100), nullable=False)
    variant = Column(String(100))
    year = Column(Integer)
    engine_capacity = Column(Integer)
    fuel_type = Column(String(20))
    transmission_type = Column(String(20))
    vehicle_type = Column(String(50))
    is_active = Column(Boolean, default=True)
    ex_showroom_price = Column(Numeric(12, 2))
    model_image_id = Column(String(64))
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    
    # Relationship
    motorcycles = relationship("Motorcycle", back_populates="motorcycle_model")


class Motorcycle(Base):
    """Motorcycle inventory instance"""
    __tablename__ = "motorcycles"
    
    id = Column(BigInteger, primary_key=True)
    vin_number = Column(String(17), unique=True)
    registration_number = Column(String(20), unique=True)
    engine_number = Column(String(50))
    chassis_number = Column(String(50))
    motorcycle_model_id = Column(BigInteger, ForeignKey("motorcycle_models.id"))
    color = Column(String(50))
    mileage_km = Column(Integer)
    manufacture_year = Column(Integer)
    registration_date = Column(Date)
    status = Column(String(32))
    storage_location_id = Column(BigInteger)
    purchase_price = Column(Numeric(12, 2))
    purchase_date = Column(Date)
    selling_price = Column(Numeric(12, 2))
    minimum_price = Column(Numeric(12, 2))
    previous_owners = Column(Integer)
    insurance_expiry_date = Column(Date)
    pollution_certificate_expiry = Column(Date)
    is_financed = Column(Boolean)
    is_accidental = Column(Boolean)
    description = Column(Text)
    primary_image_id = Column(String(64))
    gallery_image_ids = Column(Text)
    document_file_ids = Column(Text)
    
    # Merged specs
    engine_type = Column(String(50))
    max_power_bhp = Column(Numeric(6, 2))
    max_torque_nm = Column(Numeric(6, 2))
    cooling_system = Column(String(30))
    fuel_tank_capacity = Column(Numeric(5, 2))
    claimed_mileage_kmpl = Column(Numeric(5, 2))
    length_mm = Column(Integer)
    width_mm = Column(Integer)
    height_mm = Column(Integer)
    wheelbase_mm = Column(Integer)
    ground_clearance_mm = Column(Integer)
    kerb_weight_kg = Column(Integer)
    front_brake_type = Column(String(50))
    rear_brake_type = Column(String(50))
    abs_available = Column(Boolean)
    front_suspension = Column(String(100))
    rear_suspension = Column(String(100))
    front_tyre_size = Column(String(30))
    rear_tyre_size = Column(String(30))
    has_electric_start = Column(Boolean)
    has_kick_start = Column(Boolean)
    has_digital_console = Column(Boolean)
    has_usb_charging = Column(Boolean)
    has_led_lights = Column(Boolean)
    additional_features = Column(Text)
    
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    
    # Relationship
    motorcycle_model = relationship("MotorcycleModel", back_populates="motorcycles")


class Inquiry(Base):
    """Client inquiries (used for collaborative filtering)"""
    __tablename__ = "inquiries"
    
    id = Column(BigInteger, primary_key=True)
    car_id = Column(BigInteger, ForeignKey("cars.id"), nullable=True)
    motorcycle_id = Column(BigInteger, ForeignKey("motorcycles.id"), nullable=True)
    vehicle_type = Column(String(32))
    client_id = Column(BigInteger, nullable=False)
    assigned_employee_id = Column(BigInteger)
    inquiry_type = Column(String(64))
    message = Column(Text)
    status = Column(String(32))
    response = Column(Text)
    response_date = Column(DateTime)
    attachment_file_ids = Column(Text)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
