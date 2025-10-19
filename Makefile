.PHONY: dev prod

dev:
	uv run streamlit run markdoc/app.py

prod:
	uv run streamlit run markdoc/app.py --server.runOnSave false --server.headless true
