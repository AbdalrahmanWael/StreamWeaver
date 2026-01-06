"""
Minimal example: A chatbot that streams responses.

Uses StreamWeaver with FastAPI for real-time streaming.
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


@app.post("/chat")
async def chat(message: str, session_id: str):
    """
    Start a chat session and process the message.
    """
    await weaver.register_session(session_id, user_request=message)

    asyncio.create_task(process_message(session_id, message))

    return {"session_id": session_id}


async def process_message(session_id: str, message: str):
    """Simulate agent processing with streaming events."""

    await weaver.publish(
        session_id=session_id,
        event_type=StreamEventType.WORKFLOW_STARTED,
        message="Processing your message...",
    )

    await asyncio.sleep(1)

    await weaver.publish(
        session_id=session_id,
        event_type=StreamEventType.STEP_STARTED,
        message="Thinking...",
    )

    await asyncio.sleep(1)

    await weaver.publish(
        session_id=session_id,
        event_type=StreamEventType.AGENT_MESSAGE,
        message=f"I received your message: {message}",
        data={"original_message": message},
    )

    await asyncio.sleep(0.5)

    await weaver.publish(
        session_id=session_id,
        event_type=StreamEventType.WORKFLOW_COMPLETED,
        message="Done!",
        data={"response": f"Hello! You said: {message}"},
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
    uvicorn.run(app, host="0.0.0.0", port=8000)
