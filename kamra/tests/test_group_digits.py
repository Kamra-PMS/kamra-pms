from unittest import TestCase

from kamra.localization import group_digits


class TestGroupDigits(TestCase):
	def test_formats_like_the_screen(self):
		self.assertEqual(group_digits(2940.0, True), "2,940")
		self.assertEqual(group_digits(28360.4, True), "28,360.40")
		self.assertEqual(group_digits(120000, True), "1,20,000")
		self.assertEqual(group_digits(12345678.5, True), "1,23,45,678.50")
		self.assertEqual(group_digits(999, True), "999")
		self.assertEqual(group_digits(0, True), "0")
		self.assertEqual(group_digits(120000), "120,000")
		self.assertEqual(group_digits(1250.0), "1,250")
