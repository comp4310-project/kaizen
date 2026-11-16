"""AI-authored fictional situations, not collected feedback.

Each line is a distinct narrative seed. The final three in each bank are held out
from baseline training, including every wording variant derived from them.
"""

# issue, patient/family count, staff count, stage, categories
ISSUES = [
    ("discharge_medication", 130, 90, "discharge_and_transfers", ["institutional_processes"]),
    ("night_noise", 180, 0, "care_on_the_ward", ["environment"]),
    ("ed_wait", 130, 70, "admissions", ["institutional_processes", "communication"]),
    ("call_bell", 120, 60, "care_on_the_ward", ["quality"]),
    ("handover", 70, 110, "care_on_the_ward", ["communication"]),
    ("discharge_instructions", 120, 60, "discharge_and_transfers", ["communication"]),
    ("cleanliness_equipment", 100, 80, "care_on_the_ward", ["environment"]),
    ("transport", 100, 80, "discharge_and_transfers", ["institutional_processes"]),
]

PATIENT = {
"discharge_medication": """
Packed and dressed, then spent the afternoon waiting for the tablets to take home.
My lift had to leave before pharmacy sent up my discharge medicine.
Everyone said I could go home except the medication bag wasn't ready.
Discharged before lunch on paper. Still in the chair waiting for prescriptions at tea time.
Why tell me to arrange a pickup when the take-home medicines haven't even been ordered?
The nurse kept checking for my pills but there was nothing she could give me.
Going home took longer than the appointment because the hospital pharmacy had a backlog.
I thought the discharge prescription would be ready when the doctor signed it. Apparently there's another queue.
We got all the way to the exit and had to come back because the medicines were still upstairs being prepared.
The only thing keeping me in the hospital was a small bag of medication.
""",
"night_noise": """
Sleep was impossible with the bin lids banging outside the bay.
The trolley wheels squeaked past my bed every time I drifted off.
People were chatting in the corridor well after lights out.
The television opposite was on all night. Nobody seemed to notice.
Doors slamming at night, again and again.
I understand alarms matter but the ones at the empty bed kept sounding overnight.
There was a loud floor cleaning machine outside the room in the middle of the night.
A visitor was taking calls on speaker after midnight while the rest of us tried to sleep.
I could hear every conversation at the desk through the night.
Between the rattling carts and the corridor radio, I barely slept.
""",
"ed_wait": """
Sat in emergency for hours without knowing whether I was still on the list.
Triage was quick, then nothing. Nobody could tell me what we were waiting for.
The ED board didn't change and the desk had no update about my wait.
I don't mind urgent cases going first but please explain why the queue has stopped.
We were sent to another waiting area in emergency and seemed to disappear from everyone's radar.
After a long ED wait I asked what happened next and was told to sit back down.
Waiting in emergency would be less stressful if someone checked in occasionally.
There was no sign of when I'd be assessed and no explanation for the delay.
The emergency waiting room filled up, but nobody came out to tell us what was happening.
I kept wondering whether I'd missed my name being called. Hours went by with no information.
""",
"call_bell": """
Pressed the bell for help getting to the toilet and waited far too long.
My water was out of reach and the call light stayed on for ages.
I could see the bell light but nobody came to the bed.
Eventually someone answered the buzzer, by then I was really uncomfortable.
Needed help moving up the bed. Rang twice, still waited.
The call bell was working, it was getting anyone to answer that was the problem.
I waited for help with the commode until I couldn't wait any longer.
The buzzer rang and rang while I needed someone to bring the walking frame closer.
I was told to ring before standing, but getting a response took so long.
It felt like everyone assumed someone else was answering my call light.
""",
"handover": """
The evening nurse didn't know about the plan we'd agreed with the morning team.
Had to repeat the same request after every shift change.
One shift said I could get up with help; the next didn't seem to have that information.
The new nurse was surprised I was waiting for a review. It hadn't been passed on.
The overnight plan disappeared somewhere between one team leaving and the next arriving.
Staff were kind, but at changeover nobody seemed sure what had already been done.
I heard two different plans from the outgoing and incoming staff.
The nurse taking over had no idea I'd already raised this earlier.
Every new shift started from scratch with the same questions about the ward plan.
After handover I had to explain again why the team was meant to come back.
""",
"discharge_instructions": """
The sheet said book a follow-up but didn't say with whom.
Home now and still unsure which number to call about the dressing.
They explained everything as I was leaving and I couldn't take it all in.
The printed instructions used words I don't understand.
I was given two sheets with different advice about when to come back.
Please write down the next steps instead of saying them while we're packing.
There wasn't a clear explanation of what to watch for once I got home.
The discharge leaflet looked generic and didn't answer my questions about follow-up.
I know I was supposed to arrange something after leaving, but the paperwork doesn't say what.
We went through the exit with a stack of papers and no clear plan for the next week.
""",
"cleanliness_equipment": """
The bedside table was sticky when I arrived.
There were crumbs in the chair and the floor beside it hadn't been wiped.
The bathroom bin was overflowing by the afternoon.
The walking frame they brought had a loose rubber foot.
The curtain had a visible stain that was still there when I left.
A broken wheel on the bedside cabinet made it hard to move.
The shared toilet needed cleaning again and nobody seemed to own that job.
The chair arm was cracked and caught my sleeve.
The shower drain backed up and left the floor unpleasant to use.
The blood pressure machine kept failing and staff had to find another one.
""",
"transport": """
Ready to move wards but no porter arrived.
The transfer was agreed in the morning and I sat waiting for a wheelchair escort.
My scan slot was missed because nobody came to take me down.
A bed was ready on the other ward but transport kept getting pushed back.
All packed to leave the unit, then another long wait for a porter.
The nurse couldn't leave the ward to take me, and the transport request was still pending.
Waiting for the hospital escort added hours to the transfer.
We were told a wheelchair would be brought for the move. It never appeared until much later.
The receiving ward was expecting me but the porter booking hadn't reached anyone.
I spent more time waiting to be taken between departments than being seen.
""",
}

STAFF = {
"discharge_medication": """
Discharge scripts are reaching pharmacy after the ward round and coming back too late for pickup.
I'm chasing take-home meds while the next admission is waiting for the bed.
The discharge order is signed but the pharmacy queue is holding up the actual departure.
We keep promising a discharge time without checking if the medication pack is ready.
TTOs outstanding at the end of the shift again.
The prescription was ready for checking, but nobody was available to release the bag.
Families are waiting at the desk for discharge medicines I still haven't received.
A late change to the discharge prescription put the whole pack back in the pharmacy queue.
We lost the planned discharge window while the take-home supply was being assembled.
Medical clearance is being treated as a departure time even when dispensing hasn't started.
""",
"ed_wait": """
ED patients keep asking for a wait estimate and we have no reliable update to give them.
The waiting room is backing up without anyone assigned to explain the delay.
Triage is complete but patients hear nothing during the long gap before assessment.
We need a way to tell the ED queue why movement has stopped.
Several people thought they'd been forgotten because the assessment wait wasn't explained.
I'm answering the same waiting-time question between every emergency assessment.
The desk and clinical team are giving different messages about the ED delay.
People are leaving the emergency waiting room without knowing how close they are to being seen.
A long wait becomes a complaint when we never circle back with an update.
There is no owner for waiting-room communication when ED gets busy.
""",
"call_bell": """
Call lights are staying on while we're tied up assisting other patients.
The bell board doesn't show which requests somebody has already picked up.
We need coverage for call bells when two of us are helping with a transfer.
I found three unanswered call lights on coming back from a break.
Basic comfort requests sit in the bell queue longer than they should.
There isn't an agreed backup when the allocated nurse can't answer the buzzer.
A patient was still waiting for toileting help after ringing during the medication round.
Bells in the far bay are easy to miss when we're working at the other end.
The patient had used the call system correctly but waited too long for assistance.
We are responding to buzzers in whatever order someone happens to notice them.
""",
"handover": """
Pending reviews aren't consistently included in shift report.
The handover list had yesterday's plan and no mention of the change.
I spent the first part of the shift reconstructing what the outgoing team had done.
We are handing over bed numbers instead of the unresolved jobs.
The verbal report and written handover don't match.
An interruption halfway through report meant the last bay's plan wasn't passed on.
The night team didn't receive the update from the late ward round.
Tasks marked for follow-up get lost between the day and evening teams.
I couldn't tell which jobs had been completed and which still needed action after report.
Covering staff are receiving a handover without the reasons behind the plan.
""",
"discharge_instructions": """
The discharge sheet doesn't identify who is arranging the follow-up.
Patients are phoning the ward because the home-care instructions aren't clear.
We need a plain-language version of the discharge advice.
The printed leaflet and verbal instructions give different review intervals.
There's no space on the discharge form for the patient to write their questions.
Teaching gets squeezed into the last few minutes before the ride arrives.
The person leaving couldn't explain the next steps back to me.
Follow-up advice is buried in a long discharge summary that families struggle to read.
We keep handing out instructions without checking whether the patient understands them.
The discharge paperwork names a service but gives no way to contact it.
""",
"cleanliness_equipment": """
The shared commode was returned without a clear clean-status label.
A monitor lead keeps disconnecting and the spare trolley is empty.
Broken chair still in the bay despite being reported.
We are searching other rooms for a working BP cuff.
The equipment cleaning checklist has gaps between shifts.
The washroom needed attention but the cleaning request wasn't picked up.
A wheelchair brake wouldn't hold during the equipment check.
The storage area mixes clean equipment with items waiting to be wiped.
The bedside cabinet won't lock its wheels and needs taking out of use.
Another thermometer is missing its working probe, so observations take longer.
""",
"transport": """
Porter requests for ward transfers are sitting unallocated.
The receiving unit has a bed but we can't get an escort for the move.
Transport didn't arrive in time for the booked imaging slot.
We're phoning around to find out who owns an overdue transfer request.
The porter booking system shows pending long after the requested time.
A routine ward move needed repeated calls to transport.
The queue for patient escorts is getting longer on each shift.
We had everything ready for transfer and then lost the slot waiting for a wheelchair porter.
There is no confirmation that the transport team has accepted the request.
Delayed internal transport is holding up the next step even when both clinical teams are ready.
""",
}

# Follow-on details belong to the same process, not random unrelated filler.
DETAILS = {
"discharge_medication": [
"The ride had already been arranged.", "It made planning the afternoon difficult.",
"A clearer expected time would help.", "The bag arrived just as the next shift started.",
"Nothing else was holding up leaving.", "This was the last step, which made it more frustrating.",
"Everyone was polite about it.", "We only found out about the delay after asking.",
"The wait was nearly two hours.", "The actual handover of the medicines took minutes.",
"The driver ended up making a second trip.", "I'd rather get an honest estimate at the start.",
],
"night_noise": [
"Earplugs only helped a little.", "The room itself was comfortable.",
"It was quieter during the day, oddly.", "I was awake again before dawn.",
"Please keep the corridor voices down.", "I don't expect silence, just a chance to rest.",
"The noise stopped just before breakfast.", "Pulling the curtain made no difference.",
"One quiet stretch would have helped.", "I was already tired when I arrived.",
"It carried through the closed door.", "The care was good; the sleep wasn't.",
],
"ed_wait": [
"A short update would have made a difference.", "I know emergencies can't run to a timetable.",
"The desk was busy too.", "We shouldn't have to keep asking.",
"Nobody was asking to jump the queue.", "The uncertainty was worse than the waiting.",
"The explanation finally came after several requests.", "There wasn't even a rough estimate.",
"Once seen, things moved quickly.", "It's hard to plan anything around that.",
"The waiting area had nowhere comfortable left to sit.", "A simple check-in would help.",
],
"call_bell": [
"I could see everyone was busy.", "It happened more than once.",
"Once help arrived it was fine.", "It shouldn't take a second ring to be noticed.",
"The light stayed on the whole time.", "An acknowledgement would have helped.",
"It was a basic request, not something complicated.", "The wait felt much longer from the bed.",
"Nobody explained the delay.", "Please check whether someone has actually answered.",
"I didn't want to keep bothering people.", "There needs to be a backup person.",
],
"handover": [
"It meant going through everything again.", "A short written update would have helped.",
"The staff taking over did their best.", "This keeps happening at changeover.",
"Nobody seemed sure which version was current.", "The information was already available earlier.",
"It wasn't a new request.", "A checklist might catch this.",
"The gap was only noticed after someone asked.", "Both shifts were busy.",
"Please leave time for questions at the end of report.", "The confusion lasted into the next round.",
],
"discharge_instructions": [
"A phone number on the sheet would help.", "There's a lot to remember at that point.",
"The explanation was too fast.", "Please use everyday words.",
"A chance to ask questions would have helped.", "The staff seemed pressed for time.",
"It only became confusing after leaving.", "We shouldn't need to guess the next step.",
"The small print didn't help.", "The leaflet was several pages long.",
"It would help to highlight the bits that apply.", "A quick check of understanding might catch this.",
],
"cleanliness_equipment": [
"It was reported at the desk.", "A small fix, but it matters.",
"The rest of the area looked fine.", "It was still there later.",
"Please check it before the next person uses it.", "Finding a replacement took extra time.",
"This shouldn't need several reminders.", "Someone eventually sorted it out.",
"The problem was easy to see.", "It wasn't clear who to tell.",
"The same item had been mentioned before.", "Routine checks might pick it up sooner.",
],
"transport": [
"The receiving team had already been told to expect the move.", "The request had been put in early.",
"This is happening more often lately.", "Nobody could give a pickup time.",
"The delay pushed everything else back.", "Another call finally got it moving.",
"A confirmation would save a lot of chasing.", "Everything else was ready.",
"It wasn't an urgent transfer, but the wait was excessive.", "The escort was helpful once they arrived.",
"Please make the queue visible to the ward.", "It happened on the previous shift as well.",
],
}

# sentiment | stage | category (or -) | text. Mixed entries remain negative per the guide.
BACKGROUND = """
positive|care_on_the_ward|-|The nurse made time to sit down and listen instead of talking from the doorway.
positive|care_on_the_ward|-|Someone brought an extra blanket without me even asking.
positive|operations_and_procedures|-|The theatre team explained the checks before starting and I felt included.
positive|examination_and_diagnosis|-|The person doing my scan talked me through each part.
positive|admissions|-|Reception pointed me to the right desk straight away.
positive|discharge_and_transfers|-|Leaving was well organised and I knew exactly what to do next.
positive|care_on_the_ward|-|The physio helped me feel confident about walking again.
positive|unclear|-|Thanks to the volunteer who walked with us instead of just pointing.
positive|care_on_the_ward|-|Small thing, but remembering how I like my tea helped.
positive|operations_and_procedures|-|The recovery team were calm and explained why they were checking on me.
neutral|unclear|-|Is there a map showing the accessible entrance?
neutral|care_on_the_ward|-|Could visitors get drinking water nearer the ward?
neutral|admissions|-|I used the side entrance and checked in at the reception desk.
neutral|examination_and_diagnosis|-|The test was done in another department and I came back afterwards.
neutral|operations_and_procedures|-|We went through the consent form before the procedure.
neutral|discharge_and_transfers|-|I left with the papers and a number for follow-up.
negative|care_on_the_ward|environment|The meal was cold by the time it got to my bed.
negative|unclear|environment|Finding a parking space took longer than expected.
negative|care_on_the_ward|respect_and_rights|Someone discussed my personal care with the curtain open.
negative|examination_and_diagnosis|listening|I tried explaining what worried me about the test but was talked over.
negative|care_on_the_ward|quality|My pillow was damp and I couldn't get a dry one for a while.
negative|admissions|institutional_processes|I had to fill in the same registration information twice.
positive|care_on_the_ward|-|A colleague covered my break without being asked.
positive|examination_and_diagnosis|-|The imaging team called back promptly with the clarification we needed.
positive|operations_and_procedures|-|The safety pause gave everyone a chance to speak.
positive|admissions|-|Admissions sent the correct paperwork with the patient this time.
positive|discharge_and_transfers|-|The social worker sorted out the home support early.
positive|care_on_the_ward|-|The senior nurse helped with a difficult conversation instead of leaving me to manage alone.
neutral|care_on_the_ward|-|We tried the new layout for the supplies drawer on this shift.
neutral|unclear|-|Could the staff room have somewhere to refill a water bottle?
neutral|examination_and_diagnosis|-|The team reviewed the investigation list after the round.
neutral|operations_and_procedures|-|We checked the procedure list together at the start of the day.
negative|care_on_the_ward|environment|There was nowhere nearby to take a proper break.
negative|unclear|institutional_processes|The mandatory training link keeps sending me back to the login screen.
negative|care_on_the_ward|respect_and_rights|A colleague was spoken to sharply in front of the whole bay.
negative|examination_and_diagnosis|communication|The report was available but the team wasn't notified.
negative|care_on_the_ward|safety|A duplicate dose was prepared and caught in the final medication check.
negative|care_on_the_ward|safety|The wrong patient's label was on the specimen tube before we caught it.
negative|care_on_the_ward|safety|I nearly fell when the wet floor wasn't marked.
negative|discharge_and_transfers|safety|The dose on my take-home list was wrong and had to be corrected before I used it.
""".strip().splitlines()

BACKGROUND_DETAILS = {
"positive": ["That made the day easier.", "I appreciated it.", "It helped more than they probably realised.",
             "Please pass on my thanks.", "I wanted to mention something that went well.",
             "It took some of the stress out of the day.", "A good experience overall.",
             "I felt looked after.", "It was a busy day too.", "Worth recognising.",
             "Nobody made a fuss about it.", "The difference was noticeable."],
"neutral": ["Just a thought.", "I'm not sure who to ask.", "Nothing else to add.",
            "This was during the morning.", "Maybe this is already planned.",
            "It would be useful to know.", "I noticed it on this visit.", "For information.",
            "This might be worth checking.", "I haven't used this service before.",
            "There may be a reason for it.", "I'm recording it here so I don't forget."],
"negative": ["It left a poor impression.", "I mentioned it at the time.", "That part needs attention.",
             "The rest of the day went better.", "I didn't know who could sort it out.",
             "Please look into it.", "Not a great experience.", "It could have been handled better.",
             "I wouldn't want it to happen again.", "It was frustrating.", "Someone did eventually listen.",
             "The team were helpful afterwards."],
}
