import google.generativeai as genai

def analyze_incoming_reply(reply_text):
    """Elemzi a beérkező választ a Gemini AI segítségével."""
    prompt = (
        f"Elemezd az alábbi B2B partneri válaszlevelet, és állapítsd meg a szándékát. "
        f"Válassz pontosan egy kategóriát: [INTERESTED] (ha kér árajánlatot, találkozót vagy érdeklődik), "
        f"[LATER] (ha később keressük), vagy [REJECTED] (ha nem kéri).\n\n"
        f"Levél szövege:\n{reply_text}"
    )
    
    model = genai.GenerativeModel('gemini-2.5-flash')
    response = model.generate_content(prompt)
    result = response.text.strip().upper()
    
    if "INTERESTED" in result:
        return "interested"
    elif "LATER" in result:
        return "later"
    else:
        return "rejected"
