"""Builds the synthetic feedback set (P3 section 3.1): about 1,200 comments with 8 built-in problems.

    python scripts/make_synthetic.py [--seed 4310] [--n 1200] [--test-size 300] [--out tests/data]

Writes, in the output folder:

    synthetic.csv            every comment in the CSV upload format (text, source, unit, date)
    synthetic.jsonl          the same comments in the same order, with gold labels and `planted`
    synthetic_train.jsonl    everything not in the test split
    synthetic_test.jsonl     300 held-out comments (P3 section 5.1)
    synthetic_problems.json  the 8 built-in problems: id, description, who reports them

The JSONL lines are what `kaizen.classify evaluate` and `kaizen.issues recovery` read: `id`,
`text`, `source`, `unit`, `date`, `sentiment`, `categories`, `stage`, `urgency` and `planted`
(a problem id, or null for background comments). Line n of the JSONL is row n of the CSV.

Every comment is written from templates in this file, not by an LLM, and contains no names or
other personal details, so there is nothing for de-identification to change. Each template
carries its own labels, chosen with docs/labelling-guide.md. They are template labels, not
hand labels, so they are only as good as the person who wrote the template.

The seed fixes everything: the same seed and size always give byte-identical files.

To make grouping a real test, each problem is written many ways: different openings,
vocabulary, length and sentence shape, staff shorthand, typos, lower case, and sometimes a
line of praise before the complaint. Two of the problems are both about discharge (late
take-home medications and missing instructions) and have to be told apart.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import random
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

DEFAULT_SEED = 4310
DEFAULT_N = 1200
DEFAULT_TEST_SIZE = 300
OUT = Path(__file__).resolve().parent.parent / "tests" / "data"

# 12 weeks, Sunday 9 August to Saturday 31 October 2026. Week 12 is 25 to 31 October, which
# is the "last 7 days" the rising flag looks at, since the newest comment is on the 31st.
START = date(2026, 8, 9)
DAYS = 84

WARDS = ["2A", "3A", "4A", "4B", "5A"]
ALL_UNITS = ["ED", "ICU", "2A", "3A", "4A", "4B", "5A", "6A"]

# Short codes so a template fits on one line.
SENTIMENT = {"N": "negative", "U": "neutral", "P": "positive"}
CATEGORY = {
    "Q": "quality",
    "S": "safety",
    "E": "environment",
    "I": "institutional_processes",
    "L": "listening",
    "C": "communication",
    "R": "respect_and_rights",
}
STAGE = {
    "AD": "admissions",
    "EX": "examination_and_diagnosis",
    "WARD": "care_on_the_ward",
    "OP": "operations_and_procedures",
    "DIS": "discharge_and_transfers",
    "UNC": "unclear",
}
URGENCY = {"l": "low", "m": "medium", "h": "high"}
URGENCY_ORDER = ["low", "medium", "high"]


@dataclass(frozen=True)
class T:
    """One template: text plus the labels a comment written from it gets."""

    text: str
    sentiment: str  # N, U or P
    cats: str  # category letters, e.g. "IC"
    stage: str
    urgency: str  # l, m or h


@dataclass(frozen=True)
class Extra:
    """A sentence added after the main one. Adds categories and can raise urgency."""

    text: str
    cats: str = ""
    urgency: str = "l"


@dataclass
class Problem:
    id: str
    description: str
    count: int  # at the default size of 1,200
    staff_share: float  # 0 = patients and families only, 1 = staff only
    units: list[str]
    patient: list[T] = field(default_factory=list)
    staff: list[T] = field(default_factory=list)
    patient_extras: list[Extra] = field(default_factory=list)
    staff_extras: list[Extra] = field(default_factory=list)
    weekly: list[int] | None = None  # fixed weekly counts, for the rising problem

    @property
    def reporters(self) -> str:
        if self.staff_share == 0:
            return "patient_family"
        if self.staff_share == 1:
            return "staff"
        return "both"


HOURS = ["three hours", "4 hours", "five hours", "six hours", "over 5 hours", "7 hours", "most of the day", "the whole afternoon"]
LATE = ["4pm", "after 5", "6 in the evening", "nearly 8pm", "supper time", "half past four"]
MINS = ["20 minutes", "25 minutes", "40 minutes", "nearly an hour", "over half an hour", "45 minutes"]
REL = ["mother", "father", "husband", "wife", "son", "daughter", "grandmother", "grandad", "partner", "mum", "dad"]

PROBLEMS = [
    Problem(
        id="discharge_meds_delay",
        description="Discharge held up for hours waiting for take-home medications from pharmacy",
        count=130,
        staff_share=0.35,
        units=WARDS,
        patient=[
            T("We were told my {rel} could go home at 10 in the morning but we didn't leave until {late} because the pharmacy hadn't sent up the take-home medications.", "N", "I", "DIS", "m"),
            T("Discharge took the entire day. The doctor signed the papers before lunch and then we just sat there waiting for the prescription to come from pharmacy.", "N", "I", "DIS", "m"),
            T("Waited {hours} for discharge meds.", "N", "I", "DIS", "l"),
            T("Ready to go home by 9am, finally left after {late}. Every time we asked it was 'still waiting on pharmacy'.", "N", "I", "DIS", "m"),
            T("The only bad part was going home. The tablets I needed to take home took {hours} to arrive from the pharmacy downstairs.", "N", "I", "DIS", "l"),
            T("why does it take {hours} to get a bag of pills from pharmacy?? I was dressed and sitting on the bed all afternoon", "N", "I", "DIS", "m"),
            T("My {rel} was medically cleared to leave {ward} but had to stay another night because the discharge prescription was never filled.", "N", "I", "DIS", "m"),
            T("I was discharged in theory at noon. In practice I sat in the lounge until {late} waiting for my medication bag.", "N", "I", "DIS", "l"),
            T("Spent most of the day waiting for pharmacy to release my going-home medicines. The bed could have gone to someone else hours earlier.", "N", "I", "DIS", "m"),
            T("Leaving hospital should not take longer than the operation did. {hours} for a prescription is ridiculous.", "N", "I", "DIS", "m"),
            T("We had a ride booked and missed it because the meds for home were not ready. Had to pay for a taxi in the end.", "N", "I", "DIS", "l"),
            T("Told at the morning round I'd be home for lunch. Got home at {late}. The hold up was the pharmacy order every single time we asked.", "N", "I", "DIS", "m"),
            T("Its the second time my {rel} has been discharged from {ward} and both times the take home medications were hours late", "N", "I", "DIS", "m"),
            T("The whole discharge was let down by pharmacy. Paperwork done, nurse ready, but no medications until {late}.", "N", "I", "DIS", "m"),
            T("Sat waiting on prescriptions for {hours} after being told I could leave.", "N", "I", "DIS", "l"),
            T("Could the pharmacy prepare discharge prescriptions the night before? We waited {hours} on the day we went home.", "U", "I", "DIS", "l"),
            T("Suggestion: let patients collect their take-home medicines from the outpatient pharmacy instead of waiting on the ward all day.", "U", "I", "DIS", "l"),
            T("Is there a reason discharge medications can't be ordered a day ahead when everyone knows the leaving date?", "U", "I", "DIS", "l"),
        ],
        staff=[
            T("Pt ready for d/c at 10:00, meds from pharmacy not up until 16:00. Bed blocked for ED all day.", "N", "I", "DIS", "m"),
            T("Discharge meds delayed again on {ward}. Three patients waiting on pharmacy at shift change.", "N", "I", "DIS", "m"),
            T("We cannot discharge before 2pm most days because take-home prescriptions come up so late. It backs up admissions from emergency.", "N", "I", "DIS", "m"),
            T("Pharmacy turnaround for discharge scripts was {hours} today. Families keep asking us and we have no answer for them.", "N", "IC", "DIS", "m"),
            T("Patient sat in the discharge lounge {hours} waiting for take-home meds.", "N", "I", "DIS", "l"),
            T("Flagged the delay on discharge medications with pharmacy again. Same issue as last week, nothing has changed.", "N", "I", "DIS", "m"),
            T("Discharge order written at 0900, med rec and scripts not done by pharmacy until mid afternoon.", "N", "I", "DIS", "m"),
            T("Bed flow on {ward} is stuck because discharge medications are the bottleneck. ED has admitted patients waiting for our beds.", "N", "I", "DIS", "m"),
            T("d/c delayed {hours} waiting pharmacy. pt and family frustrated", "N", "I", "DIS", "m"),
            T("Nights keep getting handed patients who should have gone home that afternoon, purely because of late discharge prescriptions.", "N", "I", "DIS", "m"),
            T("Proposal: pharmacy starts discharge prescriptions when the expected discharge date is set, not when the order is signed.", "U", "I", "DIS", "l"),
            T("Can we get a pharmacy tech assigned to discharges on {ward} in the mornings?", "U", "I", "DIS", "l"),
        ],
        patient_extras=[
            Extra("Nobody could tell us why it was taking so long.", "C"),
            Extra("Every time we asked we got a different answer.", "C"),
            Extra("My {rel} was exhausted and upset by the time we left.", "", "m"),
            Extra("In the end we left without them and had to drive back the next day to collect them.", "", "m"),
            Extra("He missed his evening dose because of it.", "S", "h"),
            Extra("The nurses were apologetic, it clearly isn't their fault."),
            Extra("A neighbour was picking us up and she waited in the car park for ages."),
            Extra("All because the pharmacy was slow."),
            Extra("Waiting this long for medicine to go home with is not right.", "", "m"),
        ],
        staff_extras=[
            Extra("Family took it out on the nurse, not pharmacy.", "", "m"),
            Extra("This happens most days.", "", "m"),
            Extra("No one in pharmacy answered the phone.", "C", "m"),
            Extra("Pharmacy delays on discharge again.", "", "m"),
        ],
    ),
    Problem(
        id="discharge_instructions",
        description="Patients sent home without clear instructions about medications, wound care or follow-up",
        count=90,
        staff_share=0.28,
        units=WARDS,
        patient=[
            T("We were sent home with a bag of new tablets and nobody explained which ones replaced his old ones.", "N", "CS", "DIS", "h"),
            T("Nobody told us how to look after the wound once we got home. The sheet we were given was for a different operation.", "N", "C", "DIS", "m"),
            T("The discharge instructions were a photocopy that was hard to read and didn't say when to book a follow up.", "N", "C", "DIS", "m"),
            T("I left not knowing whether I could shower, drive, or go back to work. Nobody went over any of it with me.", "N", "C", "DIS", "m"),
            T("My {rel} came home on a blood thinner and we were given no information about it at all.", "N", "CS", "DIS", "h"),
            T("The nurse rushed through the discharge papers in about two minutes while answering a call bell. We didn't understand half of it.", "N", "C", "DIS", "m"),
            T("no one explained the new insulin doses before we left. had to phone the family doctor the next morning to find out", "N", "CS", "DIS", "h"),
            T("We got two different sets of instructions from the doctor and the nurse about his medicines at home.", "N", "C", "DIS", "m"),
            T("The follow-up appointment we were told about was never booked and nobody said who was meant to book it.", "N", "CI", "DIS", "m"),
            T("Discharge letter said to stop a medicine the pharmacist told us to keep taking. Which is it?", "N", "CS", "DIS", "h"),
            T("I asked what signs of infection to watch for at home and was told 'just come back if it gets bad'.", "N", "CL", "DIS", "m"),
            T("Home care instructions were all medical jargon. My {rel}'s first language isn't English and no interpreter was offered.", "N", "CR", "DIS", "m"),
            T("Instructions for after discharge were incomplete.", "N", "C", "DIS", "m"),
            T("He was sent home still confused and we were never told he needed someone with him. He fell that night.", "N", "CS", "DIS", "h"),
            T("Went home from {ward} with no idea when the stitches come out or who takes them out.", "N", "C", "DIS", "m"),
            T("It would help to have discharge instructions in plain language, with a number to call if you have questions.", "U", "C", "DIS", "l"),
            T("Could someone sit down with families for five minutes before discharge to go through the medication list?", "U", "C", "DIS", "l"),
        ],
        staff=[
            T("Patients on {ward} are going home without anyone doing the discharge teaching. There is no time on day shift.", "N", "CE", "DIS", "m"),
            T("Had a call from a family who did not know their dad's new medication schedule. The discharge summary was never printed for them.", "N", "C", "DIS", "m"),
            T("The discharge instructions template is out of date and still sends people to a clinic that closed.", "N", "CI", "DIS", "m"),
            T("Readmitted pt this week who had gone home without being told to stop the old blood pressure tablets.", "N", "CS", "DIS", "h"),
            T("Teaching for new anticoagulant patients is not being documented at discharge, so nobody knows if it happened.", "N", "CS", "DIS", "h"),
            T("Discharge paperwork handed over with no explanation because the RN had six other patients.", "N", "CE", "DIS", "m"),
            T("Families leave without written wound care instructions more often than not.", "N", "C", "DIS", "m"),
        ],
        patient_extras=[
            Extra("We ended up phoning the ward twice the next day.", "", "m"),
            Extra("The surgeon was brilliant, it's a shame the end of the stay let it down."),
            Extra("It was very stressful.", "", "m"),
            Extra("He was back in emergency three days later.", "S", "h"),
            Extra("Nobody explained anything properly before we left.", "C", "m"),
            Extra("We felt completely lost once we got home.", "", "m"),
        ],
        staff_extras=[
            Extra("Not the first time.", "", "m"),
            Extra("We need protected time for this."),
            Extra("Discharge teaching keeps getting skipped.", "C", "m"),
        ],
    ),
    Problem(
        id="ed_wait_no_updates",
        description="Long waits in emergency with nobody giving updates",
        count=90,
        staff_share=0.28,
        units=["ED"],
        patient=[
            T("Waited {hours} in emergency before anyone saw my {rel}, and nobody came to tell us what was happening.", "N", "IC", "AD", "m"),
            T("Triage was quick but then we sat in the waiting room for {hours} with no update.", "N", "IC", "AD", "m"),
            T("{hours} in the ER waiting room with a broken wrist. Not one person told us how much longer it would be.", "N", "IC", "AD", "m"),
            T("The wait in emergency was unacceptable. My {rel} is elderly and was on a hard plastic chair for {hours}.", "N", "IQ", "AD", "m"),
            T("We were in the ED overnight waiting for a bed upstairs.", "N", "I", "AD", "m"),
            T("Asked the triage desk three times how long it would be and got a shrug each time.", "N", "ICL", "AD", "m"),
            T("ER waits are crazy. {hours} and counting, no water, no updates.", "N", "IC", "AD", "m"),
            T("My {rel} collapsed in the waiting room after {hours}. Only then did someone take them through.", "N", "IS", "AD", "h"),
            T("Long wait in emergency before admission. Once we got to the ward things were much better.", "N", "I", "AD", "m"),
            T("Nobody explains the order people are seen in. People who came in after us went first and no one said why.", "N", "IC", "AD", "m"),
            T("spent the night on a stretcher in the corridor in emergency waiting for a bed", "N", "IE", "AD", "m"),
            T("The emergency department needs more staff. We waited {hours} to be seen for chest pain.", "N", "IES", "AD", "h"),
            T("Sat in emerg for {hours} without a single update from anyone.", "N", "IC", "AD", "m"),
            T("Could the emergency waiting room have a screen with rough wait times?", "U", "C", "AD", "l"),
            T("A volunteer checking on people in the ED waiting room every so often would make a big difference.", "U", "C", "AD", "l"),
        ],
        staff=[
            T("ED holding {n} admitted patients this morning with no beds upstairs.", "N", "I", "AD", "m"),
            T("Triage reassessments are not happening on time when the waiting room is this full.", "N", "IS", "AD", "h"),
            T("People in the ED waiting room have no idea of wait times and keep asking the triage nurse, who has no time to answer.", "N", "IC", "AD", "m"),
            T("Ambulance offload delays again, crews waiting {hours} to hand over.", "N", "I", "AD", "m"),
            T("Two RNs short in emergency tonight and the wait to be seen went past {hours}.", "N", "IE", "AD", "m"),
            T("Admitted patients boarding in ED for over a day waiting for a ward bed.", "N", "I", "AD", "m"),
        ],
        patient_extras=[
            Extra("There were no updates at all.", "C", "m"),
            Extra("My {rel} was in a lot of pain.", "Q", "m"),
            Extra("The staff were run off their feet, I don't blame them."),
            Extra("Once we were seen the doctor was very good."),
            Extra("No one kept us informed while we waited.", "C", "m"),
            Extra("The waiting room was packed.", "", "m"),
        ],
        staff_extras=[
            Extra("Same as every Monday.", "", "m"),
            Extra("Escalated to the manager on call."),
            Extra("Waiting room overflowing.", "", "m"),
        ],
    ),
    Problem(
        id="call_bells_unanswered",
        description="Call bells left unanswered on the wards, mostly at night and blamed on short staffing",
        count=90,
        staff_share=0.28,
        units=WARDS + ["6A"],
        patient=[
            T("I pressed the call bell and it was {mins} before anyone came.", "N", "Q", "WARD", "m"),
            T("Call bells go unanswered at night. My {rel} needed the toilet and waited {mins}.", "N", "Q", "WARD", "m"),
            T("Rang for help for {mins} and ended up wetting the bed. Humiliating.", "N", "QR", "WARD", "m"),
            T("There are not enough nurses on {ward} at night. The buzzer just rings and rings.", "N", "QE", "WARD", "m"),
            T("My {rel} tried to get up alone because nobody answered the bell, and fell.", "N", "QS", "WARD", "h"),
            T("Asked for pain relief, pressed the buzzer, waited {mins}. When I asked again I was told they were busy.", "N", "QL", "WARD", "m"),
            T("The bell beside my bed was broken for two days and I had to shout for help.", "N", "ES", "WARD", "m"),
            T("Nurses were kind when they came but it took forever to get one to come.", "N", "Q", "WARD", "m"),
            T("Waited {mins} for help to the bathroom after pressing the call button more than once", "N", "Q", "WARD", "m"),
            T("Short staffed every night I was there. Call bells going off constantly and nobody had time to answer them.", "N", "EQ", "WARD", "m"),
            T("buzzed and buzzed, nobody came for {mins}", "N", "Q", "WARD", "m"),
            T("Maybe the call bell could show at the desk how long it has been ringing?", "U", "Q", "WARD", "l"),
        ],
        staff=[
            T("Two nurses for 28 patients on {ward} nights. Call bells left ringing because we physically cannot get to them.", "N", "EQ", "WARD", "m"),
            T("Patient fell going to the bathroom after waiting for a call bell to be answered. We were short a nurse.", "N", "ES", "WARD", "h"),
            T("Call bell response times at night are getting worse, we're one RN down most shifts.", "N", "EQ", "WARD", "m"),
            T("Night shift, no PSW, bells constantly. Patients waiting far too long for basic care.", "N", "EQ", "WARD", "m"),
            T("Families complain to me every shift about how long the call bell takes. Staffing is the reason.", "N", "E", "WARD", "m"),
        ],
        patient_extras=[
            Extra("My {rel} was very distressed.", "", "m"),
            Extra("The nurses were run off their feet.", "E"),
            Extra("I felt ignored.", "L", "m"),
            Extra("This was every night, not once.", "", "m"),
            Extra("Nobody answered the bell.", "", "m"),
            Extra("They clearly need more nurses on nights.", "E", "m"),
        ],
        staff_extras=[Extra("Incident report filed.", "", "m"), Extra("Not enough staff to answer bells.", "E", "m")],
    ),
    Problem(
        id="night_noise",
        description="Noise on the wards at night stops patients sleeping (reported by patients only)",
        count=80,
        staff_share=0.0,
        units=WARDS + ["ICU"],
        patient=[
            T("Impossible to sleep on {ward}. Staff talking loudly at the desk all night.", "N", "E", "WARD", "l"),
            T("The noise at night was terrible, machines beeping and people shouting till 3am.", "N", "E", "WARD", "l"),
            T("Could not get any rest. Doors banging and lights on all night.", "N", "E", "WARD", "l"),
            T("I've had about four hours sleep in three nights because of the noise on the ward.", "N", "E", "WARD", "m"),
            T("noisy noisy noisy. no sleep at all", "N", "E", "WARD", "l"),
            T("The night staff were chatting and laughing outside our room every night. My {rel} is 89 and needs rest.", "N", "E", "WARD", "m"),
            T("Other than the noise at night the stay was fine. But the noise really was bad.", "N", "E", "WARD", "l"),
            T("Cleaners with floor machines at 5am, rounds at 6, never a quiet hour.", "N", "E", "WARD", "l"),
            T("The ward is far too loud at night. Ear plugs should not be needed in a hospital.", "N", "E", "WARD", "l"),
            T("Getting woken again and again by noise in the corridor made my recovery so much harder.", "N", "E", "WARD", "m"),
            T("The man in the next bed had his TV on loud past midnight and no one asked him to turn it down.", "N", "E", "WARD", "l"),
            T("Lack of sleep from the constant racket at night left my {rel} more confused each morning.", "N", "EQ", "WARD", "m"),
            T("Way too loud overnight, couldn't sleep a wink.", "N", "E", "WARD", "l"),
            T("Could quiet hours be enforced after 11pm? It was hard to sleep with the noise.", "U", "E", "WARD", "l"),
            T("Please offer ear plugs and eye masks, nights on the ward are very noisy.", "U", "E", "WARD", "l"),
        ],
        patient_extras=[
            Extra("I asked twice for it to be quieter and nothing changed.", "L"),
            Extra("The day staff were wonderful though."),
            Extra("You need sleep to get better."),
            Extra("The ward was just too noisy to sleep."),
            Extra("Nights were awful for sleep."),
        ],
    ),
    Problem(
        id="handover_gaps",
        description="Key information lost at shift handover and transfers (reported by staff only)",
        count=70,
        staff_share=1.0,
        units=["ICU", "ED"] + WARDS,
        staff=[
            T("Night shift handed over two patients without mentioning their falls risk.", "N", "CS", "WARD", "h"),
            T("Handover from ICU to {ward} missed that the patient had a new penicillin allergy.", "N", "CS", "DIS", "h"),
            T("Verbal handover at 0700 is rushed and half the information is not on the written sheet.", "N", "C", "WARD", "m"),
            T("Received a transfer with no handover at all. Found out about the DNR order from the family.", "N", "CS", "DIS", "h"),
            T("Handover sheets incomplete again. Nobody wrote down that bed 12 is nil by mouth.", "N", "CS", "WARD", "h"),
            T("Day team were not told that a patient had been getting more drowsy overnight.", "N", "CS", "WARD", "h"),
            T("The SBAR handover tool isn't being used on nights, so key information gets lost.", "N", "CI", "WARD", "m"),
            T("Handovers between shifts on {ward} keep leaving out pending bloods and scans.", "N", "C", "WARD", "m"),
            T("Pt arrived from emergency with no report called ahead and nothing in the chart about his insulin.", "N", "CS", "DIS", "h"),
            T("Shift change communication is poor. We spend the first hour chasing information that should have been handed over.", "N", "C", "WARD", "m"),
            T("handover missed that pt had a fall overnight. found out from the pt.", "N", "CS", "WARD", "h"),
            T("Locum was not handed over about a deteriorating patient at the weekend.", "N", "CS", "WARD", "h"),
            T("Nobody mentioned at handover that the family had asked for a meeting with the team.", "N", "C", "WARD", "m"),
            T("Suggest a bedside handover checklist that covers falls risk, allergies and code status.", "U", "C", "WARD", "l"),
            T("Can we protect 15 minutes at shift change so handover isn't done in the corridor?", "U", "CI", "WARD", "l"),
        ],
        staff_extras=[
            Extra("This is the third time this month.", "", "m"),
            Extra("Nobody was harmed this time but it was close.", "S", "h"),
            Extra("Raised it with the charge nurse."),
            Extra("Information keeps getting lost at handover.", "", "m"),
            Extra("Handover needs fixing."),
        ],
    ),
    Problem(
        id="test_results_not_passed_on",
        description="Test and scan results not passed on to patients or the team",
        count=75,
        staff_share=0.27,
        units=["3A", "4A", "4B", "2A", "ED"],
        patient=[
            T("Had a CT scan on Monday and nobody gave me the result before I went home.", "N", "C", "EX", "m"),
            T("We waited three days to hear about the biopsy and had to phone again and again to get anyone to tell us.", "N", "CI", "EX", "m"),
            T("My {rel}'s blood test results were back but the doctor on the ward didn't know about them.", "N", "C", "EX", "m"),
            T("No one explained what the MRI showed. We found out from the family doctor two weeks later.", "N", "C", "EX", "m"),
            T("The scan results got lost between departments and it had to be done again.", "N", "IC", "EX", "m"),
            T("Still waiting for someone to call with my ultrasound results.", "N", "C", "EX", "m"),
            T("They took bloods every morning and never once told me what they showed.", "N", "C", "EX", "l"),
            T("An abnormal x-ray was not followed up for days. Nobody told us until he was much worse.", "N", "CS", "EX", "h"),
            T("Test results seem to disappear. Three different people said they would chase them up.", "N", "CI", "EX", "m"),
            T("results took forever and nobody passed them on", "N", "CI", "EX", "m"),
            T("Could results be shared on the patient portal so we don't have to keep calling?", "U", "C", "EX", "l"),
        ],
        staff=[
            T("Lab results not passed on at handover, found a critical potassium from 6 hours earlier.", "N", "CS", "EX", "h"),
            T("Imaging reports sit unacknowledged in the system because nobody owns the follow up.", "N", "CI", "EX", "m"),
            T("Patients keep asking for their scan results and the team has not reviewed them.", "N", "C", "EX", "m"),
            T("Pathology results for discharged patients go to the ward and nobody reviews them.", "N", "CS", "EX", "h"),
        ],
        patient_extras=[
            Extra("It was a very anxious wait.", "", "m"),
            Extra("The radiology staff themselves were lovely."),
            Extra("Nobody ever told us the results.", "", "m"),
            Extra("We had to chase the results ourselves.", "I", "m"),
        ],
        staff_extras=[Extra("Needs an owner.", "", "m"), Extra("Results are falling through the cracks.", "", "m")],
    ),
    Problem(
        id="iv_pump_shortage",
        description="Not enough working IV infusion pumps, delaying drips and doses (rising in the last 3 weeks)",
        count=75,
        staff_share=0.67,
        units=WARDS + ["ICU"],
        # Steady for 9 weeks, then a sharp rise in weeks 10 to 12.
        weekly=[3, 2, 3, 3, 2, 3, 3, 2, 3, 9, 15, 27],
        patient=[
            T("My {rel}'s IV antibiotics were two hours late because the nurse couldn't find a working pump.", "N", "QE", "WARD", "m"),
            T("The IV pump alarmed all night and it took ages to get someone to swap it for one that worked.", "N", "E", "WARD", "m"),
            T("Waited for a drip to be put up because there were no pumps free on {ward}.", "N", "QE", "WARD", "m"),
            T("A nurse told us the ward had run out of infusion pumps and was borrowing them from another floor.", "N", "E", "WARD", "m"),
            T("My fluids were stopped for hours while they looked for a spare pump.", "N", "QE", "WARD", "m"),
            T("the drip machine kept breaking and they had nothing to replace it with", "N", "E", "WARD", "m"),
        ],
        staff=[
            T("No IV pumps available on {ward} again. Had to borrow from 3A and delay two antibiotic doses.", "N", "QE", "WARD", "m"),
            T("Infusion pump shortage is getting worse. Three patients waiting for pumps at 0800.", "N", "E", "WARD", "m"),
            T("Pump broke mid heparin infusion and there was no spare, infusion was off for 90 minutes.", "N", "ES", "WARD", "h"),
            T("We are hiding pumps in the med room so we have one when we need it. Biomed has a backlog.", "N", "EI", "WARD", "m"),
            T("Several pumps sent to biomed this week and none came back. Running IVs by gravity, which is not safe for some drugs.", "N", "ES", "WARD", "h"),
            T("Pumps alarming 'occlusion' constantly, a faulty batch? Nobody has looked at them.", "N", "EL", "WARD", "m"),
            T("Spent 40 minutes of my shift looking for a working IV pump.", "N", "E", "WARD", "m"),
            T("Missed a dose of IV vancomycin because there was no pump for it.", "N", "ES", "WARD", "h"),
            T("Biomed says replacement pumps are back-ordered. We need a plan until they arrive.", "U", "E", "WARD", "m"),
        ],
        patient_extras=[Extra("The nurse was embarrassed about it."), Extra("There just were not enough pumps.", "E", "m")],
        staff_extras=[
            Extra("This is getting worse every week.", "", "m"),
            Extra("Reported to the manager."),
            Extra("We do not have enough pumps.", "", "m"),
        ],
    ),
]

# Background: praise and one-off comments that belong to no built-in problem. The optional
# units list keeps, say, triage praise in ED.
BG_PATIENT_PRAISE = [
    (T("The nurses on {ward} were wonderful. Thank you.", "P", "", "WARD", "l"), WARDS),
    (T("Everyone was kind and professional from start to finish.", "P", "", "UNC", "l"), None),
    (T("The surgical team explained everything before my operation and I felt safe.", "P", "", "OP", "l"), ["2A", "5A"]),
    (T("Thank you to the emergency team for looking after my {rel} so quickly.", "P", "", "AD", "l"), ["ED"]),
    (T("The food was better than I expected!", "P", "", "WARD", "l"), WARDS),
    (T("Great care, thank you all.", "P", "", "UNC", "l"), None),
    (T("Physio got me walking again after my hip surgery, can't thank them enough.", "P", "", "WARD", "l"), ["5A"]),
    (T("The cleaner on our ward always had a smile and a chat with my {rel}.", "P", "", "WARD", "l"), WARDS),
    (T("Brilliant anaesthetist, calm and reassuring.", "P", "", "OP", "l"), ["2A", "5A"]),
    (T("My scan was booked quickly and the radiographer explained each step.", "P", "", "EX", "l"), None),
    (T("Very happy with the care in ICU. The nurses treated my {rel} with real dignity.", "P", "", "WARD", "l"), ["ICU"]),
    (T("Discharge went smoothly and the nurse went through all my medications with me.", "P", "", "DIS", "l"), WARDS),
    (T("Pharmacy had my take-home meds ready before lunch, which was great.", "P", "", "DIS", "l"), WARDS),
    (T("The triage nurse was lovely and kept us informed the whole time.", "P", "", "AD", "l"), ["ED"]),
    (T("Thank you 5A for looking after me after my knee replacement.", "P", "", "OP", "l"), ["5A"]),
    (T("Staff on the mental health unit listened to me and never made me feel judged.", "P", "", "WARD", "l"), ["6A"]),
    (T("Clean room, friendly staff, quiet nights. Couldn't ask for more.", "P", "", "WARD", "l"), WARDS),
    (T("The doctor took time to explain my results and answer every question.", "P", "", "EX", "l"), None),
    (T("Excellent care. Thank you.", "P", "", "UNC", "l"), None),
    (T("Nurses were attentive and answered the bell quickly.", "P", "", "WARD", "l"), WARDS),
    (T("Grateful to everyone on 3A after my {rel}'s heart attack.", "P", "", "WARD", "l"), ["3A"]),
    (T("Kind, patient and funny staff. Made a scary week a lot easier.", "P", "", "UNC", "l"), None),
    (T("The volunteer who brought tea round was a ray of sunshine.", "P", "", "WARD", "l"), WARDS),
    (T("Surgery went well and the recovery nurses were attentive.", "P", "", "OP", "l"), ["2A", "5A"]),
    (T("I was seen in emergency within an hour, much quicker than I expected.", "P", "", "AD", "l"), ["ED"]),
    (T("From admission to discharge everything was well organised.", "P", "", "UNC", "l"), None),
    (T("The night staff were gentle and quiet when they checked on me.", "P", "", "WARD", "l"), WARDS),
    (T("The chaplain visited and it meant a lot to our family.", "P", "", "WARD", "l"), None),
    (T("Amazing team on 2A. They made sure my pain was under control.", "P", "", "WARD", "l"), ["2A"]),
    (T("Thank you for the care, the best hospital experience I've had.", "P", "", "UNC", "l"), None),
    (T("fantastic nurses!!", "P", "", "WARD", "l"), None),
    (T("The doctors listened to us and involved us in every decision.", "P", "", "UNC", "l"), None),
]

BG_PATIENT_COMPLAINT = [
    (T("Parking cost me more than $40 over three days.", "N", "E", "UNC", "l"), None),
    (T("The food was cold every single meal.", "N", "E", "WARD", "l"), WARDS),
    (T("Lost my glasses on the ward and nobody seemed to care.", "N", "I", "WARD", "l"), WARDS),
    (T("The receptionist was rude to my elderly {rel}.", "N", "R", "AD", "l"), ["ED"]),
    (T("Wifi didn't work the whole week.", "N", "E", "WARD", "l"), None),
    (T("The bathroom had not been cleaned in two days.", "N", "E", "WARD", "l"), WARDS),
    (T("A doctor discussed my diagnosis in front of the whole bay.", "N", "R", "EX", "m"), WARDS),
    (T("The surgeon never came back to explain how the operation went.", "N", "C", "OP", "m"), ["2A", "5A"]),
    (T("My surgery was cancelled the morning of, after fasting since midnight, and nobody apologised.", "N", "IC", "OP", "m"), ["2A", "5A"]),
    (T("I was treated like I was exaggerating my pain.", "N", "L", "WARD", "m"), None),
    (T("The anaesthetist was dismissive when I said I was scared.", "N", "LR", "OP", "m"), ["2A", "5A"]),
    (T("Visiting hours are too short for working families.", "N", "I", "WARD", "l"), None),
    (T("Room was freezing and we couldn't get an extra blanket.", "N", "EQ", "WARD", "l"), WARDS),
    (T("Nobody asked my consent before students examined me.", "N", "R", "EX", "m"), None),
    (T("The vending machines were all broken.", "N", "E", "UNC", "l"), None),
    (T("Billing for the private room was confusing and nobody could explain the charges.", "N", "CI", "UNC", "l"), None),
    (T("Signs around the hospital are terrible, we got lost twice.", "N", "E", "UNC", "l"), None),
    (T("My {rel} wasn't helped with eating and the tray was taken away full.", "N", "Q", "WARD", "m"), WARDS),
    (T("The physiotherapist only came once in five days.", "N", "QI", "WARD", "m"), ["5A", "4A", "4B"]),
    (T("The chairs for family staying overnight are awful.", "N", "E", "WARD", "l"), None),
    (T("A nurse rolled her eyes when I asked a question.", "N", "R", "WARD", "l"), None),
    (T("My dressing wasn't changed for three days and started to smell.", "N", "Q", "WARD", "m"), ["2A", "5A"]),
    (T("We were moved rooms three times in one night.", "N", "I", "WARD", "l"), WARDS),
    (T("The pre-op clinic gave me the wrong fasting instructions.", "N", "CS", "OP", "m"), ["2A", "5A"]),
    (T("Took a week to get a referral to the heart specialist.", "N", "I", "EX", "m"), ["3A"]),
    (T("An interpreter was never booked even though we asked at admission.", "N", "RC", "AD", "m"), None),
    (T("I was left in a gown that didn't close in a busy corridor.", "N", "R", "AD", "m"), ["ED"]),
    (T("The mental health unit felt more like a prison than a place to get better.", "N", "RE", "WARD", "m"), ["6A"]),
    (T("Mould on the ceiling in the shower room.", "N", "E", "WARD", "m"), WARDS),
    (T("My {rel}'s hearing aids went missing during the transfer.", "N", "I", "DIS", "l"), None),
    (T("TV rental is overpriced.", "N", "E", "WARD", "l"), None),
    (T("Nobody told us the ward had a COVID outbreak until we arrived.", "N", "C", "UNC", "m"), None),
    (T("The doctor kept calling me by the wrong name.", "N", "S", "WARD", "m"), None),
    (T("Smoking outside the main entrance is constant and nobody stops it.", "N", "E", "UNC", "l"), None),
    (T("The cafeteria closes at 3pm, there's nothing for families in the evening.", "N", "E", "UNC", "l"), None),
    (T("My {rel} has dementia and was left without glasses or hearing aid for the whole stay.", "N", "Q", "WARD", "m"), WARDS),
    (T("I felt the doctor didn't believe me about my symptoms.", "N", "L", "EX", "m"), None),
    (T("Long wait for a porter to take me down to x-ray.", "N", "I", "EX", "l"), None),
    (T("Blood was taken four times because the first samples were lost.", "N", "IQ", "EX", "m"), None),
    (T("The security guard at the door was aggressive with my teenage son.", "N", "R", "UNC", "m"), ["ED"]),
]

BG_PATIENT_URGENT = [
    (T("My {rel} was given another patient's tablets. The nurse only noticed after they were swallowed.", "N", "S", "WARD", "h"), WARDS),
    (T("I told the nurse three times my {rel} was getting more breathless and nobody came until they were moved to ICU.", "N", "LS", "WARD", "h"), WARDS),
    (T("Found my {rel} on the floor beside the bed, no one knew how long they had been there.", "N", "SQ", "WARD", "h"), WARDS),
    (T("A staff member grabbed my {rel}'s arm roughly and shouted at them.", "N", "RS", "WARD", "h"), None),
    (T("I was given a double dose of my heart medication on the ward.", "N", "S", "WARD", "h"), ["3A", "4A", "4B"]),
    (T("My insulin was missed for a whole day after surgery.", "N", "S", "WARD", "h"), ["2A", "5A"]),
    (T("I was given a meal with nuts even though my allergy was on my wristband.", "N", "S", "WARD", "h"), WARDS),
]

BG_PATIENT_NEUTRAL = [
    (T("Could the ward have a water jug at each bed?", "U", "E", "WARD", "l"), WARDS),
    (T("Is there any way to get a parking pass for long stays?", "U", "E", "UNC", "l"), None),
    (T("It would be nice to have more vegetarian options.", "U", "E", "WARD", "l"), None),
    (T("Are there plans to allow overnight visitors in ICU?", "U", "I", "WARD", "l"), ["ICU"]),
    (T("Please put a clock in each room, it's easy to lose track of time.", "U", "E", "WARD", "l"), None),
    (T("Could visiting rules be put on the website?", "U", "C", "UNC", "l"), None),
    (T("A phone charger at each bed would help.", "U", "E", "WARD", "l"), None),
    (T("Filling this in because the nurse asked. No complaints.", "U", "", "UNC", "l"), None),
]

BG_STAFF_PRAISE = [
    (T("Thanks to pharmacy for turning round the urgent order so fast tonight.", "P", "", "WARD", "l"), None),
    (T("Great teamwork on {ward} during a busy shift today.", "P", "", "UNC", "l"), WARDS),
    (T("The new wound care nurse has made a real difference.", "P", "", "WARD", "l"), ["2A", "5A"]),
    (T("Rapid response team were excellent with our deteriorating patient.", "P", "", "WARD", "l"), WARDS),
    (T("Biomed fixed the cardiac monitor within the hour, thank you.", "P", "", "WARD", "l"), ["ICU", "3A"]),
    (T("Good support from the charge nurse during a hard night.", "P", "", "UNC", "l"), None),
    (T("The safety huddles this week have really helped.", "P", "", "UNC", "l"), None),
    (T("Porters were quick today and transfers went smoothly.", "P", "", "DIS", "l"), None),
]

BG_STAFF_COMPLAINT = [
    (T("Supply room out of size 7 gloves all weekend.", "N", "E", "WARD", "l"), None),
    (T("The computer on wheels in room 6 keeps freezing during the med pass.", "N", "E", "WARD", "m"), WARDS),
    (T("Sharps bin in the treatment room overflowing.", "N", "ES", "WARD", "m"), None),
    (T("Staff locker room is unsafe at night, the lighting is broken.", "N", "E", "UNC", "l"), None),
    (T("Rota released with less than a week's notice again.", "N", "I", "UNC", "l"), None),
    (T("Students arriving on the unit with no orientation.", "N", "I", "WARD", "l"), None),
    (T("Orders written illegibly on paper during the system downtime.", "N", "CS", "WARD", "m"), None),
    (T("Lift to the OR broke and patients had to wait in the hallway.", "N", "E", "OP", "m"), ["2A", "5A"]),
    (T("Theatre list overran and two cases were cancelled at the last minute.", "N", "I", "OP", "m"), ["2A", "5A"]),
    (T("Linen delivery late again, not enough sheets for morning care.", "N", "E", "WARD", "l"), None),
    (T("Patient aggressive towards staff and security took 20 minutes to arrive.", "N", "ES", "WARD", "h"), None),
    (T("Bed alarms not working on half the beds in the falls bay.", "N", "ES", "WARD", "m"), ["4A", "4B"]),
    (T("Lab keeps rejecting samples for label errors since the new printer.", "N", "EI", "EX", "l"), None),
    (T("Staff parking is full by 7am.", "N", "E", "UNC", "l"), None),
    (T("Break room fridge broken for a week.", "N", "E", "UNC", "l"), None),
    (T("Glucose meter reading way off compared with lab values, taken out of use.", "N", "ES", "EX", "m"), None),
    (T("Consultant shouted at a junior nurse in front of patients.", "N", "R", "WARD", "m"), None),
]

BG_STAFF_URGENT = [
    (T("Wrong patient label on a blood sample nearly led to a transfusion error.", "N", "S", "EX", "h"), None),
    (T("Patient on {ward} given ten times the prescribed morphine because of a decimal error.", "N", "S", "WARD", "h"), WARDS),
    (T("Deteriorating patient's early warning score was not escalated overnight.", "N", "S", "WARD", "h"), WARDS),
]

BG_STAFF_NEUTRAL = [
    (T("Can we get more training on the new bed booking system?", "U", "I", "UNC", "l"), None),
    (T("Request for a second dressing trolley on {ward}.", "U", "E", "WARD", "l"), WARDS),
    (T("Suggest moving the hand gel dispensers closer to the bed spaces.", "U", "E", "WARD", "l"), None),
]

# Background mix at the default size: 400 patient and 100 staff comments.
BACKGROUND = [
    ("patient_family", BG_PATIENT_PRAISE, 190),
    ("patient_family", BG_PATIENT_COMPLAINT, 150),
    ("patient_family", BG_PATIENT_NEUTRAL, 40),
    ("patient_family", BG_PATIENT_URGENT, 20),
    ("staff", BG_STAFF_PRAISE, 25),
    ("staff", BG_STAFF_COMPLAINT, 55),
    ("staff", BG_STAFF_NEUTRAL, 10),
    ("staff", BG_STAFF_URGENT, 10),
]

PRAISE_OPENERS = [
    "The care on the ward was excellent.",
    "The nurses were lovely.",
    "The surgery itself went really well.",
    "Staff were kind throughout.",
    "Doctors were great.",
    "Overall a good stay.",
]
PATIENT_CLOSERS = ["Please sort this out.", "Not acceptable.", "Very frustrating.", "This needs to change.", "Otherwise fine.", "Thank you."]
STAFF_CLOSERS = ["Please escalate.", "Raising this again.", "Needs a fix."]
CSV_SOURCE = {"patient_family": (["patient", "family", "patient_family"], [5, 4, 1]), "staff": (["nurse", "staff", "physician"], [5, 3, 2])}


def scaled(count: int, n: int) -> int:
    return max(1, round(count * n / DEFAULT_N))


def _ward(unit: str, rng: random.Random) -> str:
    if unit == "ED":
        return rng.choice(["emergency", "the ED", "the ER"])
    if unit == "ICU":
        return "ICU"
    return rng.choice([unit, f"ward {unit}", unit, "the ward"])


def _fill(text: str, unit: str, rng: random.Random) -> str:
    fillers = {
        "{rel}": lambda: rng.choice(REL),
        "{hours}": lambda: rng.choice(HOURS),
        "{late}": lambda: rng.choice(LATE),
        "{mins}": lambda: rng.choice(MINS),
        "{n}": lambda: str(rng.randint(6, 15)),
        "{ward}": lambda: _ward(unit, rng),
    }
    starts_with_blank = text.startswith("{")
    for key, make in fillers.items():
        while key in text:
            text = text.replace(key, make(), 1)
    return text[0].upper() + text[1:] if starts_with_blank else text


_WORD = re.compile(r"[A-Za-z]{5,}")


def _typo(text: str, rng: random.Random) -> str:
    words = list(_WORD.finditer(text))
    if not words:
        return text
    m = rng.choice(words)
    w = m.group()
    i = rng.randrange(1, len(w) - 2)
    kind = rng.randrange(3)
    if kind == 0:
        w = w[:i] + w[i + 1] + w[i] + w[i + 2 :]  # swap two letters
    elif kind == 1:
        w = w[:i] + w[i + 1 :]  # drop one
    else:
        w = w[:i] + w[i] + w[i:]  # double one
    return text[: m.start()] + w + text[m.end() :]


def roughen(text: str, rng: random.Random) -> str:
    """Typos and casual writing. Labels do not change."""
    if rng.random() < 0.18:
        for _ in range(rng.randint(1, 2)):
            text = _typo(text, rng)
    if rng.random() < 0.12:
        text = text.replace("n't", "nt").replace("'s ", "s ")
    if rng.random() < 0.08:
        text = text.lower()
    if rng.random() < 0.10:
        text = text.rstrip(".!")
    return text


def _labels(base: T, extras: list[Extra]) -> dict:
    cats = set(base.cats) | {c for e in extras for c in e.cats}
    urgency = max([URGENCY[base.urgency]] + [URGENCY[e.urgency] for e in extras], key=URGENCY_ORDER.index)
    return {
        "sentiment": SENTIMENT[base.sentiment],
        "categories": sorted(CATEGORY[c] for c in cats),
        "stage": STAGE[base.stage],
        "urgency": urgency,
    }


def _problem_comment(problem: Problem, source: str, unit: str, rng: random.Random) -> tuple[str, dict]:
    templates = problem.staff if source == "staff" else problem.patient
    pool = problem.staff_extras if source == "staff" else problem.patient_extras
    base = rng.choice(templates)
    extras: list[Extra] = []
    second: T | None = None
    if base.sentiment == "N":
        # Longer comments often cover two sides of the same problem.
        complaints = [t for t in templates if t.sentiment == "N" and t is not base]
        if complaints and rng.random() < 0.3:
            second = rng.choice(complaints)
        if pool:
            k = rng.choices([0, 1, 2], weights=[35, 45, 20])[0]
            extras = rng.sample(pool, min(k, len(pool)))
    parts = []
    if source != "staff" and base.sentiment == "N" and rng.random() < 0.15:
        parts.append(rng.choice(PRAISE_OPENERS))  # praise mixed in; the complaint still has more words
    parts.append(base.text)
    if second:
        parts.append(second.text)
        extras.append(Extra("", second.cats, second.urgency))
    parts += [e.text for e in extras if e.text]
    if base.sentiment == "N" and rng.random() < 0.15:
        parts.append(rng.choice(STAFF_CLOSERS if source == "staff" else PATIENT_CLOSERS))
    text = _fill(_join(parts), unit, rng)
    return roughen(text, rng), _labels(base, extras)


def _join(parts: list[str]) -> str:
    out = parts[0]
    for part in parts[1:]:
        out += (" " if out[-1] in ".!?" else ". ") + part
    return out


def _background_comment(entries, rng: random.Random) -> tuple[str, str, dict]:
    base, units = rng.choice(entries)
    unit = rng.choice(units or ALL_UNITS)
    text = base.text
    if base.sentiment == "P" and rng.random() < 0.25:
        other, _ = rng.choice(entries)
        if other.text != text and "{ward}" not in other.text:
            text = _join([text, other.text])
    return roughen(_fill(text, unit, rng), rng), unit, _labels(base, [])


def _spread(total: int, weights: list[int]) -> list[int]:
    """Weekly counts in proportion to `weights` that add up to `total`."""
    raw = [total * w / sum(weights) for w in weights]
    counts = [int(x) for x in raw]
    for i in sorted(range(len(raw)), key=lambda i: raw[i] - counts[i], reverse=True)[: total - sum(counts)]:
        counts[i] += 1
    return counts


def generate(seed: int = DEFAULT_SEED, n: int = DEFAULT_N) -> list[dict]:
    """All comments, sorted by date, with ids 1..len. Same seed and n, same list."""
    rng = random.Random(seed)
    rows: list[dict] = []

    for problem in PROBLEMS:
        count = scaled(problem.count, n)
        # Steady problems get the same number of comments each week (give or take one), so
        # the rising problem is the only one that rises in the data itself.
        weekly = _spread(count, problem.weekly or [1] * (DAYS // 7))
        days = [w * 7 + rng.randrange(7) for w, k in enumerate(weekly) for _ in range(k)]
        if problem.weekly:
            days[-1] = DAYS - 1  # one on the last day, so week 12 is the rising window
        n_staff = round(count * problem.staff_share)
        sources = ["staff"] * n_staff + ["patient_family"] * (count - n_staff)
        rng.shuffle(sources)
        for day, source in zip(days, sources):
            unit = rng.choice(problem.units)
            text, labels = _problem_comment(problem, source, unit, rng)
            rows.append({"text": text, "source": source, "unit": unit, "day": day, **labels, "planted": problem.id})

    planted_total = len(rows)
    background_total = max(0, n - planted_total)
    plan = _spread(background_total, [k for _, _, k in BACKGROUND])
    for (source, entries, _), k in zip(BACKGROUND, plan):
        for _ in range(k):
            text, unit, labels = _background_comment(entries, rng)
            rows.append({"text": text, "source": source, "unit": unit, "day": rng.randrange(DAYS), **labels, "planted": None})

    order = sorted(range(len(rows)), key=lambda i: (rows[i]["day"], i))
    out = []
    for new_id, i in enumerate(order, start=1):
        row = rows[i]
        names, weights = CSV_SOURCE[row["source"]]
        out.append(
            {
                "id": new_id,
                "text": row["text"],
                "source": row["source"],
                "csv_source": rng.choices(names, weights)[0],
                "unit": row["unit"],
                "date": (START + timedelta(days=row["day"])).isoformat(),
                "sentiment": row["sentiment"],
                "categories": row["categories"],
                "stage": row["stage"],
                "urgency": row["urgency"],
                "planted": row["planted"],
            }
        )
    return out


def split(rows: list[dict], test_size: int = DEFAULT_TEST_SIZE, seed: int = DEFAULT_SEED) -> tuple[list[dict], list[dict]]:
    """(train, test). Random but fixed by the seed; both keep the original order."""
    ids = [r["id"] for r in rows]
    random.Random(f"{seed}-split").shuffle(ids)
    test_ids = set(ids[: min(test_size, len(ids))])
    return [r for r in rows if r["id"] not in test_ids], [r for r in rows if r["id"] in test_ids]


def problems_summary(rows: list[dict]) -> list[dict]:
    out = []
    for p in PROBLEMS:
        mine = [r for r in rows if r["planted"] == p.id]
        out.append(
            {
                "id": p.id,
                "description": p.description,
                "reporters": p.reporters,
                "rising": p.weekly is not None,
                "comments": len(mine),
                "patient_family": sum(r["source"] == "patient_family" for r in mine),
                "staff": sum(r["source"] == "staff" for r in mine),
            }
        )
    return out


JSONL_FIELDS = ("id", "text", "source", "unit", "date", "sentiment", "categories", "stage", "urgency", "planted")


def to_csv(rows: list[dict]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["text", "source", "unit", "date"])
    for r in rows:
        writer.writerow([r["text"], r["csv_source"], r["unit"], r["date"]])
    return out.getvalue()


def to_jsonl(rows: list[dict]) -> str:
    return "".join(json.dumps({k: r[k] for k in JSONL_FIELDS}, ensure_ascii=False) + "\n" for r in rows)


def write(out_dir: Path, seed: int = DEFAULT_SEED, n: int = DEFAULT_N, test_size: int = DEFAULT_TEST_SIZE) -> dict[str, Path]:
    rows = generate(seed, n)
    train, test = split(rows, test_size, seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "csv": (out_dir / "synthetic.csv", to_csv(rows)),
        "all": (out_dir / "synthetic.jsonl", to_jsonl(rows)),
        "train": (out_dir / "synthetic_train.jsonl", to_jsonl(train)),
        "test": (out_dir / "synthetic_test.jsonl", to_jsonl(test)),
        "problems": (
            out_dir / "synthetic_problems.json",
            json.dumps({"seed": seed, "n": len(rows), "test_size": len(test), "problems": problems_summary(rows)}, indent=2) + "\n",
        ),
    }
    for path, content in files.values():
        path.write_bytes(content.encode("utf-8"))  # bytes, so Windows does not add \r
    return {name: path for name, (path, _) in files.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--n", type=int, default=DEFAULT_N, help="about how many comments")
    parser.add_argument("--test-size", type=int, default=DEFAULT_TEST_SIZE)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    paths = write(args.out, args.seed, args.n, args.test_size)
    for path in paths.values():
        print(f"wrote {path} ({path.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
