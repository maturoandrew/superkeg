#!/usr/bin/env python3
"""
Flow Meter Setup and Test Script
Simple script to test flow meter connectivity and perform initial calibration.
"""

import time
import sys
from flow_meter import FlowMeter

def test_gpio_connection(gpio_pin: int = 18):
    """Test if flow meter is connected and generating pulses."""
    print(f"\n=== Testing Flow Meter on GPIO {gpio_pin} ===")
    print("This will monitor for pulses for 10 seconds...")
    print("Try flowing liquid through the meter or manually triggering the sensor.\n")
    
    flow_meter = FlowMeter(gpio_pin=gpio_pin, pulses_per_liter=450.0)
    
    try:
        flow_meter.start_monitoring()
        
        start_time = time.time()
        last_count = 0
        
        while time.time() - start_time < 10:
            current_count = flow_meter.pulse_count
            if current_count != last_count:
                print(f"Pulse detected! Total count: {current_count}")
                last_count = current_count
            time.sleep(0.1)
        
        total_pulses = flow_meter.pulse_count
        print(f"\nTest complete. Total pulses detected: {total_pulses}")
        
        if total_pulses > 0:
            print("✓ Flow meter is connected and working!")
            return True
        else:
            print("✗ No pulses detected. Check connections:")
            print("  - VCC to 5V (or 3.3V)")
            print("  - GND to GND")
            print(f"  - Signal to GPIO {gpio_pin}")
            print("  - Pull-up resistor (10kΩ) between signal and VCC")
            return False
            
    except Exception as e:
        print(f"Error during test: {e}")
        return False
    finally:
        flow_meter.stop_monitoring()
        flow_meter.cleanup()

def interactive_calibration(gpio_pin: int = 18):
    """Interactive calibration process."""
    print(f"\n=== Flow Meter Calibration (GPIO {gpio_pin}) ===")
    print("This process will help you calibrate your flow meter for accurate measurements.")
    print("\nYou'll need:")
    print("  - A measuring cup (500ml or 1L recommended)")
    print("  - Water or another liquid")
    print("  - The flow meter installed in your system")
    
    input("\nPress Enter when ready to start...")
    
    # Get known volume
    while True:
        try:
            volume_ml = float(input("\nEnter the volume you'll pour (in ml): "))
            if volume_ml > 0:
                break
            print("Please enter a positive volume.")
        except ValueError:
            print("Please enter a valid number.")
    
    volume_liters = volume_ml / 1000.0
    
    print(f"\nCalibration setup:")
    print(f"  - GPIO pin: {gpio_pin}")
    print(f"  - Volume to pour: {volume_ml}ml ({volume_liters}L)")
    print(f"  - Starting pulse count monitoring...")
    
    flow_meter = FlowMeter(gpio_pin=gpio_pin, pulses_per_liter=450.0)  # Initial guess
    
    try:
        flow_meter.start_monitoring()
        print(f"\n🚰 Pour exactly {volume_ml}ml through the flow meter now...")
        print("Press Enter when finished pouring.")
        
        start_pulses = flow_meter.pulse_count
        input()
        end_pulses = flow_meter.pulse_count
        
        calibration_pulses = end_pulses - start_pulses
        
        if calibration_pulses > 0:
            pulses_per_liter = calibration_pulses / volume_liters
            
            print(f"\n✓ Calibration successful!")
            print(f"  Pulses detected: {calibration_pulses}")
            print(f"  Volume poured: {volume_liters}L")
            print(f"  Calculated: {pulses_per_liter:.2f} pulses/L")
            
            # Save calibration
            flow_meter.pulses_per_liter = pulses_per_liter
            config_file = f"flow_meter_gpio_{gpio_pin}_config.json"
            flow_meter.save_calibration(config_file)
            print(f"  Calibration saved to: {config_file}")
            
            return pulses_per_liter
        else:
            print("✗ No pulses detected during calibration.")
            print("Check your connections and try again.")
            return None
            
    except Exception as e:
        print(f"Error during calibration: {e}")
        return None
    finally:
        flow_meter.stop_monitoring()
        flow_meter.cleanup()

def show_hardware_setup():
    """Display hardware setup instructions."""
    print("\n=== Hardware Setup Instructions ===")
    print("""
Common Flow Meters:
  • YF-S201: ~450 pulses/L, 1-30 L/min flow rate
  • YF-S401: ~5880 pulses/L, 0.3-6 L/min flow rate
  • YF-B1: ~1800 pulses/L, 1-25 L/min flow rate

Wiring (typical 3-wire flow meter):
  • Red wire (VCC)    → Raspberry Pi 5V (pin 2 or 4)
  • Black wire (GND)  → Raspberry Pi GND (pin 6, 9, 14, 20, 25, 30, 34, or 39)
  • Yellow wire (SIG) → Raspberry Pi GPIO pin (default: GPIO 18, pin 12)

Optional Pull-up Resistor:
  • 10kΩ resistor between Signal (Yellow) and VCC (Red)
  • Some flow meters have built-in pull-ups

Raspberry Pi 2 GPIO Pinout (relevant pins):
  Pin 2:  5V
  Pin 4:  5V  
  Pin 6:  GND
  Pin 12: GPIO 18 (default signal pin)
  Pin 14: GND

Installation:
  1. Power off Raspberry Pi
  2. Connect wires as shown above
  3. Install flow meter in your liquid line
  4. Power on Raspberry Pi
  5. Run this setup script
    """)

def main():
    """Main setup menu."""
    print("=== Flow Meter Setup for Raspberry Pi ===")
    print("This script will help you set up and test your flow meter.")
    
    while True:
        print("\nOptions:")
        print("1. Show hardware setup instructions")
        print("2. Test flow meter connection")
        print("3. Calibrate flow meter")
        print("4. Exit")
        
        choice = input("\nSelect option (1-4): ").strip()
        
        if choice == "1":
            show_hardware_setup()
            
        elif choice == "2":
            gpio_pin = input(f"Enter GPIO pin number (default 18): ").strip()
            gpio_pin = int(gpio_pin) if gpio_pin else 18
            test_gpio_connection(gpio_pin)
            
        elif choice == "3":
            gpio_pin = input(f"Enter GPIO pin number (default 18): ").strip()
            gpio_pin = int(gpio_pin) if gpio_pin else 18
            
            # Test connection first
            if test_gpio_connection(gpio_pin):
                interactive_calibration(gpio_pin)
            else:
                print("\nPlease fix connection issues before calibrating.")
                
        elif choice == "4":
            print("Setup complete!")
            break
            
        else:
            print("Invalid option. Please choose 1-4.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup interrupted by user.")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        print("Please check your hardware connections and try again.")