from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.config import settings
from app.core.database import get_db, SessionLocal
from app.models.post import Post
from app.models.sentiment import SentimentResult
from app.workers.pipeline_worker import run_analytics_pipeline

router = APIRouter(prefix="/analytics", tags=["Analytics & Pipeline"])

def background_pipeline_job():
    db = SessionLocal()
    try:
        run_analytics_pipeline(db)
    finally:
        db.close()

@router.get("/status", summary="Get analytics processing status")
def get_pipeline_status(db: Session = Depends(get_db)):
    total_posts = db.query(func.count(Post.id)).scalar() or 0
    processed_posts = db.query(func.count(Post.id)).filter(Post.is_processed.is_(True)).scalar() or 0
    pending_posts = total_posts - processed_posts
    last_processed_at = db.query(func.max(SentimentResult.created_at)).scalar()

    return {
        "status": "processing" if pending_posts else "complete",
        "total_posts": total_posts,
        "processed_posts": processed_posts,
        "pending_posts": pending_posts,
        "last_processed_at": last_processed_at.isoformat() if last_processed_at else None,
        "ai_provider": "groq" if settings.GROQ_API_KEY.strip() else "fallback",
        "ai_model": settings.GROQ_MODEL if settings.GROQ_API_KEY.strip() else None,
    }

@router.post("/run-pipeline", summary="Trigger NLP & Graph processing")
def trigger_pipeline(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    result = run_analytics_pipeline(db)
    return {"message": "Pipeline execution finished", "result": result}