from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import enum
from datetime import datetime

# Use SQLite for local storage
DATABASE_URL = "sqlite:///kegs.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class KegStatus(enum.Enum):
    UNTAPPED = "untapped"
    TAPPED = "tapped"
    OFF_TAP = "off_tap"

class Keg(Base):
    __tablename__ = "kegs"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    style = Column(String, nullable=False)
    abv = Column(Float, nullable=False)
    volume_remaining = Column(Float, nullable=False)
    date_created = Column(DateTime, default=datetime.utcnow)
    date_last_tapped = Column(DateTime, nullable=True)
    date_finished = Column(DateTime, nullable=True)
    status = Column(Enum(KegStatus), default=KegStatus.UNTAPPED)

# Create tables
Base.metadata.create_all(bind=engine)

def input_new_keg(session, name, style, abv, volume_remaining):
    new_keg = Keg(
        name=name,
        style=style,
        abv=abv,
        volume_remaining=volume_remaining,
        date_created=datetime.utcnow(),
        status=KegStatus.UNTAPPED
    )
    session.add(new_keg)
    session.commit()
    session.refresh(new_keg)
    return new_keg

def tap_new_keg(session, keg_id):
    keg = session.query(Keg).filter(Keg.id == keg_id).first()
    if keg and keg.status == KegStatus.UNTAPPED:
        keg.status = KegStatus.TAPPED
        keg.date_last_tapped = datetime.utcnow()
        session.commit()
        return keg
    return None

def tap_previous_keg(session, keg_id):
    keg = session.query(Keg).filter(Keg.id == keg_id).first()
    if keg and keg.status == KegStatus.OFF_TAP:
        keg.status = KegStatus.TAPPED
        keg.date_last_tapped = datetime.utcnow()
        session.commit()
        return keg
    return None

def take_keg_off_tap(session, keg_id):
    keg = session.query(Keg).filter(Keg.id == keg_id).first()
    if keg and keg.status == KegStatus.TAPPED:
        keg.status = KegStatus.OFF_TAP
        keg.date_finished = datetime.utcnow()
        session.commit()
        return keg
    return None

def subtract_volume(session, keg_id, volume_dispensed):
    keg = session.query(Keg).filter(Keg.id == keg_id, Keg.status == KegStatus.TAPPED).first()
    if keg:
        keg.volume_remaining = max(0, keg.volume_remaining - volume_dispensed)
        session.commit()
        return keg
    return None 