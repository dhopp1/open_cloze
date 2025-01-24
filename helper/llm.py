import google.generativeai as genai


def get_gemini(query, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-pro")

    generation_config = genai.types.GenerationConfig(
        temperature=0.0,
        max_output_tokens=512,
    )

    response = model.generate_content(query, generation_config=generation_config)

    return response.text
