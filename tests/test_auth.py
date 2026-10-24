import unittest
from edge_workspace import resolve_owner


class FakeUser(dict):
    @property
    def is_logged_in(self):
        return self.get("logged_in", False)


class FakeSt:
    def __init__(self, secrets=None, user=None):
        self.secrets = secrets or {}
        self.user = FakeUser(user or {})


class AuthTests(unittest.TestCase):
    def test_unconfigured(self):
        self.assertEqual(resolve_owner(FakeSt()), (None, "CONFIGURATION_REQUIRED"))

    def test_locked_without_login(self):
        st = FakeSt({"auth": {}, "EDGE_JOURNAL_ALLOWED_EMAILS": ["owner@example.com"]})
        self.assertEqual(resolve_owner(st), (None, "LOGIN_REQUIRED"))

    def test_allowed_verified(self):
        st = FakeSt({"auth": {}, "EDGE_JOURNAL_ALLOWED_EMAILS": "owner@example.com"},
                    {"logged_in": True, "email": "owner@example.com",
                     "email_verified": True, "iss": "issuer", "sub": "subject"})
        owner, status = resolve_owner(st)
        self.assertEqual(status, "OK")
        self.assertEqual(len(owner), 64)

    def test_rejected_unlisted(self):
        st = FakeSt({"auth": {}, "EDGE_JOURNAL_ALLOWED_EMAILS": ["owner@example.com"]},
                    {"logged_in": True, "email": "intruder@example.com",
                     "email_verified": True, "iss": "issuer", "sub": "subject"})
        self.assertEqual(resolve_owner(st), (None, "UNAUTHORIZED"))

    def test_rejected_unverified(self):
        st = FakeSt({"auth": {}, "EDGE_JOURNAL_ALLOWED_EMAILS": ["owner@example.com"]},
                    {"logged_in": True, "email": "owner@example.com",
                     "email_verified": False, "iss": "issuer", "sub": "subject"})
        self.assertEqual(resolve_owner(st), (None, "UNAUTHORIZED"))


if __name__ == "__main__":
    unittest.main()
