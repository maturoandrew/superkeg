#!/usr/bin/env python3
import RPi.GPIO as GPIO  # Fixed import syntax
import time
import sys

FLOW_SENSOR = 4

GPIO.setmode(GPIO.BCM)  # Fixed - should be GPIO.BCM, not GPIO,BCM
GPIO.setup(FLOW_SENSOR, GPIO.IN, pull_up_down=GPIO.PUD_UP)

global count
count = 0

def countPulse(channel):
    global count
    count = count + 1
    print(count)  # Fixed for Python 3 - print is a function

GPIO.add_event_detect(FLOW_SENSOR, GPIO.RISING, callback=countPulse, bouncetime=1)

print(f"Flow sensor monitoring started on GPIO {FLOW_SENSOR}")
print("Pour liquid through the sensor or manually trigger it...")
print("Press Ctrl+C to stop")

while True:
    try:
        time.sleep(1)
        if count > 0:
            print(f"Total pulses: {count}")
    except KeyboardInterrupt:
        print('\nInterrupt received')
        GPIO.cleanup()
        sys.exit()