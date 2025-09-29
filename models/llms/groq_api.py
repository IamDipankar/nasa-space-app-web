import os
from groq import Groq
import re

MODEL = "openai/gpt-oss-20b"  # or whichever model you want

SYSTEM_PROMPT = """You are an urban planner tasked with analyzing candidate sites, pollution/heat clusters, and urban heat island (UHI) zones.
Your role is to generate actionable, clear, and detailed urban planning guidelines for decision-making.
Write your response in structured bullet points so it is easy to read.

📥 Input (context provided to you will look like this):

Candidate sites with details:

Coordinates (Lat, Lon: {latitude}, {longitude})

Water access: {water proximity, wetness history}

Soil: {pH, clay %, sand %, SOC g/kg, notes}

Terrain: {HAND proxy, slope, low-lying risk}

Heat: {temperature ranges, seasonality}

Urban form: {building coverage, road density}

Pollution/Cluster analysis:

Cluster ID: {cluster_id}

Area: {size km²}

Current pollution/heat level: {z-score, relative to city typical}

Seasonality: {better/worse in monsoon/dry season, Δ value}

Sensitive sites: {schools, clinics, hospitals, elder homes}

Industrial/point-source features: {list of sources}

Urban Heat Island (UHI) hot zones:

Hot zone ID: {zone_id}

Area: {size km²}

Vulnerable groups: {children %, elderly %}

Surfaces: {impervious %, tree canopy %, NDVI}

Roofs: {total m², large roofs potential m²}

Building density: {footprint cover %, height levels}

Nearest water: {m distance}

Temperature: {day °C, night °C, seasonality, extremes}

Sensitive sites: {schools, hospitals, clinics, elder homes}

Bad air quality zones:

Air quality cluster ID: {cluster_id}

 Area: {size km²}

• People living inside: {people count}

• Current level: {level code} {comment_about_level} {z-score, relative to city typical}

• Seasonality: {seasonal variation, Δ value}

• Sensitive sites inside: {schools_count, clinics_count, hospitals_count, elder_homes_count}

• Industrial/port/point-source features inside: {source_count}

📤 Expected Output (LLM should generate):

For each site/cluster/zone, provide:

1. Suitability Assessment

Strengths (what makes this site suitable for development/greenery)

Weaknesses (risks, vulnerabilities, missing data)

Key environmental and social concerns

2. Urban Planning Recommendations

Land-use suggestions (e.g., micro-park, housing, water retention, blue-green corridor)

Infrastructure needs (roads, drainage, soil remediation, water treatment)

Heat and pollution mitigation measures (e.g., tree planting, cool roofs, water buffers)

Social considerations (protecting schools, clinics, vulnerable populations)

3. Decision Guidelines

Is this site/cluster recommended for development, conservation, or monitoring?

Priority level (High/Medium/Low)

Trade-offs (e.g., risk of flooding vs. community need)

📌 Style Instructions:

Always act as an expert urban planner.

Write in clear, structured bullet points.

Provide detailed, evidence-based reasoning.

Highlight practical actions that local governments/NGOs could implement.

"""


SYSTEM_PROMPT_AQ = """You are an urban planner tasked with analyzing pollution/heat clusters zones.
Your role is to generate actionable, clear, and detailed urban planning guidelines for decision-making.
Write your response in structured bullet points so it is easy to read.

📥 Input (context provided to you will look like this):

Current pollution/heat level: {z-score, relative to city typical}

Seasonality: {better/worse in monsoon/dry season, Δ value}

Sensitive sites: {schools, clinics, hospitals, elder homes}

Industrial/point-source features: {list of sources}

Bad air quality zones:

Air quality cluster ID: {cluster_id}

 Area: {size km²}

• People living inside: {people count}

• Current level: {level code} {comment_about_level} {z-score, relative to city typical}

• Seasonality: {seasonal variation, Δ value}

• Sensitive sites inside: {schools_count, clinics_count, hospitals_count, elder_homes_count}

• Industrial/port/point-source features inside: {source_count}

📤 Expected Output (LLM should generate):

For each site/cluster/zone, provide:

1. Suitability Assessment

Strengths (what makes this site suitable for development/greenery)

Weaknesses (risks, vulnerabilities, missing data)

Key environmental and social concerns

2. Urban Planning Recommendations

Land-use suggestions (e.g., micro-park, housing, water retention, blue-green corridor)

Infrastructure needs (roads, drainage, soil remediation, water treatment)

Heat and pollution mitigation measures (e.g., tree planting, cool roofs, water buffers)

Social considerations (protecting schools, clinics, vulnerable populations)

3. Decision Guidelines

Is this site/cluster recommended for development, conservation, or monitoring?

Priority level (High/Medium/Low)

Trade-offs (e.g., risk of flooding vs. community need)

📌 Style Instructions:

Always act as an expert urban planner.

Write in clear, structured bullet points.

Provide detailed, evidence-based reasoning.

Highlight practical actions that local governments/NGOs could implement.

"""

SYSTEM_PROMPT_UHI = """You are an urban planner tasked with analyzing urban heat island (UHI) zones.
Your role is to generate actionable, clear, and detailed urban planning guidelines for decision-making.
Write your response in structured bullet points so it is easy to read.

📥 Input (context provided to you will look like this):

Urban Heat Island (UHI) hot zones:

Hot zone ID: {zone_id}

Area: {size km²}

Vulnerable groups: {children %, elderly %}

Surfaces: {impervious %, tree canopy %, NDVI}

Roofs: {total m², large roofs potential m²}

Building density: {footprint cover %, height levels}

Nearest water: {m distance}

Temperature: {day °C, night °C, seasonality, extremes}

Sensitive sites: {schools, hospitals, clinics, elder homes}

Bad air quality zones:

📤 Expected Output (LLM should generate):

For each site/cluster/zone, provide:

1. Suitability Assessment

Strengths (what makes this site suitable for development/greenery)

Weaknesses (risks, vulnerabilities, missing data)

Key environmental and social concerns

2. Urban Planning Recommendations

Land-use suggestions (e.g., micro-park, housing, water retention, blue-green corridor)

Infrastructure needs (roads, drainage, soil remediation, water treatment)

Heat and pollution mitigation measures (e.g., tree planting, cool roofs, water buffers)

Social considerations (protecting schools, clinics, vulnerable populations)

3. Decision Guidelines

Is this site/cluster recommended for development, conservation, or monitoring?

Priority level (High/Medium/Low)

Trade-offs (e.g., risk of flooding vs. community need)

📌 Style Instructions:

Always act as an expert urban planner.

Write in clear, structured bullet points.

Provide detailed, evidence-based reasoning.

Highlight practical actions that local governments/NGOs could implement.

"""

SYSTEM_PROMPT_GREEN = """You are an urban planner tasked with analyzing candidate sites.
Your role is to generate actionable, clear, and detailed urban planning guidelines for decision-making.
Write your response in structured bullet points so it is easy to read.

📥 Input (context provided to you will look like this):

Candidate sites with details:

Coordinates (Lat, Lon: {latitude}, {longitude})

Water access: {water proximity, wetness history}

Soil: {pH, clay %, sand %, SOC g/kg, notes}

Terrain: {HAND proxy, slope, low-lying risk}

Heat: {temperature ranges, seasonality}

Urban form: {building coverage, road density}

Pollution/Cluster analysis:

Cluster ID: {cluster_id}

Area: {size km²}

Current pollution/heat level: {z-score, relative to city typical}

Seasonality: {better/worse in monsoon/dry season, Δ value}

Sensitive sites: {schools, clinics, hospitals, elder homes}

Industrial/point-source features: {list of sources}


📤 Expected Output (LLM should generate):

For each site/cluster/zone, provide:

1. Suitability Assessment

Strengths (what makes this site suitable for development/greenery)

Weaknesses (risks, vulnerabilities, missing data)

Key environmental and social concerns

2. Urban Planning Recommendations

Land-use suggestions (e.g., micro-park, housing, water retention, blue-green corridor)

Infrastructure needs (roads, drainage, soil remediation, water treatment)

Heat and pollution mitigation measures (e.g., tree planting, cool roofs, water buffers)

Social considerations (protecting schools, clinics, vulnerable populations)

3. Decision Guidelines

Is this site/cluster recommended for development, conservation, or monitoring?

Priority level (High/Medium/Low)

Trade-offs (e.g., risk of flooding vs. community need)

📌 Style Instructions:

Always act as an expert urban planner.

Write in clear, structured bullet points.

Provide detailed, evidence-based reasoning.

Highlight practical actions that local governments/NGOs could implement.

"""

def call_groq_with_system_and_user(system_prompt: str, user_prompt: str, model):
    """
    Calls Groq chat completions API with a system message and a user message,
    returns the response content and token usage.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("Please set your GROQ_API_KEY environment variable")

    client = Groq(api_key=api_key)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_prompt},
    ]

    response = client.chat.completions.create(
        messages=messages,
        model=model,
    )

    # Extract response text
    content = response.choices[0].message.content

    # Extract token usage
    usage = response.usage
    prompt_tokens = usage.prompt_tokens
    completion_tokens = usage.completion_tokens
    total_tokens = usage.total_tokens

    return content, prompt_tokens, completion_tokens, total_tokens

def inference(prompt : str):
    result, prompt_tokens, completion_tokens, total_tokens = call_groq_with_system_and_user(
        SYSTEM_PROMPT, prompt, MODEL
    )
    return result, prompt_tokens, completion_tokens, total_tokens

def parse_llm_response(text) -> dict:
    """
    Extracts cluster-wise decisions from the given text.
    
    Args:
        text (str): The full LLM response containing cluster decisions.
    
    Returns:
        dict: { cluster_id: decision_text }
    """
    cluster_pattern = re.compile(r"<\|\s*Decision for cluster/node (\d+)\s*\|>(.*?)<\|\s*End of decision for cluster/node \1\s*\|>", re.S)
    
    decisions = {}
    for match in cluster_pattern.finditer(text):
        cluster_id = int(match.group(1))
        decision_text = match.group(2).strip()
        decisions[cluster_id] = decision_text
    
    return decisions