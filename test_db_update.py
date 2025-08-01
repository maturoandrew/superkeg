#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
from datetime import datetime

# Add the current directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from keg_app import SessionLocal, Keg, KegStatus, PourEvent

def test_database_state():
    """Test the current state of the database."""
    print("=== Database State Test ===")
    
    session = SessionLocal()
    
    try:
        # Check all kegs
        print("\n--- All Kegs ---")
        kegs = session.query(Keg).all()
        for keg in kegs:
            print("Keg %d: %s (%s) - Status: %s, Volume: %.2fL, Tap: %s" % (
                keg.id, keg.name, keg.brewer, keg.status.value, 
                keg.volume_remaining, keg.tap_position or "None"
            ))
        
        # Check tapped kegs
        print("\n--- Tapped Kegs ---")
        tapped_kegs = session.query(Keg).filter(Keg.status == KegStatus.TAPPED).all()
        for keg in tapped_kegs:
            print("Tap %d: %s (%s) - Volume: %.2fL" % (
                keg.tap_position, keg.name, keg.brewer, keg.volume_remaining
            ))
        
        # Check recent pour events
        print("\n--- Recent Pour Events (last 10) ---")
        events = session.query(PourEvent).order_by(PourEvent.timestamp.desc()).limit(10).all()
        for event in events:
            print("Event %d: Keg %d, %.1fml at %s" % (
                event.id, event.keg_id, event.volume_dispensed * 1000, 
                event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            ))
        
        # Check total pour events
        total_events = session.query(PourEvent).count()
        print("\n--- Summary ---")
        print("Total pour events: %d" % total_events)
        print("Tapped kegs: %d" % len(tapped_kegs))
        
    except Exception as e:
        print("Error: %s" % str(e))
    finally:
        session.close()

def test_manual_update():
    """Test manually updating a keg volume."""
    print("\n=== Manual Update Test ===")
    
    session = SessionLocal()
    
    try:
        # Find a tapped keg
        keg = session.query(Keg).filter(Keg.status == KegStatus.TAPPED).first()
        if not keg:
            print("No tapped kegs found!")
            return
        
        print("Testing update on keg %d: %s (current volume: %.2fL)" % (
            keg.id, keg.name, keg.volume_remaining
        ))
        
        # Simulate a small pour (50ml)
        volume_to_subtract = 0.05  # 50ml in liters
        old_volume = keg.volume_remaining
        keg.volume_remaining = max(0, keg.volume_remaining - volume_to_subtract)
        
        # Log the pour event
        event = PourEvent(
            keg_id=keg.id, 
            volume_dispensed=volume_to_subtract, 
            timestamp=datetime.utcnow()
        )
        session.add(event)
        
        session.commit()
        
        print("Updated keg %d: %.2fL -> %.2fL (-%.1fml)" % (
            keg.id, old_volume, keg.volume_remaining, volume_to_subtract * 1000
        ))
        print("Added pour event %d" % event.id)
        
    except Exception as e:
        print("Error: %s" % str(e))
    finally:
        session.close()

if __name__ == "__main__":
    test_database_state()
    test_manual_update()
    print("\n=== Test Complete ===") 