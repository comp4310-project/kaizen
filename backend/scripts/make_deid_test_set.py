"""Builds the de-identification test set (P3 Table 9): 150 comments with fake personal details.

    python scripts/make_deid_test_set.py

Writes tests/data/deid_test_set.jsonl. Every value is made up. Each line holds the
comment, the character spans of every personal detail, and "keep" spans (unit names and
lengths of time) that de-identification must leave alone. The seed is fixed, so rerunning
gives the same file.

Hard cases built in: names that are ordinary words ("Rose", "Will", "Bird"), names
written in lower case, mixed date formats, and numbers that look like IDs but are not
(doses, pain scores, room numbers).
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path

SEED = 4310
N_COMMENTS = 150
OUT = Path(__file__).resolve().parent.parent / "tests" / "data" / "deid_test_set.jsonl"

FIRST = [
    "Rose", "Grace", "Will", "Faith", "Hope", "Mark", "Bill", "June", "April", "Daisy",
    "Ray", "Dawn", "Pat", "Hunter", "Joy", "Priya", "Mohammed", "Wei", "Sarah", "David",
    "Aisha", "Liam", "Olivia", "Siobhan", "Jean-Luc", "Mei", "Tyler", "Fatima", "Noah", "Chloe",
]
LAST = [
    "Smith", "Patel", "Nguyen", "Tremblay", "Wong", "Singh", "Brown", "Bird", "Young",
    "King", "Little", "White", "Kowalski", "Okafor", "Lavoie", "Chen", "Ahmed", "Moreau",
]
UNITS = ["4B", "4A", "ICU", "the Emergency Department", "5A", "3A", "2A", "6A", "ward 4B", "unit 5A"]
DURATIONS = [
    "3 days", "six hours", "45 minutes", "two weeks", "overnight", "4 hours", "an hour",
    "the whole weekend", "2 days", "90 minutes", "five hours", "a week",
]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]

PATIENT = [
    "My mother waited {dur} in {unit} before anyone saw her. {dr} finally came around 3am.",
    "On {date} my husband {first} was told he could go home, then sat {dur} waiting for his discharge medications.",
    "{nurse} on {unit} was so kind to my dad. Please pass on our thanks.",
    "Nobody called me back. My number is {phone} and I left three messages for {dr}.",
    "I was discharged on {date} without any instructions about my wound dressing.",
    "The noise at night on {unit} was unbearable. I slept maybe {dur} in total.",
    "My health card number is {hcn} and the front desk still could not find my file.",
    "Please email me at {email} about my complaint. Patient record {mrn}.",
    "My daughter {first} had surgery on {date} and nobody told us when she would move to {unit}.",
    "{full} at the registration desk was rude and would not explain the wait.",
    "We waited {dur} for a bed. {dr} apologised but the delay kept happening.",
    "I am writing about my father, {full}, who was in {unit} from {date} to {date}.",
    "The pharmacy gave the wrong dose, 10 mg instead of 5 mg. Call me at {phone}.",
    "My pain was 8/10 and it took {dur} to get anything. Thanks to {lcname} who finally helped.",
    "{nurse} explained everything clearly before my procedure. Best care I have had.",
    "Room 412 was not cleaned for {dur}. I reported it to {nurse} on {date}.",
    "My chart number is {mrn}. I was told my results would be sent but nothing came.",
    "Contact {full} at {email} or {phone}, she is my power of attorney.",
    "Discharge on {date} was rushed. The prescription went to the wrong pharmacy.",
    "I have been coming here since 2019 and this was the worst visit. {dr} did not listen.",
    "{first} from the night shift checked on me every hour. Please thank her.",
    "My son {first} was left in a hallway bed in {unit} for {dur}.",
    "We were told on Monday that my mother would go home, then nothing happened until {date}.",
    "Signed, {full}, health card {hcn}",
    "The call bell was not answered for {dur}. I am in bed 3 and my record number is {mrn}.",
    "I spoke to {dr} and {nurse} and got two different answers about my medications.",
    "Visiting hours changed without notice. You can reach me at {email}.",
    "{full} was discharged on {date} without a follow-up appointment.",
    "Thank you to the {unit} team, especially {nurse}, for {dur} of excellent care.",
    "on the night shift {lcname} ignored my call bell for {dur}",
]
STAFF = [
    "Discharge meds not ready again for pt in {unit}. Pharmacy said {dur}. {full}, RN",
    "Bed 7 waited {dur} for transport to {unit}. Family upset. Reported by {nurse}.",
    "Patient {mrn} discharged {date} without med reconciliation.",
    "Not enough staff on {unit} nights. Two RNs for 28 patients again on {date}.",
    "{dr} paged three times over {dur}, no response. Patient deteriorating.",
    "Handover from ED incomplete for patient {full}, HCN {hcn}.",
    "Only one working IV pump on {unit} for {dur}.",
    "Pt family called {dr} directly at {phone}, should go through the unit.",
    "Escalated to charge nurse {first}. Still waiting on bed management after {dur}.",
    "Discharge summary for chart {mrn} not sent to family doctor, {dr}.",
    "Med error caught by {nurse} on {date}. Wrong patient label.",
    "Night noise complaints from pts in {unit}, construction started {date}.",
    "Contact me at {email} if you need more detail. {full}, RPN",
    "Lab results for MRN {mrn} delayed {dur}, physician not notified.",
    "Transfer from ICU to {unit} delayed {dur} waiting on cleaning.",
    "{full} NP covering {unit} today, page if needed.",
]
# Complaint forms and incident reports often end with contact or ID details.
PATIENT_ENDINGS = [
    " Please call me at {phone}.", " My email is {email}.", " - {full}", " My health card is {hcn}.",
    " This happened on {date}.", " {full}, {phone}", " Chart {mrn}.", " You can reach me at {email} or {phone}.",
]
STAFF_ENDINGS = [
    " MRN {mrn}.", " Incident date {date}.", " Pt chart {mrn}, seen {date}.",
    " Call me at {phone} if needed.", " Pt HCN {hcn}.",
]
ENDING_CHANCE = 0.6


def luhn_check_digit(nine: str) -> str:
    for d in range(10):
        digits = nine + str(d)
        total = 0
        for i, ch in enumerate(reversed(digits)):
            n = int(ch)
            if i % 2 == 1:
                n = n * 2 - 9 if n > 4 else n * 2
            total += n
        if total % 10 == 0:
            return str(d)
    raise AssertionError("unreachable")


class Filler:
    """Each method returns (text, [(start, end, type, kind)]) with spans relative to text."""

    def __init__(self, rng: random.Random) -> None:
        self.r = rng

    def _whole(self, text: str, typ: str, kind: str = "detail"):
        return text, [(0, len(text), typ, kind)]

    def _prefixed(self, prefix: str, value: str, typ: str):
        return prefix + value, [(len(prefix), len(prefix) + len(value), typ, "detail")]

    def first(self):
        return self._whole(self.r.choice(FIRST), "PERSON")

    def full(self):
        return self._whole(f"{self.r.choice(FIRST)} {self.r.choice(LAST)}", "PERSON")

    def dr(self):
        return self._prefixed(self.r.choice(["Dr. ", "Dr ", "Doctor "]), self.r.choice(LAST), "PERSON")

    def nurse(self):
        return self._prefixed(self.r.choice(["Nurse ", "nurse "]), self.r.choice(FIRST), "PERSON")

    def lcname(self):
        return self._prefixed("nurse ", self.r.choice(FIRST).lower(), "PERSON")

    def date(self):
        r = self.r
        m, d, y = r.randint(1, 12), r.randint(1, 28), r.choice([2025, 2026])
        month = MONTHS[m - 1]
        suffix = {1: "st", 2: "nd", 3: "rd", 21: "st", 22: "nd", 23: "rd"}.get(d, "th")
        text = r.choice([
            f"{month} {d}", f"{month} {d}{suffix}", f"{month[:3]}. {d}", f"{d} {month} {y}",
            f"{d}{suffix} of {month}", f"{d:02d}/{m:02d}/{y}", f"{y}-{m:02d}-{d:02d}",
            f"{m}/{d}/{y % 100}", f"{month} {d}, {y}", f"{month[:3]} {d}{suffix}",
        ])
        return self._whole(text, "DATE")

    def phone(self):
        r = self.r
        area, line = r.choice(["807", "416", "647", "705"]), f"01{r.randint(0, 99):02d}"
        text = r.choice([
            f"{area}-555-{line}", f"({area}) 555-{line}", f"{area}.555.{line}",
            f"{area}555{line}", f"+1 {area} 555 {line}", f"{area} 555 {line}",
        ])
        return self._whole(text, "PHONE")

    def email(self):
        r = self.r
        first, last = r.choice(FIRST).lower().replace("-", ""), r.choice(LAST).lower()
        user = r.choice([f"{first}.{last}", f"{first[0]}{last}{r.randint(10, 99)}", f"{first}_{last}"])
        return self._whole(f"{user}@{r.choice(['example.com', 'mail.example.ca', 'example.org'])}", "EMAIL")

    def hcn(self):
        r = self.r
        nine = str(r.randint(1, 9)) + "".join(str(r.randint(0, 9)) for _ in range(8))
        n = nine + luhn_check_digit(nine)
        version = "".join(r.choice("ABCDEFGHJKLMNPRSTVWXYZ") for _ in range(2))
        text = r.choice([
            f"{n[:4]}-{n[4:7]}-{n[7:]}", f"{n[:4]} {n[4:7]} {n[7:]}", n,
            f"{n[:4]}-{n[4:7]}-{n[7:]}-{version}", f"{n[:4]} {n[4:7]} {n[7:]} {version}",
        ])
        return self._whole(text, "HEALTH_CARD")

    def mrn(self):
        r = self.r
        text = r.choice([
            f"M{r.randint(1000000, 9999999)}", str(r.randint(10000000, 99999999)),
            f"TB-{r.randint(1000000, 9999999)}", str(r.randint(100000, 999999)),
        ])
        return self._whole(text, "RECORD_NUMBER")

    def unit(self):
        return self._whole(self.r.choice(UNITS), "UNIT", "keep")

    def dur(self):
        return self._whole(self.r.choice(DURATIONS), "DURATION", "keep")


def expand(template: str, filler: Filler) -> tuple[str, list[dict], list[dict]]:
    out, details, keep, pos = [], [], [], 0
    for piece in re.split(r"(\{\w+\})", template):
        if piece.startswith("{") and piece.endswith("}"):
            text, spans = getattr(filler, piece[1:-1])()
            for start, end, typ, kind in spans:
                (details if kind == "detail" else keep).append(
                    {"start": pos + start, "end": pos + end, "type": typ}
                )
        else:
            text = piece
        out.append(text)
        pos += len(text)
    return "".join(out), details, keep


def main() -> None:
    rng = random.Random(SEED)
    filler = Filler(rng)
    templates = [("patient", t) for t in PATIENT] + [("staff", t) for t in STAFF]
    rows = []
    for i in range(N_COMMENTS):
        voice, template = templates[i] if i < len(templates) else rng.choice(templates)
        if rng.random() < ENDING_CHANCE:
            template += rng.choice(PATIENT_ENDINGS if voice == "patient" else STAFF_ENDINGS)
        text, details, keep = expand(template, filler)
        rows.append({"id": i + 1, "voice": voice, "text": text, "details": details, "keep": keep})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")

    n_details = sum(len(r["details"]) for r in rows)
    print(f"wrote {len(rows)} comments with {n_details} personal details to {OUT}")


if __name__ == "__main__":
    main()
