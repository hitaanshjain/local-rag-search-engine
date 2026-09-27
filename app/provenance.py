"""Extract document scope labels from PDF title material without guessing."""

import re

US_STATES = {
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut", "Delaware",
    "District of Columbia", "Florida", "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa",
    "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
    "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire", "New Jersey",
    "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon",
    "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah",
    "Vermont", "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming",
}


def infer_document_provenance(pages: list[str]) -> dict[str, str]:
    text = "\n".join(pages[:2])
    result = {}
    city = re.search(r"(?im)^City of[ \t]*(?:\n[ \t]*)?([A-Za-z][A-Za-z ]+(?:,[ \t]*[A-Za-z ]+)?)$", text)
    # A "Place, State" line counts only when the state is real; table cells can look alike.
    place = next((
        match for match in re.finditer(
            r"(?m)^([A-Z][a-z]+(?: [A-Z][a-z]+)*),[ \t]*([A-Z][a-z]+(?: [A-Z][a-z]+)*)[ \t]*$", text
        )
        if match.group(2) in US_STATES
    ), None)
    ordinance = re.search(r"\b([A-Z][a-z]+(?: [A-Z][a-z]+)*) Zoning Ordinance\b", text)
    central = re.search(r"\bCentral ([A-Z][a-z]+)\b", text)
    planning = re.search(r"\b([A-Z][a-z]+(?: [A-Z][a-z]+)*) Department of City Planning\b", text)
    if city:
        result["jurisdiction"] = city.group(1).strip().title()
    elif place:
        result["jurisdiction"] = f"{place.group(1)}, {place.group(2)}"
    elif ordinance:
        result["jurisdiction"] = re.sub(r"^(?:The|A) ", "", ordinance.group(1))
    elif central:
        result["jurisdiction"] = central.group(1)
    elif planning:
        result["jurisdiction"] = planning.group(1)

    revision = re.search(r"(?im)^([A-Z][a-z]+ \d{1,2}, \d{4}, Rev\.)", text)
    supplement = re.search(r"(?im)^SUPPLEMENT NO\.[ \t]*(\d+)[ \t]*\n[ \t]*([A-Z][a-z]+ \d{4})", text)
    updated = re.search(r"(?im)^Updated:[^\n]*?\b(\d{1,2}-\d{1,2}-\d{2,4})\b", text)
    adopted = re.search(r"(?i)\b(Adopted [A-Z][a-z]+ \d{1,2}, \d{4})\b", text)
    if revision:
        result["version"] = revision.group(1)
    elif supplement:
        result["version"] = f"Supplement No. {supplement.group(1)}, {supplement.group(2)}"
    elif updated:
        result["version"] = f"Updated {updated.group(1)}"
    elif adopted:
        result["version"] = adopted.group(1)
    return result
