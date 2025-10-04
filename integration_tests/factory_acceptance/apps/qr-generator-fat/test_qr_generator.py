"""
Test suite for QR Code Generator Service
Tests external dependency integration and functionality
"""
import pytest
import base64
import unittest
from io import BytesIO
import requests
from PIL import Image

@pytest.mark.crust
class TestQRGenerator(unittest.TestCase):
    """Test QR code generator functionality"""
    BASE_URL = 'http://localhost:5004'

    @pytest.mark.crust
    def test_health_check(self):
        """Test health check endpoint"""
        response = requests.get(f'{self.BASE_URL}/api/health')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'healthy')
        self.assertEqual(data['service'], 'qr-generator')
        self.assertEqual(data['test_type'], 'external_dependency_fat')
        deps = data.get('dependencies', {})
        self.assertTrue(deps.get('qrcode') == 'installed')
        self.assertTrue(deps.get('Pillow') == 'installed')

    @pytest.mark.crust
    def test_generate_qr_code(self):
        """Test single QR code generation"""
        test_text = 'Hello from FAT test'
        response = requests.post(f'{self.BASE_URL}/api/generate', json={'text': test_text}, headers={'Content-Type': 'application/json'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('qr_code', data)
        self.assertEqual(data['format'], 'png')
        self.assertEqual(data['encoding'], 'base64')
        self.assertEqual(data['text'], test_text)
        try:
            img_data = base64.b64decode(data['qr_code'])
            img = Image.open(BytesIO(img_data))
            self.assertEqual(img.format, 'PNG')
        except Exception as e:
            self.fail(f'Invalid QR code image: {e}')

    @pytest.mark.crust
    def test_generate_with_options(self):
        """Test QR generation with custom options"""
        response = requests.post(f'{self.BASE_URL}/api/generate', json={'text': 'Custom QR', 'size': 15, 'border': 2, 'fill_color': 'blue', 'back_color': 'yellow'}, headers={'Content-Type': 'application/json'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('qr_code', data)

    @pytest.mark.crust
    def test_batch_generation(self):
        """Test batch QR code generation"""
        items = ['Item 1', 'Item 2', 'Item 3']
        response = requests.post(f'{self.BASE_URL}/api/batch', json={'items': items}, headers={'Content-Type': 'application/json'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['count'], 3)
        self.assertEqual(len(data['results']), 3)
        for i, result in enumerate(data['results']):
            self.assertEqual(result['text'], items[i])
            self.assertIn('qr_code', result)

    @pytest.mark.crust
    def test_missing_text_parameter(self):
        """Test error handling for missing text"""
        response = requests.post(f'{self.BASE_URL}/api/generate', json={}, headers={'Content-Type': 'application/json'})
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('error', data)

    @pytest.mark.crust
    def test_validate_dependencies(self):
        """Test dependency validation endpoint"""
        response = requests.post(f'{self.BASE_URL}/api/validate')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        deps = data['dependencies']
        self.assertTrue(deps['qrcode']['installed'])
        self.assertTrue(deps['Pillow']['installed'])
        self.assertTrue(deps['flask']['installed'])
        self.assertTrue(deps['flask_cors']['installed'])
if __name__ == '__main__':
    unittest.main(verbosity=2)