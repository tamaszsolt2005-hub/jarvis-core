import google.generativeai as genai

def analyze_incoming_reply(reply_text, gemini_api_key):
    """Elemzi a beérkező választ a Gemini AI segítségével."""
    if not reply_text:
        return "later"
        
    genai.configure(api_key=gemini_api_key)
    prompt = (
        f"Elemezd az alábbi B2B partneri válaszlevelet, és állapítsd meg a szándékát. "
        f"Válassz pontosan egy kategóriát: [INTERESTED] (ha kér árajánlatot, találkozót vagy érdeklődik), "
        f"[LATER] (ha később keressük), vagy [REJECTED] (ha nem kéri).\n\n"
        f"Levél szövege:\n{reply_text}"
    )
    
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        result = response.text.strip().upper()
        
        if "INTERESTED" in result:
            return "interested"
        elif "LATER" in result:
            return "later"
        else:
            return "rejected"
    except Exception:
        return "later"
