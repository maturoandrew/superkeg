from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Enum, ForeignKey
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
    brewer = Column(String, nullable=False)
    abv = Column(Float, nullable=False)
    volume_remaining = Column(Float, nullable=False)
    original_volume = Column(Float, nullable=True)  # New field
    date_created = Column(DateTime, default=datetime.utcnow)
    date_last_tapped = Column(DateTime, nullable=True)
    date_finished = Column(DateTime, nullable=True)
    status = Column(Enum(KegStatus), default=KegStatus.UNTAPPED)

class PourEvent(Base):
    __tablename__ = "pour_events"
    id = Column(Integer, primary_key=True, index=True)
    keg_id = Column(Integer, ForeignKey("kegs.id"), nullable=False)
    volume_dispensed = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

# Create tables
Base.metadata.create_all(bind=engine)

def input_new_keg(session, name, style, brewer, abv, volume_remaining):
    new_keg = Keg(
        name=name,
        style=style,
        brewer=brewer,
        abv=abv,
        volume_remaining=volume_remaining,
        original_volume=volume_remaining,  # Set original_volume at creation
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

def log_pour_event(session, keg_id, volume_dispensed):
    from datetime import datetime
    event = PourEvent(keg_id=keg_id, volume_dispensed=volume_dispensed, timestamp=datetime.utcnow())
    session.add(event)
    session.commit()
    return event 