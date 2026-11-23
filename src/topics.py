"""
topics.py - Lightweight, dependency-free topic and region tagging.

Each story gets one primary topic (Politics, Conflict, Business...) and the
regions/countries it mentions, so the site can offer Ground News-style topic
and region feeds. Keyword lists are deliberately simple; extend them freely.
"""
import re
from typing import Dict, List, Tuple

TOPICS: Dict[str, List[str]] = {
    "Conflict": ["war", "strike", "strikes", "missile", "drone", "troops", "military", "ceasefire", "truce",
                 "army", "attack", "attacks", "airstrike", "shelling", "invasion", "hostage", "hostages",
                 "militants", "insurgents", "rebels", "frontline", "bombing", "killed", "soldiers", "nato",
                 "hamas", "hezbollah", "houthi", "houthis", "idf", "offensive", "peace talks", "peace deal"],
    "Politics": ["election", "elections", "vote", "voters", "parliament", "president", "prime minister",
                 "minister", "government", "opposition", "party", "coalition", "senate", "congress", "lawmakers",
                 "campaign", "referendum", "policy", "sanctions", "diplomat", "diplomatic", "summit", "trump",
                 "white house", "chancellor", "cabinet", "impeachment", "apec", "g20", "un general assembly"],
    "Crime & Justice": ["court", "trial", "judge", "arrested", "arrest", "police", "charged", "sentenced",
                        "prison", "murder", "cartel", "smuggling", "fraud", "investigation", "lawsuit", "verdict",
                        "genocide", "icj", "icc", "extradited", "execution", "death penalty", "drug"],
    "Business": ["economy", "economic", "market", "markets", "stocks", "inflation", "trade", "tariff", "tariffs",
                 "bank", "interest rates", "gdp", "oil prices", "company", "companies", "investors", "deal",
                 "exports", "imports", "jobs", "unemployment", "budget", "debt", "loans", "imf", "world bank"],
    "Tech": ["ai", "artificial intelligence", "tech", "technology", "chip", "chips", "semiconductor", "cyber",
             "hack", "hackers", "software", "internet", "social media", "tiktok", "meta", "google", "apple",
             "microsoft", "openai", "anthropic", "satellite", "spacex", "robot", "data centre", "data center"],
    "Climate & Environment": ["climate", "emissions", "cop", "carbon", "warming", "wildfire", "wildfires",
                              "flood", "floods", "drought", "heatwave", "hurricane", "typhoon", "cyclone",
                              "earthquake", "storm", "pollution", "biodiversity", "deforestation", "glacier"],
    "Health": ["health", "virus", "outbreak", "ebola", "covid", "vaccine", "vaccines", "disease", "hospital",
               "hospitals", "doctors", "cancer", "world health organization", "pandemic", "measles", "cholera", "mpox", "malaria"],
    "Science": ["scientists", "study", "research", "nasa", "space", "astronomers", "discovery", "fossil",
                "species", "archaeologists", "telescope"],
    "Migration": ["migrants", "migrant", "refugees", "refugee", "asylum", "deportation", "deported", "border",
                  "immigration", "smugglers"],
    "Human Rights": ["human rights", "rights groups", "protest", "protests", "protesters", "crackdown",
                     "dissidents", "censorship", "rohingya", "persecution", "women's rights", "activists"],
    "Sports": ["football", "soccer", "olympics", "world cup", "cricket", "tennis", "fifa", "championship",
               "tournament", "league", "match"],
    "Culture": ["film", "museum", "festival", "art", "music", "royal", "king charles", "pope", "vatican",
                "celebrity", "book", "heritage"],
}

# country / place keyword → (display name, region)
PLACES: Dict[str, Tuple[str, str]] = {}


def _add(region: str, entries: Dict[str, List[str]]):
    for country, keys in entries.items():
        for k in [country.lower()] + keys:
            PLACES[k] = (country, region)


_add("Europe", {
    "Ukraine": ["ukrainian", "ukrainians", "kyiv", "kharkiv", "odesa", "zelensky", "zelenskyy", "kryvyi rih"],
    "Russia": ["russian", "russians", "moscow", "kremlin", "putin"],
    "UK": ["britain", "british", "england", "scotland", "wales", "london", "starmer", "united kingdom"],
    "France": ["french", "paris", "macron"],
    "Germany": ["german", "berlin", "merz"],
    "Italy": ["italian", "rome", "meloni"],
    "Spain": ["spanish", "madrid"],
    "Poland": ["polish", "warsaw"],
    "EU": ["european union", "brussels", "european commission", "von der leyen"],
    "Hungary": ["hungarian", "budapest", "orban"],
    "Turkey": ["turkish", "ankara", "istanbul", "erdogan", "türkiye"],
    "Netherlands": ["dutch", "amsterdam"],
    "Belarus": ["belarusian", "minsk", "lukashenko"],
    "Serbia": ["serbian", "belgrade"],
    "Greece": ["greek", "athens"],
    "Ireland": ["irish", "dublin"],
})
_add("Middle East", {
    "Israel": ["israeli", "israelis", "netanyahu", "jerusalem", "tel aviv", "idf"],
    "Gaza": ["gazans", "palestinian", "palestinians", "west bank", "hamas"],
    "Iran": ["iranian", "tehran", "khamenei"],
    "Lebanon": ["lebanese", "beirut", "hezbollah"],
    "Syria": ["syrian", "damascus"],
    "Iraq": ["iraqi", "baghdad"],
    "Saudi Arabia": ["saudi", "riyadh"],
    "Yemen": ["yemeni", "houthi", "houthis"],
    "Qatar": ["qatari", "doha"],
    "UAE": ["emirati", "dubai", "abu dhabi"],
    "Egypt": ["egyptian", "cairo", "sisi"],
})
_add("Asia-Pacific", {
    "China": ["chinese", "beijing", "xi jinping", "shanghai", "shenzhen", "hong kong", "taiwan", "taiwanese"],
    "Japan": ["japanese", "tokyo"],
    "South Korea": ["south korean", "seoul"],
    "North Korea": ["north korean", "pyongyang", "kim jong un"],
    "Philippines": ["filipino", "filipinos", "manila"],
    "Australia": ["australian", "canberra", "sydney"],
    "Indonesia": ["indonesian", "jakarta"],
    "Myanmar": ["burma", "rohingya"],
    "Vietnam": ["vietnamese", "hanoi"],
    "Thailand": ["thai", "bangkok"],
    "New Zealand": ["auckland", "wellington"],
})
_add("South Asia", {
    "India": ["indian", "new delhi", "delhi", "modi", "mumbai"],
    "Pakistan": ["pakistani", "islamabad"],
    "Afghanistan": ["afghan", "kabul", "taliban"],
    "Bangladesh": ["bangladeshi", "dhaka"],
    "Sri Lanka": ["colombo"],
    "Nepal": ["kathmandu"],
})
_add("Africa", {
    "Sudan": ["sudanese", "khartoum", "darfur", "rsf"],
    "DR Congo": ["congo", "congolese", "kinshasa", "m23"],
    "Nigeria": ["nigerian", "abuja", "lagos"],
    "South Africa": ["south african", "johannesburg", "pretoria", "cape town"],
    "Ethiopia": ["ethiopian", "addis ababa", "tigray"],
    "Kenya": ["kenyan", "nairobi"],
    "Somalia": ["somali", "mogadishu"],
    "Libya": ["libyan", "tripoli"],
    "Mali": ["malian", "bamako"],
})
_add("Americas", {
    "US": ["u.s.", "united states", "american", "americans", "washington", "trump", "white house", "pentagon",
           "congress", "senate"],
    "Canada": ["canadian", "ottawa", "carney"],
    "Mexico": ["mexican", "mexico city", "sheinbaum"],
    "Brazil": ["brazilian", "brasilia", "lula"],
    "Venezuela": ["venezuelan", "caracas", "maduro"],
    "Argentina": ["argentine", "buenos aires", "milei"],
    "Colombia": ["colombian", "bogota", "petro"],
    "Cuba": ["cuban", "havana"],
    "Haiti": ["haitian", "port-au-prince"],
    "Chile": ["chilean", "santiago"],
    "Peru": ["peruvian", "lima"],
})

_TOKEN_CACHE: Dict[str, re.Pattern] = {}


def _pattern(key: str) -> re.Pattern:
    p = _TOKEN_CACHE.get(key)
    if p is None:
        p = re.compile(r"(?<![a-z])" + re.escape(key) + r"(?![a-z])")
        _TOKEN_CACHE[key] = p
    return p


def classify_topic(title: str, summary: str = "") -> str:
    """Pick the best-matching topic; title matches count triple."""
    t, s = (title or "").lower(), (summary or "").lower()
    best, best_score = "World", 0.0
    for topic, keys in TOPICS.items():
        score = 0.0
        for k in keys:
            p = _pattern(k)
            score += 3 * len(p.findall(t)) + len(p.findall(s))
        if score > best_score:
            best, best_score = topic, score
    return best if best_score >= 2 else "World"


def find_places(title: str, summary: str = "") -> List[Dict[str, str]]:
    """Countries/places mentioned, most-mentioned first: [{name, region}]."""
    text = f"{title} {title} {summary}".lower()  # title weighted double
    hits: Dict[str, Tuple[int, str]] = {}
    for key, (country, region) in PLACES.items():
        n = len(_pattern(key).findall(text))
        if n:
            prev = hits.get(country, (0, region))
            hits[country] = (prev[0] + n, region)
    ranked = sorted(hits.items(), key=lambda kv: -kv[1][0])
    return [{"name": c, "region": r} for c, (_, r) in ranked[:4]]


def primary_region(places: List[Dict[str, str]]) -> str:
    return places[0]["region"] if places else "Global"
