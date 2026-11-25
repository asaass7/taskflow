import os
import requests

LLM_BASE_URL = os.getenv('LLM_BASE_URL', 'http://localhost:11434/v1')
LLM_API_KEY = os.getenv('LLM_API_KEY', 'ollama')
LLM_MODEL = os.getenv('LLM_MODEL', 'llama3.2:3b')
LLM_TIMEOUT = int(os.getenv('LLM_TIMEOUT', '60'))


class AgentError(Exception):
    """Ошибка интеграции с ИИ-агентом."""
    pass


SYSTEM_PROMPT = (
    "Ты — TaskBot, встроенный ИИ-помощник веб-приложения TaskFlow (трекер задач). "
    "Отвечай кратко, по-русски, вежливо. Помогай пользователю разобраться "
    "с возможностями приложения: создание задач, проекты, статусы, приоритеты, "
    "восстановление пароля. Не давай советов, не связанных с TaskFlow. "
    "Не раскрывай технические детали, ключи и пароли."
)


def ask_agent(history, user_text):
    """
    history: список {"role": ..., "content": ...} предыдущих реплик.
    user_text: новый вопрос пользователя.
    Возвращает текст ответа модели.
    Бросает AgentError при сбое.
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history[-10:])  # не более 10 последних реплик
    messages.append({"role": "user", "content": user_text})

    headers = {"Content-Type": "application/json"}
    if LLM_API_KEY and LLM_API_KEY != 'ollama':
        headers['Authorization'] = f'Bearer {LLM_API_KEY}'

    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 500,
    }

    try:
        resp = requests.post(
            LLM_BASE_URL.rstrip('/') + '/chat/completions',
            json=payload,
            headers=headers,
            timeout=LLM_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        answer = data['choices'][0]['message']['content']
    except requests.exceptions.Timeout:
        raise AgentError('ИИ-агент не ответил вовремя. Попробуйте ещё раз.')
    except requests.exceptions.RequestException:
        raise AgentError('Сервис ИИ-агента временно недоступен.')
    except (KeyError, IndexError, ValueError):
        raise AgentError('Получен некорректный ответ сервиса ИИ.')

    return answer.strip()
