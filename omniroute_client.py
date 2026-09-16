"""OmniRoute AI Gateway Client"""
import os
from openai import OpenAI

# Initialize OmniRoute client (localhost:20128 default)
OMNIROUTE_BASE_URL = os.getenv("OMNIROUTE_URL", "http://localhost:20128/v1")
OMNIROUTE_MODEL = os.getenv("OMNIROUTE_MODEL", "auto")

client = OpenAI(
    api_key="sk-free",  # Dummy key for free tier
    base_url=OMNIROUTE_BASE_URL
)


def query_ai(prompt: str, model: str = OMNIROUTE_MODEL, temperature: float = 0.7, max_tokens: int = 1500) -> str:
    """Query OmniRoute AI gateway."""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens
        )
        msg = response.choices[0].message
        return msg.content
    except Exception as e:
        raise RuntimeError(f"OmniRoute error: {str(e)}")


def summarize_text(text: str, max_tokens: int = 200) -> str:
    """Summarize text using OmniRoute."""
    prompt = f"Resuma o texto abaixo em poucas frases, em Portugues do Brasil. Responda apenas o resumo, sem introducao.\n\nTexto:\n{text}"
    return query_ai(prompt, max_tokens=max_tokens + 500)


def generate_description(subject: str, context: str = "", max_tokens: int = 300) -> str:
    """Generate description for a subject using OmniRoute."""
    prompt = f"Crie uma descricao profissional em Portugues do Brasil para: {subject}"
    if context:
        prompt += f"\nContexto: {context}"
    prompt += "\nResponda apenas a descricao, sem titulo adicional."
    return query_ai(prompt, max_tokens=max_tokens + 500)


def analyze_data(data_description: str, query: str, max_tokens: int = 400) -> str:
    """Analyze data patterns using OmniRoute."""
    prompt = f"Analise os dados abaixo e responda em Portugues do Brasil:\n\nDados: {data_description}\n\nPergunta: {query}"
    return query_ai(prompt, max_tokens=max_tokens + 500)
