"""
Complex example: Research agent with multiple steps.

Demonstrates step-by-step progress tracking with StreamWeaver.
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import uvicorn

from streamweaver import StreamWeaver, StreamEventType


# Initialize StreamWeaver
weaver = StreamWeaver()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown."""
    await weaver.initialize()
    yield
    await weaver.shutdown()


app = FastAPI(lifespan=lifespan)


@app.post("/research")
async def research(query: str, session_id: str):
    """Start a research workflow."""
    await weaver.register_session(session_id, user_request=query)

    asyncio.create_task(research_workflow(session_id, query))

    return {"session_id": session_id}


async def research_workflow(session_id: str, query: str):
    """Multi-step research workflow."""

    await weaver.publish(
        session_id=session_id,
        event_type=StreamEventType.WORKFLOW_STARTED,
        message=f"Starting research on: {query}",
    )

    total_steps = 4
    current_step = 0

    # Step 1: Web search
    current_step += 1
    await weaver.publish(
        session_id=session_id,
        event_type=StreamEventType.STEP_STARTED,
        message=f"Step {current_step}/{total_steps}: Searching web...",
        step_number=current_step,
        progress_percent=(current_step / total_steps) * 100,
    )

    await asyncio.sleep(1.5)

    await weaver.publish(
        session_id=session_id,
        event_type=StreamEventType.TOOL_EXECUTED,
        message="Search executed successfully",
        tool_used="web_search",
        data={"query": query, "results_found": 5},
    )

    await weaver.publish(
        session_id=session_id,
        event_type=StreamEventType.STEP_COMPLETED,
        message=f"Step {current_step} completed",
        step_number=current_step,
        progress_percent=(current_step / total_steps) * 100,
    )

    # Step 2: Content extraction
    current_step += 1
    await weaver.publish(
        session_id=session_id,
        event_type=StreamEventType.STEP_STARTED,
        message=f"Step {current_step}/{total_steps}: Extracting content...",
        step_number=current_step,
        progress_percent=(current_step / total_steps) * 100,
    )

    await asyncio.sleep(2)

    await weaver.publish(
        session_id=session_id,
        event_type=StreamEventType.STEP_PROGRESS,
        message="Processing documents...",
        step_number=current_step,
        data={"documents_processed": 3},
    )

    await weaver.publish(
        session_id=session_id,
        event_type=StreamEventType.STEP_COMPLETED,
        message=f"Step {current_step} completed",
        step_number=current_step,
        progress_percent=(current_step / total_steps) * 100,
    )

    # Step 3: Analysis
    current_step += 1
    await weaver.publish(
        session_id=session_id,
        event_type=StreamEventType.STEP_STARTED,
        message=f"Step {current_step}/{total_steps}: Analyzing findings...",
        step_number=current_step,
        progress_percent=(current_step / total_steps) * 100,
    )

    await asyncio.sleep(1.5)

    await weaver.publish(
        session_id=session_id,
        event_type=StreamEventType.AGENT_MESSAGE,
        message="Analysis complete. Preparing summary...",
        data={"key_findings": 7},
    )

    await weaver.publish(
        session_id=session_id,
        event_type=StreamEventType.STEP_COMPLETED,
        message=f"Step {current_step} completed",
        step_number=current_step,
        progress_percent=(current_step / total_steps) * 100,
    )

    # Step 4: Summary generation
    current_step += 1
    await weaver.publish(
        session_id=session_id,
        event_type=StreamEventType.STEP_STARTED,
        message=f"Step {current_step}/{total_steps}: Generating summary...",
        step_number=current_step,
        progress_percent=(current_step / total_steps) * 100,
    )

    await asyncio.sleep(1)

    summary = (
        f"Research summary for '{query}': Found 5 relevant sources. "
        "Key findings include recent developments in the area."
    )

    await weaver.publish(
        session_id=session_id,
        event_type=StreamEventType.WORKFLOW_COMPLETED,
        message="Research workflow completed!",
        step_number=current_step,
        progress_percent=100,
        data={"summary": summary, "total_steps": total_steps},
    )


@app.get("/stream/{session_id}")
async def stream(session_id: str):
    """Get SSE stream for a session."""
    stream_gen = await weaver.get_stream_response(session_id)

    return StreamingResponse(
        stream_gen,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        },
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
