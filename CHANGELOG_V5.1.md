# ResearchAI UI & Conversation Upgrade

## Added
- ChatGPT-style conversation threads with separate saved chats per user.
- Automatic chat titles generated from the first user question.
- Searchable conversation list in the Streamlit sidebar.
- New chat, rename chat and delete chat actions.
- Persistent conversation loading after login/restart.
- User account metadata: `created_at`, `last_login`, `login_count`.
- Polished sign-in / create-account experience.
- User profile area with sign-out and account statistics.
- Conversation-aware RAG and image-question history.
- Automatic migration of legacy v5 messages into a `Previous research` conversation.
- Updated README/API documentation.

## Security
- Passwords remain scrypt-hashed.
- JWT authentication is retained.
- Conversation and document data remain scoped to the authenticated user.
- No plaintext passwords are stored.
