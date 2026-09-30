"""Offline teaching example inspired by agent_p; not its production code."""

from dataclasses import dataclass
from enum import Enum
import hashlib
import json


class Availability(Enum):
    FREE = "free"
    TAKEN = "taken"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Command:
    client_ref: str
    service_refs: tuple[str, ...]
    staff_ref: str
    slot: str

    def fingerprint(self) -> str:
        payload = [self.client_ref, sorted(self.service_refs), self.staff_ref, self.slot]
        return hashlib.sha256(json.dumps(payload).encode()).hexdigest()


@dataclass(frozen=True)
class Outcome:
    status: str
    message: str


class FakeCRM:
    """No network, real catalog, customers or credentials. Memory only."""

    def __init__(self, response: str = "success"):
        if response not in {"success", "rejected", "uncertain"}:
            raise ValueError("Unsupported fake response")
        self.response = response
        self.calls = 0

    def create(self, command: Command) -> str:
        self.calls += 1
        return self.response


class BookingExample:
    """Single-process illustration; no distributed/concurrency guarantee."""

    def __init__(self, crm: FakeCRM):
        self.crm = crm
        self.receipts: dict[str, Outcome] = {}

    def confirm(self, command: Command, *, confirmed: bool,
                availability: Availability, state_matches: bool = True) -> Outcome:
        if not confirmed:
            return Outcome("confirmation_needed", "Сначала подтвердите параметры записи.")
        if not state_matches:
            return Outcome("state_conflict", "Параметры разошлись. Повторно выберите время.")
        if not command.service_refs or not all((command.client_ref, command.staff_ref, command.slot)):
            return Outcome("incomplete", "Нужно заполнить параметры записи.")
        key = command.fingerprint()
        if key in self.receipts:
            return self.receipts[key]
        if availability is not Availability.FREE:
            if availability is Availability.TAKEN:
                return Outcome("slot_taken", "Это время уже занято. Выберите другое.")
            return Outcome("availability_unknown", "Не удалось проверить время. Запись не создана.")
        response = self.crm.create(command)
        if response == "success":
            result = Outcome("created", "Тестовая CRM подтвердила запись DEMO-001.")
        elif response == "rejected":
            result = Outcome("rejected", "Тестовая CRM отклонила запрос. Записи нет.")
        else:
            # Do not retry an external action blindly after an uncertain result.
            result = Outcome("needs_review", "Ответ CRM неясен. Нужна сверка перед повтором.")
        self.receipts[key] = result
        return result


def demo_results() -> list[dict[str, object]]:
    command = Command("DEMO-CUSTOMER-1", ("DEMO-SERVICE-1",), "DEMO-STAFF-1", "2030-01-15T15:00")
    rows = []
    for label, availability, matches, response in [
        ("Запись подтверждена", Availability.FREE, True, "success"),
        ("Время занято", Availability.TAKEN, True, "success"),
        ("Расписание недоступно", Availability.UNKNOWN, True, "success"),
        ("Конфликт параметров", Availability.FREE, False, "success"),
        ("Неясный ответ CRM", Availability.FREE, True, "uncertain"),
    ]:
        crm = FakeCRM(response)
        example = BookingExample(crm)
        outcome = example.confirm(command, confirmed=True, availability=availability, state_matches=matches)
        rows.append({"scenario": label, "status": outcome.status, "message": outcome.message, "crm_calls": crm.calls})
    crm = FakeCRM()
    example = BookingExample(crm)
    first = example.confirm(command, confirmed=True, availability=Availability.FREE)
    second = example.confirm(command, confirmed=True, availability=Availability.FREE)
    rows.append({"scenario": "Повтор подтверждения", "status": second.status,
                 "message": "Возвращён прежний результат DEMO-001; второй записи нет.",
                 "crm_calls": crm.calls, "same_result": first == second})
    return rows


if __name__ == "__main__":
    print(json.dumps(demo_results(), ensure_ascii=False, indent=2))
