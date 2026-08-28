import random
from datetime import date, time
from typing import Dict, List, Any, Tuple

NARRATIVE_STYLES = [
    "FORMAL_FIR",
    "CHRONOLOGICAL",
    "COMPLAINT_STYLE",
    "OFFICER_INVESTIGATION",
    "WITNESS_LED",
    "EVIDENCE_LED",
]

CRIME_DETAILS_TEMPLATES: Dict[str, List[Dict[str, Any]]] = {
    "VEHICLE_THEFT": [
        {
            "mo": "Targeted parked SUV/Motorcycle using master/duplicate key after dark",
            "details": "parked outside the commercial complex near the main market road. The owner locked the vehicle at around {time} and returned to find the parking space empty with no broken glass on the ground.",
            "tools": "duplicate master key, electronic key jammer",
            "loss": "Mahindra Scorpio SUV valued at approx. Rs. 14 Lakhs",
        },
        {
            "mo": "Two-wheeler lifting from residential apartment parking bay during early morning hours",
            "details": "parked inside the open basement parking area of the residential society. The culprits cut the handlebar lock mechanism quietly before fleeing towards the state highway.",
            "tools": "lock-cutter tool, universal ignition key",
            "loss": "Hero Splendor motorcycle (OD02 registered)",
        },
        {
            "mo": "Intercepted unattended delivery vehicle during transit stop",
            "details": "left briefly idling outside a local grocery shop while the driver stepped out for a delivery receipt signature.",
            "tools": "opportunity theft",
            "loss": "Commercial Bolero pickup truck along with retail goods",
        },
    ],
    "HOUSE_BURGLARY": [
        {
            "mo": "Night break-in by cutting rear iron window grilles using hydraulic cutter",
            "details": "while the occupants were away attending a family function in Puri. The perpetrators entered through the rear balcony after severing three iron window bars.",
            "tools": "hydraulic cutter, heavy iron crowbar, gloves",
            "loss": "Gold ornaments weighing 120 grams and cash Rs. 1,80,000/- stored in bedroom godrej almirah",
        },
        {
            "mo": "Rooftop lattice lock breaking during early morning rainstorm",
            "details": "by breaking open the rooftop staircase door lock. The suspects ransacked the master bedroom and escaped through the rear boundary wall.",
            "tools": "bolt cutter, screwdriver set, torch light",
            "loss": "Diamond ring, silver coins, and cash Rs. 95,000/-",
        },
    ],
    "CYBER_FINANCIAL_FRAUD": [
        {
            "mo": "Stock market investment scam via WhatsApp advisory group",
            "details": "wherein the victim was added to an unauthorized WhatsApp group named 'Odisha Elite Traders'. The victim was persuaded to install a fraudulent APK trading app and transfer funds to multiple mule bank accounts.",
            "tools": "phishing APK, fake Telegram/WhatsApp admin handles, mule bank accounts",
            "loss": "Rs. 6,80,000/- transferred across 4 separate IMPS transactions",
        },
        {
            "mo": "APK phishing and SIM swap financial fraud",
            "details": "after the victim received a fraudulent SMS regarding electricity bill disconnection. Clicking the embedded link downloaded a malicious malware application that intercepted OTPs.",
            "tools": "malicious APK link, SMS spoofing gateway",
            "loss": "Rs. 3,25,000/- debited from victim's savings account",
        },
    ],
    "CHAIN_SNATCHING": [
        {
            "mo": "Motorcycle-borne snatchers targeting morning walkers",
            "details": "approached from behind on a black un-numbered motorcycle. The pillion rider forcefully yanked the victim's gold chain before speeding off towards the bypass road.",
            "tools": "speed motorcycle, helmet face disguise",
            "loss": "22-carat gold chain weighing 25 grams valued at Rs. 1,50,000/-",
        },
    ],
    "PHYSICAL_ASSAULT": [
        {
            "mo": "Rival group altercation over land boundary dispute",
            "details": "escalated near the village chhak when the accused group assembled unlawfully armed with wooden lathis and sharp weapons, inflicting head injuries on the complainant.",
            "tools": "bamboo lathis, iron rods",
            "loss": "Severe physical trauma requiring emergency medical admission",
        },
    ],
}


def generate_varied_narrative(
    rng: random.Random,
    crime_type: str,
    police_station: str,
    registration_date: date,
    incident_date: date,
    incident_time: time,
    complainant_name: str,
    accused_name: str,
    location_address: str,
    fir_number: str,
) -> Tuple[str, str]:
    """Generates a unique, non-template FIR narrative across 6 distinct narrative structures."""

    style = rng.choice(NARRATIVE_STYLES)
    category_templates = CRIME_DETAILS_TEMPLATES.get(
        crime_type, CRIME_DETAILS_TEMPLATES["VEHICLE_THEFT"]
    )
    item = rng.choice(category_templates)

    t_str = incident_time.strftime("%I:%M %p") if incident_time else "late evening hours"
    d_str = incident_date.strftime("%d-%b-%Y") if incident_date else "recently"

    if style == "FORMAL_FIR":
        text = (
            f"On {registration_date.strftime('%d-%b-%Y')}, complainant {complainant_name} appeared at {police_station} "
            f"and presented a written petition regarding an incident of {crime_type.lower().replace('_', ' ')} that occurred on {d_str} "
            f"at approximately {t_str} near {location_address}. As per the FIR registration statement, the incident involved "
            f"{item['mo'].lower()}. The property in question was {item['details'].format(time=t_str)}. "
            f"Preliminary inspection indicates the involvement of suspect(s) including {accused_name}. Total reported loss/damage is estimated at {item['loss']}. "
            f"Case registered under relevant provisions of law and SI in-charge has initiated technical investigation."
        )

    elif style == "CHRONOLOGICAL":
        text = (
            f"CHRONOLOGY OF INCIDENT ({fir_number}):\n"
            f"1. On {d_str} at around {t_str}, complainant {complainant_name} was present at {location_address}.\n"
            f"2. Without prior warning, perpetrator(s) identified as or associated with {accused_name} executed a planned crime involving {item['mo'].lower()}.\n"
            f"3. Specifically, the victim reported that property was {item['details'].format(time=t_str)}.\n"
            f"4. Tools/weapons observed or suspected include {item['tools']}. Total estimated loss is {item['loss']}.\n"
            f"5. On {registration_date.strftime('%d-%b-%Y')}, formal information was logged at {police_station} for prompt law enforcement action."
        )

    elif style == "COMPLAINT_STYLE":
        text = (
            f"EXTRACT FROM WRITTEN COMPLAINT FILED BY {complainant_name.upper()}:\n"
            f"\"Respected Officer-in-Charge, {police_station}, I am writing to report a serious offense committed on {d_str} at around {t_str}. "
            f"While I was at {location_address}, unknown culprits / accused {accused_name} committed {crime_type.lower().replace('_', ' ')}. "
            f"The modus operandi appeared to be {item['mo'].lower()}. Our {item['details'].format(time=t_str)}. "
            f"We suffered a financial/property loss of {item['loss']}. I request immediate police intervention, seizure of evidence, and arrest of the culprits.\""
        )

    elif style == "OFFICER_INVESTIGATION":
        text = (
            f"INVESTIGATING OFFICER SPOT INSPECTION REPORT ({police_station}):\n"
            f"Upon receiving oral information from complainant {complainant_name} regarding FIR {fir_number}, the undersigned police team proceeded to {location_address}. "
            f"Physical examination of the crime spot confirmed {crime_type.lower().replace('_', ' ')} executed on {d_str} at {t_str}. "
            f"The crime scene revealed evidence of {item['mo'].lower()}. Witnesses confirmed that {item['details'].format(time=t_str)}. "
            f"Suspect involvement of {accused_name} is currently under verification. Suspected instruments used: {item['tools']}. Total property affected: {item['loss']}."
        )

    elif style == "WITNESS_LED":
        text = (
            f"WITNESS-LED INCIDENT REPORT:\n"
            f"Statements recorded at {location_address} following the registration of FIR {fir_number} at {police_station} on {registration_date.strftime('%d-%b-%Y')}. "
            f"Eyewitnesses present during the incident on {d_str} at {t_str} reported observing suspicious movements by individuals linked with {accused_name}. "
            f"The incident of {crime_type.lower().replace('_', ' ')} was characterized by {item['mo'].lower()}. "
            f"According to witnesses, the target area was {item['details'].format(time=t_str)}. Complainant {complainant_name} suffered a total loss of {item['loss']}."
        )

    else:  # EVIDENCE_LED
        text = (
            f"TECHNICAL & FORENSIC EVIDENCE SUMMARY ({police_station} / {fir_number}):\n"
            f"Technical investigation initiated into the reported {crime_type.lower().replace('_', ' ')} incident occurring on {d_str} at {t_str} near {location_address}. "
            f"Initial technical analysis (CCTV / CDR / Physical exhibits) aligns with {item['mo'].lower()}. "
            f"The physical location analysis indicates that property was {item['details'].format(time=t_str)}. "
            f"Technical indicators link the crime scene to suspect(s) including {accused_name}. Total reported damage/loss stands at {item['loss']}. Complainant: {complainant_name}."
        )

    return text, style
