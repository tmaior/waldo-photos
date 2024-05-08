from tests.classes import CDCTestCase

import requests
import unittest
import time


class TestHealthCheck(CDCTestCase):
    def test_get_200(self):
        response = requests.get("http://cdc_service:5000/health-check/")
        self.assertEqual(response.status_code, 200)
