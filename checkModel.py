from openai import OpenAI
import config

client = OpenAI(
    api_key=config.LLM_API_KEY,
    base_url=config.LLM_BASE_URL
)

try:
    models = client.models.list()

    print("\nAvailable models:")
    for model in models.data:
        print(model.id)

except Exception as e:
    print("Error connecting to Groq:", e)