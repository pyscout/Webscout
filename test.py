from webscout.search import DuckDuckGoSearch
ws = DuckDuckGoSearch()
results = ws.text("OpenAI", max_results=5)
print(results)
