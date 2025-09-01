#!/usr/bin/env python3

import argparse
import json

def search(args):
    from ddgs import DDGS
    with DDGS() as ddgs:
        if args.type == "text":
            results = [r for r in ddgs.text(args.query, max_results=args.max_results)]
            return [{"title": r['title'], "url": r['href'], "snippet": r['body']} for r in results]
        elif args.type == "images":
            results = [r for r in ddgs.images(args.query, max_results=args.max_results)]
            return [{"title": r['title'], "url": r['image'], "thumbnail": r['thumbnail']} for r in results]
        elif args.type == "news":
            results = [r for r in ddgs.news(args.query, max_results=args.max_results)]
            return [{"title": r['title'], "url": r['url'], "snippet": r['body']} for r in results]
        else:
            return []

def tool_duck_search(argstr):
    """
    Tool wrapper for agent: accepts a JSON string or a plain query string.
    JSON form: {"query":"...", "type":"text"|"images"|"news", "max_results":10}
    Plain form: treated as query text.
    Returns JSON string of results.
    """
    try:
        params = json.loads(argstr)
        if isinstance(params, str):
            query = params
            qtype = "text"
            max_results = 10
        else:
            query = params.get("query") or params.get("q") or ""
            qtype = params.get("type", "text")
            max_results = params.get("max_results", params.get("maxResults", 10))
    except Exception:
        query = (argstr or "").strip()
        qtype = "text"
        max_results = 10
    from types import SimpleNamespace
    args = SimpleNamespace(query=query, type=qtype, max_results=max_results)
    try:
        results = search(args)
        return json.dumps(results, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})

def main():
    parser = argparse.ArgumentParser(description="DuckDuckGo Search CLI Tool for PiControl or general use")
    parser.add_argument("--query", type=str, required=True, help="Search query")
    parser.add_argument("--type", type=str, default="text", choices=["text", "images", "news"], help="Search type")
    parser.add_argument("--max-results", type=int, default=10, help="Maximum number of results")

    args = parser.parse_args()

    results = search(args)
    print(json.dumps(results))

if __name__ == "__main__":
    main()
