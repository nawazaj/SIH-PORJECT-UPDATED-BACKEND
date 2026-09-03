from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.post import Post
from app.models.sentiment import SentimentResult

router = APIRouter(prefix="/network", tags=["Network & Link Analysis"])


def _cascade_posts(posts: list[Post], topic: str | None) -> list[tuple[Post, int, str | None, str | None]]:
    posts_by_id = {str(post.id): post for post in posts}
    posts_by_platform_ref = {(post.platform, post.platform_post_id): post for post in posts}
    posts_by_ref = {}
    for post in posts:
        posts_by_ref.setdefault(post.platform_post_id, []).append(post)

    parent_by_id = {}
    children_by_id = {}
    for post in posts:
        parent = posts_by_id.get(str(post.parent_post_id))
        if parent is None:
            parent = posts_by_platform_ref.get((post.platform, post.parent_post_id))
        if parent is None:
            candidates = posts_by_ref.get(post.parent_post_id, [])
            if len(candidates) == 1:
                parent = candidates[0]
        if parent is not None and parent.id != post.id:
            parent_by_id[post.id] = parent
            children_by_id.setdefault(parent.id, []).append(post)

    for children in children_by_id.values():
        children.sort(key=lambda post: (post.created_at, str(post.id)))

    if topic:
        needle = topic.casefold()
        seeds = [post for post in posts if needle in post.text.casefold()]
        selected_ids = {post.id for post in seeds}
        for seed in seeds:
            ancestor = parent_by_id.get(seed.id)
            while ancestor is not None and ancestor.id not in selected_ids:
                selected_ids.add(ancestor.id)
                ancestor = parent_by_id.get(ancestor.id)

        pending = list(seeds)
        while pending:
            current = pending.pop()
            for child in children_by_id.get(current.id, []):
                if child.id not in selected_ids:
                    selected_ids.add(child.id)
                    pending.append(child)
    else:
        selected_ids = {post.id for post in posts}

    selected = [post for post in posts if post.id in selected_ids]
    roots = [post for post in selected if post.id not in parent_by_id or parent_by_id[post.id].id not in selected_ids]
    roots.sort(key=lambda post: (post.created_at, str(post.id)))

    ordered = []
    visited = set()

    def visit(post: Post, depth: int, cascade_root: str):
        if post.id in visited or post.id not in selected_ids:
            return
        visited.add(post.id)
        parent = parent_by_id.get(post.id)
        ordered.append((post, depth, cascade_root, parent.author_id if parent else None))
        for child in children_by_id.get(post.id, []):
            visit(child, depth + 1, cascade_root)

    for root in roots:
        visit(root, 0, str(root.id))
    for post in sorted(selected, key=lambda item: (item.created_at, str(item.id))):
        visit(post, 0, str(post.id))
    return ordered

@router.get("/propagation-timeline", summary="Track chronological diffusion of discussions through influencers")
def get_propagation_timeline(
    topic: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Post, SentimentResult.sentiment, SentimentResult.emotion)
        .outerjoin(SentimentResult, Post.id == SentimentResult.post_id)
    )

    rows = query.all()
    sentiment_by_id = {
        post.id: (sentiment_value, emotion_value)
        for post, sentiment_value, emotion_value in rows
    }
    cascade = _cascade_posts([post for post, _, _ in rows], topic)
    
    cascade_events = []
    for post, depth, cascade_root, parent_author_id in cascade[:limit]:
        sentiment_value, emotion_value = sentiment_by_id[post.id]
        cascade_events.append({
            "timestamp": post.created_at.isoformat(),
            "platform": post.platform,
            "author_id": post.author_id,
            "parent_post_id": post.parent_post_id,
            "parent_author_id": parent_author_id,
            "depth": depth,
            "cascade_id": cascade_root,
            "sentiment": sentiment_value or "neutral",
            "emotion": emotion_value or "neutral",
            "snippet": post.text[:80]
        })
        
    return {
        "filtered_topic": topic or "all_topics",
        "total_cascade_steps": len(cascade_events),
        "cascade_flow": cascade_events
    }