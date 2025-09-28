#!/usr/bin/env python3
"""
Currency Service Demo - Simulating the deployed endpoint
This represents what the autonomous AI agency would deliver
"""

import json
import random
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading
import time

class CurrencyServiceHandler(BaseHTTPRequestHandler):
    """HTTP handler for currency conversion API"""

    # Mock exchange rates (in production, this would fetch from external API)
    EXCHANGE_RATES = {
        "USD": 1.0,
        "EUR": 0.85,
        "GBP": 0.73,
        "JPY": 110.0,
        "CAD": 1.25,
        "AUD": 1.35,
        "CHF": 0.92,
        "CNY": 6.45
    }

    def do_GET(self):
        """Handle GET requests"""

        parsed_url = urlparse(self.path)

        if parsed_url.path == "/health":
            self._health_check()
        elif parsed_url.path == "/convert":
            self._convert_currency(parsed_url.query)
        elif parsed_url.path == "/rates":
            self._get_rates()
        else:
            self._send_error(404, "Endpoint not found")

    def _health_check(self):
        """Health check endpoint"""
        response = {
            "status": "healthy",
            "service": "currency-service",
            "version": "1.0.0",
            "timestamp": time.time(),
            "uptime_seconds": int(time.time() - start_time)
        }
        self._send_json_response(200, response)

    def _convert_currency(self, query_string):
        """Convert currency endpoint"""
        try:
            params = parse_qs(query_string)

            # Validate required parameters
            if "from" not in params or "to" not in params or "amount" not in params:
                self._send_error(400, "Missing required parameters: from, to, amount")
                return

            from_currency = params["from"][0].upper()
            to_currency = params["to"][0].upper()
            amount = float(params["amount"][0])

            # Validate currencies
            if from_currency not in self.EXCHANGE_RATES:
                self._send_error(400, f"Unsupported source currency: {from_currency}")
                return

            if to_currency not in self.EXCHANGE_RATES:
                self._send_error(400, f"Unsupported target currency: {to_currency}")
                return

            # Perform conversion
            usd_amount = amount / self.EXCHANGE_RATES[from_currency]
            converted_amount = usd_amount * self.EXCHANGE_RATES[to_currency]

            # Add some realistic variance to simulate live rates
            variance = 0.02 * random.random() - 0.01  # +/- 1%
            converted_amount *= (1 + variance)

            response = {
                "from_currency": from_currency,
                "to_currency": to_currency,
                "original_amount": amount,
                "converted_amount": round(converted_amount, 2),
                "exchange_rate": round(self.EXCHANGE_RATES[to_currency] / self.EXCHANGE_RATES[from_currency], 4),
                "timestamp": time.time(),
                "source": "mock_exchange_api"
            }

            self._send_json_response(200, response)

        except ValueError as e:
            self._send_error(400, f"Invalid amount parameter: {e}")
        except Exception as e:
            self._send_error(500, f"Internal server error: {e}")

    def _get_rates(self):
        """Get all exchange rates"""
        response = {
            "base_currency": "USD",
            "rates": self.EXCHANGE_RATES,
            "timestamp": time.time(),
            "source": "mock_exchange_api"
        }
        self._send_json_response(200, response)

    def _send_json_response(self, status_code, data):
        """Send JSON response"""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        json_data = json.dumps(data, indent=2)
        self.wfile.write(json_data.encode())

    def _send_error(self, status_code, message):
        """Send error response"""
        error_response = {
            "error": True,
            "status_code": status_code,
            "message": message,
            "timestamp": time.time()
        }
        self._send_json_response(status_code, error_response)

    def log_message(self, format, *args):
        """Override to reduce log noise"""
        print(f"[{time.strftime('%H:%M:%S')}] {format % args}")

def run_currency_service(port=8080):
    """Run the currency service"""
    global start_time
    start_time = time.time()

    server_address = ('', port)
    httpd = HTTPServer(server_address, CurrencyServiceHandler)

    print(f"Currency Service Demo - Zero-Touch AI Delivery Validation")
    print(f"=" * 60)
    print(f"Server running on http://localhost:{port}")
    print(f"")
    print(f"Available endpoints:")
    print(f"  GET /health - Health check")
    print(f"  GET /convert?from=USD&to=EUR&amount=100 - Convert currency")
    print(f"  GET /rates - Get all exchange rates")
    print(f"")
    print(f"This represents the LIVE DEPLOYED ENDPOINT that would be")
    print(f"automatically created by the autonomous AI agency!")
    print(f"=" * 60)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print(f"\nShutting down currency service...")
        httpd.shutdown()

def test_endpoints():
    """Test the currency service endpoints"""
    import urllib.request

    base_url = "http://localhost:8080"

    test_cases = [
        "/health",
        "/convert?from=USD&to=EUR&amount=100",
        "/convert?from=EUR&to=JPY&amount=50",
        "/rates"
    ]

    print(f"\nTesting Currency Service Endpoints:")
    print(f"=" * 40)

    for endpoint in test_cases:
        try:
            response = urllib.request.urlopen(f"{base_url}{endpoint}")
            data = json.loads(response.read().decode())
            print(f"✓ {endpoint}")
            print(f"  Status: {response.status}")
            if "converted_amount" in data:
                print(f"  Result: {data['original_amount']} {data['from_currency']} = {data['converted_amount']} {data['to_currency']}")
            print()
        except Exception as e:
            print(f"✗ {endpoint} - Error: {e}")

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Test mode - run tests against existing server
        test_endpoints()
    else:
        # Server mode - start the service
        try:
            run_currency_service()
        except Exception as e:
            print(f"Failed to start currency service: {e}")
            sys.exit(1)