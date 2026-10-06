# vendor_detector.py
# Indicators are hypotheses; unverified rules must be checked against real vendor samples before higher confidence is allowed.

VENDOR_RULES = [
    {
        "vendor": "HIKVISION",
        "type": "MAGIC",
        "value": b"IMKH",
        "offset": 0,
        "strength": "MEDIUM",
        "description": "HIKVISION IMKH magic at offset 0",
        "rule_status": "UNVERIFIED_PUBLIC_KNOWLEDGE"
    },
    {
        "vendor": "HIKVISION",
        "type": "STRING",
        "value": b"HIKVISION",
        "strength": "LOW",
        "description": "HIKVISION ASCII string anywhere in header",
        "rule_status": "UNVERIFIED_PUBLIC_KNOWLEDGE"
    },
    {
        "vendor": "DAHUA",
        "type": "MAGIC",
        "value": b"DHAV",
        "offset": 0,
        "strength": "MEDIUM",
        "description": "DAHUA DHAV magic at offset 0",
        "rule_status": "UNVERIFIED_PUBLIC_KNOWLEDGE"
    },
    {
        "vendor": "DAHUA",
        "type": "EXTENSION",
        "value": ".dav",
        "strength": "LOW",
        "description": "DAHUA .dav extension",
        "rule_status": "UNVERIFIED_PUBLIC_KNOWLEDGE"
    }
]

def _get_extension(filename: str) -> str:
    # Filenames are user-controlled and easy to fake.
    # A vendor name inside the filename is NEVER an indicator.
    if "." not in filename:
        return ""
    ext = filename.rsplit(".", 1)[-1]
    if not ext:
        return ""
    return "." + ext.lower()

def detect_vendor(header: bytes, filename: str, rules=None) -> dict:
    if rules is None:
        rules = VENDOR_RULES

    indicators = []
    
    ext = _get_extension(filename)
    
    for rule in rules:
        matched = False
        if rule["type"] == "MAGIC":
            offset = rule["offset"]
            val = rule["value"]
            if len(header) >= offset + len(val) and header[offset:offset+len(val)] == val:
                matched = True
        elif rule["type"] == "STRING":
            if rule["value"] in header:
                matched = True
        elif rule["type"] == "EXTENSION":
            if ext == rule["value"].lower():
                matched = True
                
        if matched:
            indicators.append({
                "vendor": rule["vendor"],
                "type": rule["type"],
                "description": rule["description"],
                "strength": rule["strength"],
                "rule_status": rule["rule_status"]
            })
            
    notes = []
    has_unverified = any(ind["rule_status"] == "UNVERIFIED_PUBLIC_KNOWLEDGE" for ind in indicators) or any(r["rule_status"] == "UNVERIFIED_PUBLIC_KNOWLEDGE" for r in rules)
    if has_unverified:
        notes.append("Confidence is capped at MEDIUM because some rules are UNVERIFIED_PUBLIC_KNOWLEDGE.")

    if not indicators:
        notes.append("No vendor indicators found. This does not prove the file is not from a DVR/NVR.")
        return {
            "vendor": "UNKNOWN",
            "confidence": "NONE",
            "conflict": False,
            "indicators": indicators,
            "notes": notes
        }
        
    vendors_found = {ind["vendor"] for ind in indicators}
    
    if len(vendors_found) > 1:
        notes.append("Indicators point to more than one vendor. Vendor is left UNKNOWN and all indicators are listed for manual review.")
        return {
            "vendor": "UNKNOWN",
            "confidence": "NONE",
            "conflict": True,
            "indicators": indicators,
            "notes": notes
        }
        
    vendor = list(vendors_found)[0]
    
    # Calculate confidence for the single vendor
    # Strength values: HIGH, MEDIUM, LOW
    strength_map = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    max_strength = max((strength_map[ind["strength"]] for ind in indicators), default=0)
    
    # Raise to MEDIUM if two or more DIFFERENT indicator types agree
    types_found = {ind["type"] for ind in indicators}
    if len(types_found) >= 2 and max_strength < 2:
        max_strength = 2
        
    # Cap at MEDIUM if unverified
    if has_unverified and max_strength > 2:
        max_strength = 2
        
    conf_str = {3: "HIGH", 2: "MEDIUM", 1: "LOW", 0: "NONE"}[max_strength]
    
    return {
        "vendor": vendor,
        "confidence": conf_str,
        "conflict": False,
        "indicators": indicators,
        "notes": notes
    }
