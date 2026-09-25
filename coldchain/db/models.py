"""The tables the brief asks for, as SQLAlchemy models.

`sensor_readings` is the time series and is indexed on (truck_id, ts). When
TimescaleDB is present it becomes a hypertable — see session.py — and when it
is not, a plain table with that index is fine for a 48-hour demo.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (Boolean, DateTime, Float, ForeignKey, Index, Integer,
                        String, Text)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Truck(Base):
    __tablename__ = "trucks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    plate: Mapped[str] = mapped_column(String(32), default="")
    status: Mapped[str] = mapped_column(String(24), default="IDLE")
    route_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    destination_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    batch_id: Mapped[str | None] = mapped_column(String(32), nullable=True)


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    truck_id: Mapped[str] = mapped_column(ForeignKey("trucks.id"))
    kind: Mapped[str] = mapped_column(String(32), default="SIMULATED")
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    truck_id: Mapped[str] = mapped_column(String(32), index=True)
    device_id: Mapped[str] = mapped_column(String(48))
    temperature_c: Mapped[float] = mapped_column(Float)
    humidity_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    speed_kmh: Mapped[float] = mapped_column(Float)
    g_force: Mapped[float] = mapped_column(Float)
    door_open: Mapped[bool] = mapped_column(Boolean)
    refrigeration_on: Mapped[bool] = mapped_column(Boolean)

    __table_args__ = (Index("ix_readings_truck_ts", "truck_id", "ts"),)


class RejectedReading(Base):
    """Bad data is logged, never silently dropped (spec: Data quality)."""

    __tablename__ = "rejected_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    truck_id: Mapped[str] = mapped_column(String(32), default="UNKNOWN")
    reason: Mapped[str] = mapped_column(String(64))
    detail: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[str] = mapped_column(Text, default="")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    safe_min_temp_c: Mapped[float] = mapped_column(Float)
    safe_max_temp_c: Mapped[float] = mapped_column(Float)
    shelf_life_hours: Mapped[float] = mapped_column(Float)
    value_qar_per_kg: Mapped[float] = mapped_column(Float, default=0.0)


class ProductBatch(Base):
    __tablename__ = "product_batches"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    quantity_kg: Mapped[float] = mapped_column(Float)
    production_date: Mapped[str] = mapped_column(String(16))
    expiry_date: Mapped[str] = mapped_column(String(16))
    safe_min_temp_c: Mapped[float] = mapped_column(Float)
    safe_max_temp_c: Mapped[float] = mapped_column(Float)
    initial_shelf_life_hours: Mapped[float] = mapped_column(Float)
    truck_id: Mapped[str | None] = mapped_column(String(32), nullable=True)


class Warehouse(Base):
    __tablename__ = "warehouses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    capacity_kg: Mapped[float] = mapped_column(Float)
    available_capacity_kg: Mapped[float] = mapped_column(Float)
    min_temp_c: Mapped[float] = mapped_column(Float)
    max_temp_c: Mapped[float] = mapped_column(Float)


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(96))
    origin_id: Mapped[str] = mapped_column(String(32))
    destination_id: Mapped[str] = mapped_column(String(32))
    distance_km: Mapped[float] = mapped_column(Float, default=0.0)
    geometry: Mapped[str] = mapped_column(Text, default="[]")   # JSON [[lon,lat],...]


class Inventory(Base):
    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("product_batches.id"))
    location_id: Mapped[str] = mapped_column(String(32))
    location_kind: Mapped[str] = mapped_column(String(16), default="TRUCK")
    quantity_kg: Mapped[float] = mapped_column(Float)


class IncidentRow(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    truck_id: Mapped[str] = mapped_column(String(32), index=True)
    type: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="OPEN")
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    peak_temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scenario: Mapped[str] = mapped_column(String(32), default="NORMAL")
    speed_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    seed: Mapped[int] = mapped_column(Integer, default=0)


class DeviceEventRow(Base):
    """What a device reported between telemetry ticks."""

    __tablename__ = "device_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    truck_id: Mapped[str] = mapped_column(String(32), index=True)
    device_id: Mapped[str] = mapped_column(String(48))
    type: Mapped[str] = mapped_column(String(32))
    detail: Mapped[str] = mapped_column(Text, default="")
    value: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (Index("ix_device_events_truck_ts", "truck_id", "ts"),)
