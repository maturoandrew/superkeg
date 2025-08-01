#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import threading
import requests
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class VolumeTracker(object):
    """Tracks pour volume in memory and sends updates to Flask."""
    
    def __init__(self, flask_base_url="http://localhost:5000"):
        self.flask_base_url = flask_base_url
        self.active_pours = {}  # {keg_id: {'volume': float, 'start_time': datetime, 'last_update': datetime}}
        self.running = False
        self.update_thread = None
        
    def start_pour(self, keg_id, keg_name):
        """Start tracking a new pour."""
        if keg_id not in self.active_pours:
            self.active_pours[keg_id] = {
                'volume': 0.0,
                'keg_name': keg_name,
                'start_time': datetime.utcnow(),
                'last_update': datetime.utcnow()
            }
            logger.info("Started tracking pour for keg %d (%s)" % (keg_id, keg_name))
    
    def update_pour_volume(self, keg_id, volume_increment):
        """Update the volume for an active pour."""
        if keg_id in self.active_pours:
            self.active_pours[keg_id]['volume'] += volume_increment
            self.active_pours[keg_id]['last_update'] = datetime.utcnow()
            logger.info("Updated pour - Keg %d: %.1fml total" % (keg_id, self.active_pours[keg_id]['volume'] * 1000))
    
    def finish_pour(self, keg_id):
        """Mark a pour as finished."""
        if keg_id in self.active_pours:
            total_volume = self.active_pours[keg_id]['volume']
            logger.info("Finished pour - Keg %d: %.1fml total" % (keg_id, total_volume * 1000))
            del self.active_pours[keg_id]
    
    def get_active_pours(self):
        """Get current active pours for API."""
        from datetime import datetime
        
        active_pours = []
        completed_pours = []
        current_time = datetime.utcnow()
        kegs_to_remove = []
        
        for keg_id, pour_data in self.active_pours.items():
            time_since_update = (current_time - pour_data['last_update']).total_seconds()
            
            if time_since_update > 5:  # Mark as completed if no updates for 5 seconds
                completed_pours.append({
                    'keg_id': keg_id,
                    'keg_name': pour_data['keg_name'],
                    'final_volume': pour_data['volume']
                })
                kegs_to_remove.append(keg_id)
                logger.info("Auto-completed pour for keg %d after 5s timeout" % keg_id)
            else:
                active_pours.append({
                    'keg_id': keg_id,
                    'keg_name': pour_data['keg_name'],
                    'current_volume': pour_data['volume'],
                    'total_volume': min(pour_data['volume'] * 2, 0.5)  # Estimate total
                })
        
        # Remove completed pours
        for keg_id in kegs_to_remove:
            del self.active_pours[keg_id]
        
        return active_pours, completed_pours
    
    def _send_updates_to_flask(self):
        """Send active pour updates to Flask every 250ms."""
        while self.running:
            try:
                active_pours, completed_pours = self.get_active_pours()
                
                if active_pours or completed_pours:
                    # Send update to Flask
                    url = "%s/api/volume-update" % self.flask_base_url
                    data = {
                        'active_pours': active_pours,
                        'completed_pours': completed_pours,
                        'timestamp': datetime.utcnow().isoformat()
                    }
                    
                    response = requests.post(url, json=data, timeout=1)
                    if response.status_code != 200:
                        logger.warning("Failed to send volume update to Flask: %d" % response.status_code)
                
            except Exception as e:
                logger.error("Error sending volume update: %s" % str(e))
            
            time.sleep(0.25)  # Update every 250ms
    
    def start(self):
        """Start the volume tracker."""
        self.running = True
        self.update_thread = threading.Thread(target=self._send_updates_to_flask)
        self.update_thread.daemon = True
        self.update_thread.start()
        logger.info("Volume tracker started")
    
    def stop(self):
        """Stop the volume tracker."""
        self.running = False
        if self.update_thread:
            self.update_thread.join(timeout=1.0)
        logger.info("Volume tracker stopped")

# Global instance
volume_tracker = VolumeTracker() 