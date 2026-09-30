"""Behavior checks for this isolated example, not a production agent audit."""

from dataclasses import replace
import unittest
from scenario_demo import Availability, BookingExample, Command, FakeCRM


class BookingContractTests(unittest.TestCase):
    def setUp(self):
        self.command = Command("DEMO-CUSTOMER-1", ("DEMO-SERVICE-1",), "DEMO-STAFF-1", "2030-01-15T15:00")
        self.crm = FakeCRM()
        self.example = BookingExample(self.crm)

    def run_command(self, **kwargs):
        return self.example.confirm(self.command, confirmed=True,
                                    availability=kwargs.pop("availability", Availability.FREE), **kwargs)

    def test_no_confirmation_means_no_side_effect(self):
        result = self.example.confirm(self.command, confirmed=False, availability=Availability.FREE)
        self.assertEqual(result.status, "confirmation_needed")
        self.assertEqual(self.crm.calls, 0)

    def test_available_and_confirmed_creates_once(self):
        self.assertEqual(self.run_command().status, "created")
        self.assertEqual(self.crm.calls, 1)

    def test_taken_slot_never_calls_create(self):
        self.assertEqual(self.run_command(availability=Availability.TAKEN).status, "slot_taken")
        self.assertEqual(self.crm.calls, 0)

    def test_unknown_availability_never_calls_create(self):
        self.assertEqual(self.run_command(availability=Availability.UNKNOWN).status, "availability_unknown")
        self.assertEqual(self.crm.calls, 0)

    def test_state_conflict_blocks_write(self):
        self.assertEqual(self.run_command(state_matches=False).status, "state_conflict")
        self.assertEqual(self.crm.calls, 0)

    def test_retry_returns_previous_receipt_without_new_write(self):
        first = self.run_command()
        self.assertEqual(first, self.run_command())
        self.assertEqual(self.crm.calls, 1)

    def test_changed_slot_is_a_different_command(self):
        self.run_command()
        changed = replace(self.command, slot="2030-01-15T16:00")
        self.example.confirm(changed, confirmed=True, availability=Availability.FREE)
        self.assertEqual(self.crm.calls, 2)

    def test_service_order_does_not_change_command_identity(self):
        a = replace(self.command, service_refs=("DEMO-SERVICE-1", "DEMO-SERVICE-2"))
        b = replace(a, service_refs=tuple(reversed(a.service_refs)))
        self.assertEqual(a.fingerprint(), b.fingerprint())

    def test_uncertain_provider_result_requires_review_before_retry(self):
        crm = FakeCRM("uncertain")
        example = BookingExample(crm)
        for _ in range(2):
            result = example.confirm(self.command, confirmed=True, availability=Availability.FREE)
            self.assertEqual(result.status, "needs_review")
        self.assertEqual(crm.calls, 1)

    def test_provider_rejection_is_not_reported_as_success(self):
        example = BookingExample(FakeCRM("rejected"))
        self.assertEqual(example.confirm(self.command, confirmed=True,
                                        availability=Availability.FREE).status, "rejected")

    def test_incomplete_command_never_calls_create(self):
        result = self.example.confirm(replace(self.command, service_refs=()),
                                      confirmed=True, availability=Availability.FREE)
        self.assertEqual(result.status, "incomplete")
        self.assertEqual(self.crm.calls, 0)


if __name__ == "__main__":
    unittest.main()
