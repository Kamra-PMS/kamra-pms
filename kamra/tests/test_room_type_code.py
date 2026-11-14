"""Room type codes must stay ASCII — Arabic keyboard marks break the ID."""

import unittest

from kamra.kamra.doctype.room_type.room_type import clean_room_type_code


class TestRoomTypeCode(unittest.TestCase):
	def test_strips_arabic_dammatan_prefix(self):
		# U+064C DAMMATAN left in front when the layout was still Arabic
		self.assertEqual(clean_room_type_code("\u064cRWBT3"), "RWBT3")

	def test_keeps_latin_and_digits(self):
		self.assertEqual(clean_room_type_code("BRBT"), "BRBT")
		self.assertEqual(clean_room_type_code("DLX-2"), "DLX-2")

	def test_rejects_empty_after_clean(self):
		self.assertEqual(clean_room_type_code("ٌٌ"), "")
		self.assertEqual(clean_room_type_code("@@@"), "")
