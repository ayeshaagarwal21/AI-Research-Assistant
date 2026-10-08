from langchain_core.prompts import ChatPromptTemplate

# The model is told to answer with this exact sentence when the documents don't
# contain the answer; chat.py checks for it so it can hide irrelevant sources.
NOT_FOUND_MESSAGE = "I couldn't find that information in the uploaded documents."

RAG_PROMPT = ChatPromptTemplate.from_template(
    """
You are an intelligent AI Research Assistant.
Answer the user's question ONLY using the provided context.

Rules:
1. If the answer exists in the context, answer clearly and mention which
   document and page it came from, e.g. (report.pdf, p. 3).
2. If the answer is not in the context, reply exactly:
"""
    + NOT_FOUND_MESSAGE
    + """
3. Do not make up facts.
4. Keep answers concise but informative.
5. Use the earlier conversation only to understand follow-up questions
   (e.g. "explain that more"); the facts must still come from the context.

Earlier conversation:
{chat_history}

Context:
{context}

Question:
{question}

Answer:
"""
)


GENERAL_PROMPT = ChatPromptTemplate.from_template(
    """
You are a helpful AI assistant. Answer clearly and concisely.
If you are not sure about something, say so instead of guessing.

Earlier conversation:
{chat_history}

Question:
{question}

Answer:
"""
)
