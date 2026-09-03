from datetime import datetime, timezone

import httpx

from app.config import settings
from app.ingestion.base import BaseSocialAdapter
from app.schemas.social import NormalizedPost

class XAdapter(BaseSocialAdapter):
    endpoint = "https://api.x.com/2/tweets/search/recent"

    async def fetch_posts(self, query: str = "technology", limit: int = 15) -> list[NormalizedPost]:
        token = settings.X_BEARER_TOKEN.strip()
        requested_limit = max(1, min(limit, 100))
        if token:
            try:
                params = {
                    "query": f"({query.strip()}) -is:retweet",
                    "max_results": max(10, requested_limit),
                    "tweet.fields": "created_at,author_id,public_metrics,referenced_tweets,lang",
                    "expansions": "author_id",
                    "user.fields": "username,description",
                }
                headers = {"Authorization": f"Bearer {token}"}
                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.get(self.endpoint, params=params, headers=headers)
                if response.status_code != 200:
                    raise RuntimeError(f"X API request failed ({response.status_code}): {response.text[:300]}")
                payload = response.json()
            except (httpx.HTTPError, RuntimeError, ValueError) as error:
                if not settings.X_DEMO_FALLBACK:
                    raise RuntimeError(str(error)) from error
                return self._demo_posts(query, requested_limit, str(error))
        elif settings.X_DEMO_FALLBACK:
            return self._demo_posts(query, requested_limit, "X_BEARER_TOKEN is not configured")
        else:
            raise RuntimeError("X_BEARER_TOKEN is not configured")

        users = {
            user["id"]: user
            for user in payload.get("includes", {}).get("users", [])
        }
        normalized = []
        for tweet in payload.get("data", [])[:requested_limit]:
            try:
                created_dt = datetime.fromisoformat(tweet["created_at"].replace("Z", "+00:00"))
            except (KeyError, ValueError):
                created_dt = datetime.now(timezone.utc)

            author = users.get(tweet.get("author_id"), {})
            metrics = tweet.get("public_metrics", {})
            parent_post_id = next(
                (
                    f"x_{reference['id']}"
                    for reference in tweet.get("referenced_tweets", [])
                    if reference.get("type") == "replied_to"
                ),
                None,
            )
            normalized.append(NormalizedPost(
                platform="x",
                platform_post_id=f"x_{tweet['id']}",
                author_id=f"usr_{tweet.get('author_id', 'x_user')}",
                author_username=author.get("username"),
                author_bio=author.get("description"),
                text=tweet.get("text", ""),
                language=tweet.get("lang") or "en",
                created_at=created_dt,
                parent_post_id=parent_post_id,
                engagement_count={
                    "likes": metrics.get("like_count", 0),
                    "shares": metrics.get("retweet_count", 0),
                    "comments": metrics.get("reply_count", 0),
                },
                raw_data={
                    "source": "x_api_v2",
                    "query": query,
                    "tweet_id": tweet.get("id"),
                },
            ))
        return normalized

    @staticmethod
    def _demo_posts(query: str, limit: int, reason: str) -> list[NormalizedPost]:
        clean_query = query.replace("#", "").strip() or "technology"
        templates = [
            f"Breaking: Security advisory issued regarding #{clean_query} demonstrations and crowd aggregation.",
            f"Civic monitoring team reports elevated social sentiment shifts around #{clean_query}.",
            f"Critical discussions emerging across public forums concerning policy impacts on #{clean_query}.",
        ]
        return [
            NormalizedPost(
                platform="x",
                platform_post_id=f"x_demo_{clean_query}_{index}",
                author_id=f"demo_x_user_{index + 1}",
                author_username=f"demo_x_user_{index + 1}",
                author_bio="Demo account for Civic Shield testing",
                text=templates[index % len(templates)],
                language="en",
                created_at=datetime.now(timezone.utc),
                engagement_count={"likes": 45, "shares": 18, "comments": 6},
                raw_data={"source": "x_demo_fallback", "query": query, "reason": reason},
            )
            for index in range(limit)
        ]