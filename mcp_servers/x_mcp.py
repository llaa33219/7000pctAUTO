"""
X/Twitter MCP Server for 7000%AUTO
Provides Twitter posting and search functionality
"""

import logging
import os
from typing import Optional

import tweepy
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

mcp = FastMCP("X API Server")

# Twitter API credentials from environment
API_KEY = os.getenv("X_API_KEY", "")
API_SECRET = os.getenv("X_API_SECRET", "")
ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN", "")
ACCESS_TOKEN_SECRET = os.getenv("X_ACCESS_TOKEN_SECRET", "")
BEARER_TOKEN = os.getenv("X_BEARER_TOKEN", "")


def get_client() -> Optional[tweepy.Client]:
    """Get authenticated Twitter client"""
    if not all([API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET]):
        return None
    
    return tweepy.Client(
        consumer_key=API_KEY,
        consumer_secret=API_SECRET,
        access_token=ACCESS_TOKEN,
        access_token_secret=ACCESS_TOKEN_SECRET,
        bearer_token=BEARER_TOKEN if BEARER_TOKEN else None,
        wait_on_rate_limit=True
    )


@mcp.tool()
async def post_tweet(text: str) -> dict:
    """
    Post a tweet to X/Twitter.
    
    Args:
        text: Tweet text (max 280 characters)
    
    Returns:
        Dictionary with tweet URL and status
    """
    try:
        if len(text) > 280:
            return {
                "success": False,
                "error": f"Tweet exceeds 280 characters (got {len(text)})"
            }
        
        client = get_client()
        if not client:
            return {
                "success": False,
                "error": "Twitter API credentials not configured"
            }
        
        response = client.create_tweet(text=text)
        tweet_id = response.data["id"]
        
        # Get username for URL construction
        me = client.get_me()
        username = me.data.username if me.data else "user"
        
        tweet_url = f"https://twitter.com/{username}/status/{tweet_id}"
        
        logger.info(f"Posted tweet: {tweet_url}")
        
        return {
            "success": True,
            "tweet_id": tweet_id,
            "url": tweet_url,
            "text": text,
            "character_count": len(text)
        }
    
    except tweepy.TweepyException as e:
        logger.error(f"Twitter API error: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Error posting tweet: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def search_tweets(query: str, max_results: int = 10) -> dict:
    """
    Search recent tweets on X/Twitter.
    
    Args:
        query: Search query string
        max_results: Maximum number of results (default 10, max 100)
    
    Returns:
        Dictionary with list of tweets
    """
    try:
        client = get_client()
        if not client:
            return {
                "success": False,
                "error": "Twitter API credentials not configured"
            }
        
        max_results = min(max_results, 100)
        
        response = client.search_recent_tweets(
            query=query,
            max_results=max_results,
            tweet_fields=["created_at", "public_metrics", "author_id"]
        )
        
        tweets = []
        if response.data:
            for tweet in response.data:
                tweets.append({
                    "id": tweet.id,
                    "text": tweet.text,
                    "created_at": tweet.created_at.isoformat() if tweet.created_at else "",
                    "metrics": tweet.public_metrics if hasattr(tweet, "public_metrics") else {}
                })
        
        return {
            "success": True,
            "tweets": tweets,
            "count": len(tweets)
        }
    
    except tweepy.TweepyException as e:
        logger.error(f"Twitter search error: {e}")
        return {"success": False, "error": str(e), "tweets": []}
    except Exception as e:
        logger.error(f"Error searching tweets: {e}")
        return {"success": False, "error": str(e), "tweets": []}


@mcp.tool()
async def get_rate_limit_status() -> dict:
    """
    Get current rate limit status for the Twitter API.
    
    Returns:
        Dictionary with rate limit information
    """
    try:
        client = get_client()
        if not client:
            return {
                "success": False,
                "error": "Twitter API credentials not configured"
            }
        
        # Basic check by getting user info
        me = client.get_me()
        
        return {
            "success": True,
            "authenticated": True,
            "username": me.data.username if me.data else None
        }
    
    except tweepy.TweepyException as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    mcp.run()
