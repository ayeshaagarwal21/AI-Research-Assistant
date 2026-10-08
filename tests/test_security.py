import unittest

import jwt

from backend.app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


class PasswordTests(unittest.TestCase):
    def test_hash_and_verify(self):
        hashed = hash_password("correct horse")
        self.assertNotIn("correct horse", hashed)
        self.assertTrue(verify_password("correct horse", hashed))
        self.assertFalse(verify_password("wrong", hashed))

    def test_same_password_gets_different_hashes(self):
        self.assertNotEqual(hash_password("abc123"), hash_password("abc123"))

    def test_malformed_hash_is_rejected_not_crashing(self):
        self.assertFalse(verify_password("x", "not-a-valid-hash"))
        self.assertFalse(verify_password("x", "bcrypt$aa$bb"))


class TokenTests(unittest.TestCase):
    def test_round_trip(self):
        token = create_access_token({"sub": "42"})
        self.assertEqual(decode_access_token(token)["sub"], "42")

    def test_expired_token_is_rejected(self):
        token = create_access_token({"sub": "42"}, expires_minutes=-1)
        with self.assertRaises(jwt.PyJWTError):
            decode_access_token(token)

    def test_tampered_token_is_rejected(self):
        token = create_access_token({"sub": "42"})
        with self.assertRaises(jwt.PyJWTError):
            decode_access_token(token[:-2] + "xx")


if __name__ == "__main__":
    unittest.main()
