#!/usr/bin/env python3
"""
Locust Load Test for Flask API

This file defines load tests for the /api/analyze endpoint.
Run with: locust

Then open http://localhost:8089 in your browser to control the test.

Environment Variables:
    BASE_URL: Base URL for the API (default: https://startup-hmwd.onrender.com)
"""

import os
from locust import HttpUser, task, between


class AnalyzeAPIUser(HttpUser):
    """
    A simulated user that repeatedly calls the /api/analyze endpoint.
    
    Locust will spawn multiple instances of this class to simulate
    concurrent users hitting your API.
    """
    
    # Wait between 1 and 3 seconds between tasks (simulates real user behavior)
    wait_time = between(1, 3)
    
    def on_start(self):
        """
        Called once when a user instance starts.
        You can use this to log in or set up session data if needed.
        """
        # Get base URL from environment variable or use default
        base_url = os.environ.get("BASE_URL", "https://startup-hmwd.onrender.com")
        
        # If the client was initialized with a different base URL, update it
        if not self.client.base_url.startswith(base_url):
            self.client.base_url = base_url.rstrip("/")
    
    @task
    def analyze_ingredients(self):
        """
        This is the main task that will be executed repeatedly.
        The @task decorator tells Locust to call this method.
        """
        # Realistic ingredient combinations for testing
        test_ingredients = [
            ["banana", "spinach", "almond milk"],
            ["strawberry", "blueberry", "greek yogurt"],
            ["mango", "coconut milk", "chia seeds"],
            ["apple", "kale", "oat milk"],
            ["peach", "ginger", "soy milk"],
        ]
        
        # Rotate through different ingredient combinations
        import random
        ingredients = random.choice(test_ingredients)
        
        # Prepare the JSON payload
        payload = {
            "ingredients": ingredients
        }
        
        # Make the POST request
        # Locust automatically tracks response time, success/failure, etc.
        with self.client.post(
            "/api/analyze",
            json=payload,
            catch_response=True,
            name="POST /api/analyze"
        ) as response:
            # Check if the request was successful
            if response.status_code == 200:
                response.success()
            else:
                # Mark as failure if status code is not 200
                response.failure(f"Unexpected status code: {response.status_code}")

