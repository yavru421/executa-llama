#!/usr/bin/env python3

import argparse
from ddgs import DDGS
import json

def search(args):
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

def main():
    parser = argparse.ArgumentParser(description="DuckDuckGo Search CLI Tool")
    parser.add_argument("--query", type=str, required=True, help="Search query")
    parser.add_argument("--type", type=str, default="text", choices=["text", "images", "news"], help="Search type")
    parser.add_argument("--max-results", type=int, default=10, help="Maximum number of results")

    args = parser.parse_args()

    results = search(args)
    print(json.dumps(results))

if __name__ == "__main__":
    main()