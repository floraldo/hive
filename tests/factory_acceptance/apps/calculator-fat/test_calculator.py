#!/usr/bin/env python3
"""
Test suite for Calculator Service
Designed to catch bugs and validate fixes through iterations
"""

import unittest
import requests
import json

class TestCalculator(unittest.TestCase):
    BASE_URL = "http://localhost:5005"

    def test_health_check(self):
        """Test health check endpoint"""
        response = requests.get(f"{self.BASE_URL}/api/health")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["service"], "calculator")

    def test_addition(self):
        """Test addition operation"""
        response = requests.post(
            f"{self.BASE_URL}/api/add",
            json={"a": 5, "b": 3},
            headers={"Content-Type": "application/json"}
        )
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["result"], 8)  # 5 + 3 = 8

    def test_subtraction(self):
        """Test subtraction operation"""
        response = requests.post(
            f"{self.BASE_URL}/api/subtract",
            json={"a": 10, "b": 4},
            headers={"Content-Type": "application/json"}
        )
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["result"], 6)  # 10 - 4 = 6

    def test_multiplication(self):
        """Test multiplication operation"""
        response = requests.post(
            f"{self.BASE_URL}/api/multiply",
            json={"a": 4, "b": 7},
            headers={"Content-Type": "application/json"}
        )
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["result"], 28)  # 4 * 7 = 28

    def test_division(self):
        """Test division operation"""
        response = requests.post(
            f"{self.BASE_URL}/api/divide",
            json={"a": 15, "b": 3},
            headers={"Content-Type": "application/json"}
        )
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["result"], 5)  # 15 / 3 = 5

    def test_division_by_zero(self):
        """Test division by zero protection"""
        response = requests.post(
            f"{self.BASE_URL}/api/divide",
            json={"a": 10, "b": 0},
            headers={"Content-Type": "application/json"}
        )
        # Should return 400 with error message
        self.assertEqual(response.status_code, 400)

        data = response.json()
        self.assertFalse(data["success"])
        self.assertIn("zero", data["error"].lower())

    def test_missing_parameters(self):
        """Test error handling for missing parameters"""
        response = requests.post(
            f"{self.BASE_URL}/api/add",
            json={"a": 5},  # Missing 'b'
            headers={"Content-Type": "application/json"}
        )
        self.assertEqual(response.status_code, 400)

        data = response.json()
        self.assertFalse(data["success"])

if __name__ == '__main__':
    unittest.main(verbosity=2)
