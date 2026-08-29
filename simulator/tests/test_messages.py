import unittest

from src.main import identified


class MessageIdentityTests(unittest.TestCase):
    def test_identified_adds_unique_message_ids(self):
        first = identified({"printer_id": "P1"})
        second = identified({"printer_id": "P1"})

        self.assertEqual(first["printer_id"], "P1")
        self.assertEqual(len(first["message_id"]), 32)
        self.assertNotEqual(first["message_id"], second["message_id"])

    def test_identified_overrides_untrusted_message_id(self):
        payload = identified({"message_id": "external", "printer_id": "P1"})

        self.assertNotEqual(payload["message_id"], "external")


if __name__ == "__main__":
    unittest.main()
