# Changelog

All notable changes to StreamWeaver will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-01-06

### Added

- **Event Replay** - Full reconnection support with `Last-Event-ID` header
  - `EventBuffer` class for storing recent events per session
  - `SessionEventBuffers` manager for multi-session replay
  - Automatic replay of missed events on reconnection

- **Backpressure Handling** - Configurable queue overflow policies
  - `BackpressureQueue` with `DROP_OLDEST`, `DROP_NEWEST`, and `BLOCK` policies
  - Dropped event counters for monitoring
  - Configurable queue size per session

- **Event Filtering** - Filter events before delivery
  - `VisibilityFilter` - Filter by `EventVisibility`
  - `TypeFilter` - Filter by `StreamEventType`
  - `CompositeFilter` - Combine filters with AND/OR logic
  - `NotFilter` - Invert filter results
  - `CallableFilter` - Custom predicate functions
  - `SessionFilter` - Filter by session ID
  - Pre-built filters: `USER_FACING_FILTER`, `LIVE_UI_FILTER`, `NO_HEARTBEAT_FILTER`

- **Redis Session Storage** - Production-ready distributed storage
  - `RedisSessionStore` implementing `SessionStore` interface
  - Connection pooling with configurable pool size
  - TTL-based automatic session expiration
  - JSON serialization of session data

- **Observability** - Prometheus metrics
  - Event counters: `events_published_total`, `events_dropped_total`
  - Session gauges: `active_sessions`, `active_streams`
  - Queue metrics: `queue_depth`
  - Latency histograms: `event_publish_duration_seconds`
  - Graceful degradation when `prometheus_client` not installed

- **WebSocket Transport** - Alternative to SSE
  - `WebSocketStreamHandler` for FastAPI
  - Bidirectional communication support
  - Ping/pong keepalive
  - Message handler registration

- **Event Batching** - Reduce overhead for high-frequency events
  - `EventBatcher` with configurable batch size and timeout
  - Immediate event types bypass batching
  - `BatcherPool` for multi-session batching

- **Event Schemas** - Pydantic models for validation
  - Typed data models for all event types
  - Helper functions: `create_workflow_started()`, `create_error()`, etc.
  - `validate_event_data()` for strict validation

- **Event Visibility** - Control event audience
  - `EventVisibility.USER_FACING` - For UI and model
  - `EventVisibility.MODEL_ONLY` - For model memory only
  - `EventVisibility.LIVE_UI_ONLY` - For real-time UI
  - `EventVisibility.INTERNAL_ONLY` - For logging/debugging

- **Event ID** - Unique identifier per event
  - `event_id` field with UUID generation
  - SSE `id:` field for reconnection support
  - `to_dict()` and `from_dict()` serialization methods

### Changed

- **Breaking**: Minimum Python version is now 3.9 (was 3.8)
- **Breaking**: `check_capacity()` is now async
- FastAPI integration now uses lifespan context manager
- Heartbeat interval is now configurable (was hardcoded to 30s)
- Event queues are now bounded with configurable size
- Development status changed from Alpha to Beta

### Fixed

- Fixed `asyncio.run()` blocking call in async context (`check_capacity`)
- Fixed example imports (`EventType` → `StreamEventType`)
- Fixed deprecated `@app.on_event("startup")` pattern
- Fixed unbounded queue memory issue

### Deprecated

- `@app.on_event("startup")` pattern in examples (use lifespan instead)

## [0.1.0] - 2025-12-01

### Added

- Initial release
- Core SSE streaming implementation
- `StreamEvent` dataclass with SSE format conversion
- `StreamEventType` enum for workflow events
- `EventVisibility` enum for event targeting
- `SessionData` and `SessionStore` abstractions
- `InMemorySessionStore` for development
- `StreamGenerator` for SSE event generation
- `StreamWeaver` main service class
- `StreamWeaverConfig` configuration model
- FastAPI integration with `setup_streaming_routes()`
- Heartbeat mechanism
- Event callbacks
- Session cleanup
- Basic examples (simple agent, multi-step workflow)
- React client example
- Comprehensive test suite (18 tests)
- GitHub Actions CI/CD
- Pre-commit hooks (black, ruff, mypy)
- MIT License

---

## Upgrade Guide

### From 0.1.x to 0.2.0

1. **Update Python version**: Ensure Python 3.9+

2. **Update FastAPI startup**:
   ```python
   # Before
   @app.on_event("startup")
   async def startup():
       await weaver.initialize()
   
   # After
   @asynccontextmanager
   async def lifespan(app: FastAPI):
       await weaver.initialize()
       yield
       await weaver.shutdown()
   
   app = FastAPI(lifespan=lifespan)
   ```

3. **Update imports** (if using examples):
   ```python
   # Before
   from streamweaver import EventType
   
   # After
   from streamweaver import StreamEventType
   ```

4. **Update `check_capacity()` calls**:
   ```python
   # Before
   if weaver.check_capacity():
   
   # After
   if await weaver.check_capacity():
   ```
