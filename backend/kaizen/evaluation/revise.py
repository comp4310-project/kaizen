"""Version-two wording corrections from the seeded 100-row AI audit.

Revision changes only text. Source, dates, planted patterns and evaluation split stay
unchanged. This is an AI quality review, never human annotation.
"""
from __future__ import annotations

import random

from kaizen.evaluation.scenarios import BACKGROUND, BACKGROUND_DETAILS, DETAILS, PATIENT, STAFF

# One family-perspective alternative for each original patient narrative seed.
FAMILY = {
"discharge_medication": """
Dad was dressed and ready, but his take-home tablets weren't.
I had to leave and come back because mum's discharge medicine hadn't arrived.
They said my partner could leave, then we learned the medication bag wasn't ready.
My sister's discharge was done on paper before lunch. We were still waiting for her prescriptions at tea time.
I arranged a lift for my brother only to find his take-home medication hadn't been ordered.
Mum's nurse checked several times for the tablets. She couldn't make them arrive any faster.
The hospital pharmacy backlog kept us there long after dad was ready to come home.
I assumed signing my partner's prescription meant it was ready to collect. We had another long wait.
We reached the exit before anyone realised my sister's medicines were still being prepared.
A small bag of pills was the only thing keeping my brother in hospital.
""",
"night_noise": """
Dad couldn't sleep with the bin lids banging outside his bay.
Every time mum nodded off a squeaky trolley woke her again.
I stayed with my partner and could hear corridor chatter long after lights out.
The television across from my sister stayed on all night.
My brother kept waking up to doors being slammed.
The alarm on an empty bed kept sounding while mum was trying to sleep.
Dad told me the floor cleaning machine had kept him awake in the night.
A visitor beside my partner was using speakerphone after midnight.
From the chair beside my sister's bed I could hear the desk conversations all night.
My brother said he'd barely slept between the carts rattling past and the radio outside.
""",
"ed_wait": """
We sat in emergency for hours, wondering if dad was still on the list.
Mum went through triage quickly, then we heard nothing about the wait.
I watched the ED board with my partner, but it didn't change and the desk had no news.
We understand urgent cases go first. I just wanted someone to explain my sister's long wait.
They moved my brother to another emergency waiting area and then seemed to forget us.
After waiting with dad for hours in ED, I asked what was next and got told to sit down.
A check-in during mum's emergency wait would have helped us both.
My partner had no idea when the assessment would happen, and neither did I.
The ED room was filling up around us without anyone explaining the delay to my sister.
I kept checking whether they'd called my brother's name. Nobody could explain the long wait.
""",
"call_bell": """
Mum rang for help to the toilet and was still waiting when I came back.
Dad's water was out of reach and his call light stayed on.
I could see my partner's bell light, but no one came to the bed.
By the time someone answered, my sister was very uncomfortable.
My brother asked to be moved up the bed. Two rings and a long wait.
Mum's bell worked; getting a response was the problem.
Dad waited so long for help with the commode that he couldn't wait any more.
My partner rang because the walking frame was too far away. Nobody came for ages.
They asked my sister to ring before standing, but then left her waiting.
It seemed everyone thought somebody else was answering my brother's buzzer.
""",
"handover": """
The evening nurse hadn't heard the plan we agreed for dad that morning.
Mum and I repeated the same request after every shift change.
One shift said my partner could get up with help, but the next hadn't been told.
The new nurse didn't know my sister was waiting for a review.
My brother's overnight plan got lost between the two teams.
Everyone was kind to mum, but at changeover nobody knew what had been done.
I heard different plans for dad from the outgoing and incoming shifts.
The nurse taking over hadn't heard about the concern I'd already raised for my partner.
Each new shift asked us the same questions about my sister's ward plan.
After handover I had to explain again why the team was coming back to my brother.
""",
"discharge_instructions": """
Dad's sheet said book a follow-up but didn't say who with.
Mum is home and we still don't know which number to call about her dressing.
They explained my partner's home care as we were packing. Neither of us took it all in.
My sister's printed instructions used words neither of us understood.
My brother came away with two sheets giving different advice about when to return.
Please write mum's next steps down, not just tell us while we're leaving.
Nobody clearly explained what to watch for when dad got home.
The leaflet my partner received didn't answer our follow-up questions.
I know there was something to arrange for my sister, but the paperwork doesn't say what.
We left with my brother's stack of papers and no clear plan for the following week.
""",
"cleanliness_equipment": """
Mum's bedside table was sticky when we arrived.
There were crumbs on dad's chair and the floor around it hadn't been wiped.
The bathroom bin near my partner's room was overflowing.
The frame brought for my sister had a loose rubber foot.
The stain on my brother's curtain was still there when he left.
A wheel on mum's bedside cabinet was broken.
The shared toilet dad was using needed cleaning again.
The cracked arm of the chair beside my partner caught my sleeve.
My sister couldn't use the shower properly because the drain backed up.
Staff had to find another blood pressure machine after the one at my brother's bed kept failing.
""",
"transport": """
Dad was ready to move wards but the porter never came.
Mum sat waiting for a wheelchair escort long after her transfer was agreed.
My partner missed the scan slot because nobody came to take them down.
A bed was ready for my sister but transport kept being postponed.
My brother was packed to leave the unit, still waiting for a porter.
Mum's nurse couldn't leave the ward to take her, and the transport request stayed pending.
Waiting for an escort added hours to dad's ward transfer.
They said a wheelchair was coming for my partner's move. It arrived much later.
The other ward expected my sister, but nobody had picked up the porter booking.
My brother spent longer waiting to move between departments than being seen.
""",
}

FAMILY_BACKGROUND = {
0: "The nurse sat down and listened to mum instead of talking from the doorway.",
1: "Someone noticed dad was cold and brought him another blanket.",
2: "They explained the theatre checks to my partner and included me in the conversation.",
3: "Mum said the scan staff talked her through each part.",
4: "Reception showed us where to take my brother.",
5: "Bringing my sister home was well organised and we knew the next steps.",
6: "The physio helped dad feel more confident walking.",
7: "Thank you to the volunteer who walked with mum and me.",
8: "Remembering how my partner takes their tea was a nice touch.",
9: "Dad said the recovery team were calm and explained their checks.",
10: "Is there a map of the accessible entrance? I'll be bringing mum.",
11: "Could visitors get drinking water closer to the ward?",
12: "I brought my sister through the side entrance and we checked in at reception.",
13: "My brother had his test in another department and came back afterwards.",
14: "My partner went through the consent form with the team before the procedure.",
15: "Mum left with the papers and a number for follow-up.",
16: "Dad's meal was already cold when it reached him.",
17: "Finding somewhere to park while visiting my sister took longer than expected.",
18: "My brother's personal care was discussed while his curtain was still open.",
19: "I tried to explain mum's worry about the test, but someone talked over me.",
20: "My partner couldn't get a dry pillow to replace the damp one for a while.",
21: "We had to enter dad's registration details twice.",
38: "My sister nearly fell on a wet floor that had no warning sign.",
39: "The dose on mum's take-home list was wrong. It was corrected before she used it.",
}

STAFF_UNSUITABLE = {
"The wait felt much longer from the bed.": "The waiting patient had no indication that the request was being handled.",
"I didn't want to keep bothering people.": "Patients shouldn't have to ring repeatedly for the same request.",
"I could see everyone was busy.": "We were busy, but still need to acknowledge the request.",
"I'd rather get an honest estimate at the start.": "We need a realistic estimate before arranging pickup.",
"A phone number on the sheet would help.": "Putting the contact number on the sheet would reduce calls back to the ward.",
"The staff seemed pressed for time.": "Teaching time needs to be protected.",
"We shouldn't need to guess the next step.": "Patients shouldn't have to guess the next step.",
"The explanation was too fast.": "We need time to explain it at a manageable pace.",
"I felt looked after.": "I felt supported by the team.",
}
NEUTRAL_UNSUITABLE = {
"I'm not sure who to ask.": "That was the arrangement on this shift.",
"Maybe this is already planned.": "This is how it was organised on the day.",
"Just a thought.": "No particular problem to report.",
"It would be useful to know.": "Nothing else to report about that part.",
"I'm recording it here so I don't forget.": "That's all I wanted to record.",
}


def revise(rows, truth, seed=4310):
    """Return revised copies, preserving the original row order and every truth field."""
    from kaizen.evaluation.generate import render

    revised, seen = [], set()
    for row, meta in zip(rows, truth):
        row = dict(row)
        text = row["text"]
        rng = random.Random(seed + meta["row_id"])
        issue = meta["planted"]
        index = int(meta["scenario"].rsplit("/", 1)[1])
        group = meta["source_group"]
        if row["source"] == "family":
            base = FAMILY[issue].strip().splitlines()[index] if issue else FAMILY_BACKGROUND[index]
            details = list(DETAILS[issue] if issue else BACKGROUND_DETAILS[meta["sentiment"]])
            details = [d.replace("I was already tired when I arrived.", "We were both tired by then.")
                       .replace("I was awake again before dawn.", "They were awake again before dawn.")
                       .replace("I felt looked after.", "We felt supported.")
                       .replace("The wait felt much longer from the bed.", "The wait was hard on them.")
                       .replace("Please leave time for questions at the end of report.", "Please give us a chance to check the plan when the team changes.")
                       for d in details]
            text = render(base, details, rng)
        else:
            base = (STAFF if group == "staff" else PATIENT)[issue].strip().splitlines()[index] if issue else BACKGROUND[index].split("|", 3)[3]
            details = DETAILS[issue] if issue else BACKGROUND_DETAILS[meta["sentiment"]]

        def clean(value):
            if group == "staff":
                for old, new in STAFF_UNSUITABLE.items():
                    value = value.replace(old.rstrip("."), new.rstrip("."))
            if meta["sentiment"] == "neutral" and "?" not in base:
                for old, new in NEUTRAL_UNSUITABLE.items():
                    value = value.replace(old.rstrip("."), new.rstrip("."))
            value = value.replace("That's all I wanted to record. Nothing else to report about that part.",
                                  "That's all I wanted to record.")
            value = value.replace("Nothing else to report about that part. That's all I wanted to record.",
                                  "Nothing else to report about that part.")
            if issue == "cleanliness_equipment":
                value = value.replace("Finding a replacement took extra time", "It took extra time to sort out")
            if row["source"] == "family":
                value = value.replace("It happened on the previous shift as well", "This wasn't the first delay")
            # More common local wording, without changing the described process.
            return value.replace("TTOs outstanding", "Take-home meds outstanding")

        text = clean(text)
        for _ in range(5000):
            if text not in seen:
                break
            text = clean(render(base, details, rng))
        else:
            raise ValueError("revision exhausted unique wording")
        row["text"] = text
        seen.add(text)
        revised.append(row)
    return revised
