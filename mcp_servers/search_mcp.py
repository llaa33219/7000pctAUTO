"""
Search MCP Server for 7000%AUTO
Provides search functionality across arXiv, Reddit, Hacker News, Product Hunt
"""

import logging
import xml.etree.ElementTree as ET
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

mcp = FastMCP("Search Server")


@mcp.tool()
async def search_arxiv(query: str, max_results: int = 5) -> dict:
    """
    Search arXiv papers for the given query.
    
    Args:
        query: Search query string
        max_results: Maximum number of results to return (default 5)
    
    Returns:
        Dictionary with papers list containing title, summary, authors, link, published date
    """
    try:
        url = "http://export.arxiv.org/api/query"
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending"
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
        
        # Parse XML response
        root = ET.fromstring(response.text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        
        papers = []
        for entry in root.findall("atom:entry", ns):
            title = entry.find("atom:title", ns)
            summary = entry.find("atom:summary", ns)
            published = entry.find("atom:published", ns)
            link = entry.find("atom:id", ns)
            
            authors = []
            for author in entry.findall("atom:author", ns):
                name = author.find("atom:name", ns)
                if name is not None:
                    authors.append(name.text)
            
            papers.append({
                "title": title.text.strip() if title is not None else "",
                "summary": summary.text.strip()[:500] if summary is not None else "",
                "authors": authors[:3],
                "link": link.text if link is not None else "",
                "published": published.text if published is not None else ""
            })
        
        return {"success": True, "papers": papers, "count": len(papers)}
    
    except Exception as e:
        logger.error(f"arXiv search failed: {e}")
        return {"success": False, "error": str(e), "papers": []}


@mcp.tool()
async def search_reddit(subreddit: str, query: str, limit: int = 10) -> dict:
    """
    Search Reddit posts in a specific subreddit.
    
    Args:
        subreddit: Subreddit name (e.g., "programming")
        query: Search query string
        limit: Maximum number of results (default 10)
    
    Returns:
        Dictionary with posts list containing title, score, url, comments count
    """
    try:
        url = f"https://www.reddit.com/r/{subreddit}/search.json"
        params = {
            "q": query,
            "restrict_sr": "on",
            "sort": "relevance",
            "t": "month",
            "limit": limit
        }
        headers = {"User-Agent": "7000AUTO/1.0"}
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
        
        posts = []
        for child in data.get("data", {}).get("children", []):
            post = child.get("data", {})
            posts.append({
                "title": post.get("title", ""),
                "score": post.get("score", 0),
                "url": f"https://reddit.com{post.get('permalink', '')}",
                "comments": post.get("num_comments", 0),
                "created_utc": post.get("created_utc", 0)
            })
        
        return {"success": True, "posts": posts, "count": len(posts)}
    
    except Exception as e:
        logger.error(f"Reddit search failed: {e}")
        return {"success": False, "error": str(e), "posts": []}


@mcp.tool()
async def search_hackernews(query: str, limit: int = 10) -> dict:
    """
    Search Hacker News via Algolia API.
    
    Args:
        query: Search query string
        limit: Maximum number of results (default 10)
    
    Returns:
        Dictionary with stories list containing title, points, url, comments count
    """
    try:
        url = "https://hn.algolia.com/api/v1/search"
        params = {
            "query": query,
            "tags": "story",
            "hitsPerPage": limit
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        
        stories = []
        for hit in data.get("hits", []):
            stories.append({
                "title": hit.get("title", ""),
                "points": hit.get("points", 0),
                "url": hit.get("url", f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"),
                "comments": hit.get("num_comments", 0),
                "author": hit.get("author", ""),
                "created_at": hit.get("created_at", "")
            })
        
        return {"success": True, "stories": stories, "count": len(stories)}
    
    except Exception as e:
        logger.error(f"Hacker News search failed: {e}")
        return {"success": False, "error": str(e), "stories": []}


@mcp.tool()
async def search_producthunt(days: int = 7) -> dict:
    """
    Get recent Product Hunt posts via RSS feed.
    
    Args:
        days: Number of days to look back (default 7)
    
    Returns:
        Dictionary with products list containing title, tagline, url
    """
    try:
        # Product Hunt doesn't have a free API, use RSS feed
        url = "https://www.producthunt.com/feed"
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url)
            response.raise_for_status()
        
        # Parse RSS XML
        root = ET.fromstring(response.text)
        
        products = []
        for item in root.findall(".//item")[:20]:
            title = item.find("title")
            link = item.find("link")
            description = item.find("description")
            
            products.append({
                "title": title.text if title is not None else "",
                "tagline": description.text[:200] if description is not None and description.text else "",
                "url": link.text if link is not None else ""
            })
        
        return {"success": True, "products": products, "count": len(products)}
    
    except Exception as e:
        logger.error(f"Product Hunt search failed: {e}")
        return {"success": False, "error": str(e), "products": []}


if __name__ == "__main__":
    mcp.run()
